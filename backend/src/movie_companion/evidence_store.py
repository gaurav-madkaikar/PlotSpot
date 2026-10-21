"""Bounded, single-writer teaching snapshots; retained revisions are explicit."""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Literal

import chromadb
from chromadb.config import Settings

from .chunking_learning import TextChunk
from .source_sections import SourceSection, source_chunks, section_for_chunk
from .retrieval_learning import EmbeddedPassage, _validate_vector
from .passage_location import PassageLocation


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    movie_id: int
    text: str
    source_label: str
    source_ref: str
    revision: str
    spoiler_status: Literal["safe", "spoiler", "unknown"] = "unknown"

    sections: tuple[SourceSection, ...] = ()

    def __post_init__(self):
        if not isinstance(self.source_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.source_id):
            raise ValueError("Source ID must be a short identifier")
        if type(self.movie_id) is not int or self.movie_id <= 0:
            raise ValueError("Movie ID must be a positive integer")
        for name, maximum in (("text", 100000), ("source_label", 200), ("source_ref", 500), ("revision", 100)):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"Invalid source {name}")
        if not isinstance(self.sections, (tuple, list)) or len(self.sections) > 200:
            raise ValueError("Expected bounded source sections")
        sections = tuple(SourceSection(**section) if isinstance(section, dict) else section for section in self.sections)
        cursor = 0
        for section in sections:
            if not isinstance(section, SourceSection) or section.start != cursor or section.end > len(self.text):
                raise ValueError("Sections must cover the source contiguously without overlap")
            cursor = section.end
        if sections and cursor != len(self.text):
            raise ValueError("Sections must cover the source end")
        object.__setattr__(self, "sections", sections)
        if self.spoiler_status not in ("safe", "spoiler", "unknown"):
            raise ValueError("Invalid spoiler status")


def snapshot_key(source: SourceDocument, *, model: str, max_chars: int, overlap_chars: int) -> str:
    if not isinstance(source, SourceDocument):
        raise ValueError("Expected a validated source record")
    if not isinstance(model, str) or not model.strip() or len(model) > 100:
        raise ValueError("Embedding model tag is required")
    chunks = source_chunks(source, max_chars=max_chars, overlap_chars=overlap_chars)
    if len(chunks) > (400 if source.sections else 200):
        raise ValueError("Teaching snapshots allow at most 200 chunks without sections or 400 with sections")
    identity = {
        "source": asdict(source), "model": model,
        "chunker_version": "section-windows-v1" if source.sections else "character-windows-v1", "document_prefix": "search_document: ",
        "max_chars": max_chars, "overlap_chars": overlap_chars,
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class EvidenceStore:
    def __init__(self, path: Path):
        self.client = chromadb.PersistentClient(
            path=str(path), settings=Settings(anonymized_telemetry=False),
        )

    def _collection(self, model: str):
        name = "evidence_v1_" + hashlib.sha256(model.encode()).hexdigest()[:24]
        return self.client.get_or_create_collection(name=name, embedding_function=None)

    @staticmethod
    def _metadata(source, key, model, chunk, count, index):
        section = section_for_chunk(source, chunk)
        return {
            "section_title": section.title if section else "Unclassified",
            "section_category": section.category if section else "other",
            "snapshot": key, "source_id": source.source_id, "movie_id": source.movie_id,
            "source_label": source.source_label, "source_ref": source.source_ref,
            "revision": source.revision, "spoiler_status": source.spoiler_status,
            "embedding_model": model, "start": chunk.start, "end": chunk.end,
            "chunk_count": count, "chunk_index": index,
        }

    def _read(self, source, *, model, max_chars, overlap_chars):
        key = snapshot_key(source, model=model, max_chars=max_chars, overlap_chars=overlap_chars)
        chunks = source_chunks(source, max_chars=max_chars, overlap_chars=overlap_chars)
        data = self._collection(model).get(
            where={"snapshot": key}, limit=401, include=["documents", "metadatas", "embeddings"],
        )
        return key, chunks, data

    def _complete(self, source, model, key, chunks, data):
        expected_ids = [f"{key[:32]}_{index:03}" for index in range(len(chunks))]
        if set(data["ids"]) != set(expected_ids) or data["embeddings"] is None:
            return False
        positions = {identifier: index for index, identifier in enumerate(data["ids"])}
        dimensions = None
        for index, (identifier, chunk) in enumerate(zip(expected_ids, chunks)):
            position = positions[identifier]
            if data["documents"][position] != chunk.text or data["metadatas"][position] != self._metadata(source, key, model, chunk, len(chunks), index):
                return False
            vector = data["embeddings"][position].tolist()
            try:
                _validate_vector(vector, dimensions)
            except ValueError:
                return False
            dimensions = len(vector)
        return True

    def contains_snapshot(self, source: SourceDocument, *, model: str, max_chars: int, overlap_chars: int) -> bool:
        key, chunks, data = self._read(source, model=model, max_chars=max_chars, overlap_chars=overlap_chars)
        return self._complete(source, model, key, chunks, data)

    def save_snapshot(self, source: SourceDocument, chunks: list[TextChunk], vectors: list[list[float]], *, model: str, max_chars: int, overlap_chars: int) -> None:
        key = snapshot_key(source, model=model, max_chars=max_chars, overlap_chars=overlap_chars)
        expected = source_chunks(source, max_chars=max_chars, overlap_chars=overlap_chars)
        if chunks != expected or not isinstance(vectors, list) or len(vectors) != len(chunks):
            raise ValueError("Chunks/vectors must correspond to the complete source snapshot")
        dimensions = None
        for vector in vectors:
            _validate_vector(vector, dimensions)
            dimensions = len(vector)
        # Upsert completes/replaces only this fingerprint, leaving other revisions intact.
        self._collection(model).upsert(
            ids=[f"{key[:32]}_{index:03}" for index in range(len(chunks))],
            documents=[chunk.text for chunk in chunks], embeddings=vectors,
            metadatas=[self._metadata(source, key, model, chunk, len(chunks), index) for index, chunk in enumerate(chunks)],
        )

    def load_snapshot(self, source: SourceDocument, *, model: str, max_chars: int, overlap_chars: int) -> list[EmbeddedPassage]:
        key, chunks, data = self._read(source, model=model, max_chars=max_chars, overlap_chars=overlap_chars)
        if not self._complete(source, model, key, chunks, data):
            raise ValueError("Snapshot is missing or incomplete; ingest it first")
        positions = {identifier: index for index, identifier in enumerate(data["ids"])}
        return [EmbeddedPassage(
            passage_id=f"{key[:32]}_{index:03}", movie_id=source.movie_id,
            text=chunk.text, vector=data["embeddings"][positions[f"{key[:32]}_{index:03}"]].tolist(),
            embedding_model=model, source_label=source.source_label,
            spoiler_status=source.spoiler_status,
            section_title=(section_for_chunk(source, chunk).title if source.sections else "Unclassified"),
            section_category=(section_for_chunk(source, chunk).category if source.sections else "other"),
            location=PassageLocation(
                key, source.movie_id, source.source_label, source.spoiler_status,
                source.text, chunk.start, chunk.end,
                (section_for_chunk(source, chunk).start if source.sections else 0),
                (section_for_chunk(source, chunk).end if source.sections else len(source.text)),
                (section_for_chunk(source, chunk).title if source.sections else 'Unclassified'),
                (section_for_chunk(source, chunk).category if source.sections else 'other'),
            ),
        ) for index, chunk in enumerate(chunks)]
