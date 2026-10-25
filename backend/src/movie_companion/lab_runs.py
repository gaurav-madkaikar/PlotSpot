"""Read-only, allowlisted projections of recent internal AI run records."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable, Literal
from urllib.parse import quote

from .lab_contracts import LabRunDetail, LabRunStage, LabRunSummary, LabWarning


RUN_ID = re.compile(r"^(?P<kind>prep|story)_(?P<id>[a-f0-9]{32})$")
TRACE_NAME = re.compile(r"^(?P<movie>[1-9][0-9]*)-(?P<id>[a-f0-9]{32})\.json$")
PREPARATION_STATES = {
    "queued",
    "running",
    "needs_review",
    "incomplete",
    "ready",
    "published",
    "failed",
    "cancelled",
    "interrupted",
}


def _warning(code, message):
    return LabWarning(code=code, suite_id=None, message=message)


def _timestamp(value) -> datetime:
    if not isinstance(value, str) or len(value) > 50:
        raise ValueError("Invalid timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


def _count_list(value, *, maximum=10_000):
    if not isinstance(value, list) or len(value) > maximum:
        return 0
    return len(value)


def _safe_title(loader, movie_id):
    if loader is None:
        return None
    try:
        value = loader(movie_id)
        return value[:200] if isinstance(value, str) and value.strip() else None
    except (OSError, ValueError, TypeError, KeyError):
        return None


class LabRunReader:
    def __init__(
        self,
        preparation_db: Path,
        trace_root: Path,
        title_lookup: Callable[[int], str | None] | None = None,
    ):
        self.preparation_db = Path(preparation_db)
        self.trace_root = Path(trace_root)
        self.title_lookup = title_lookup

    def list(
        self,
        workflow: Literal["preparation", "story_rag"] | None,
        state: str | None,
        limit: int,
    ) -> tuple[list[LabRunSummary], list[LabWarning]]:
        if workflow not in (None, "preparation", "story_rag"):
            raise ValueError("Invalid workflow")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError("Invalid run limit")
        records: list[tuple[LabRunSummary, LabRunDetail]] = []
        warnings: list[LabWarning] = []
        if workflow in (None, "preparation"):
            found, problems = self._preparation_records(50)
            records.extend(found)
            warnings.extend(problems)
        if workflow in (None, "story_rag"):
            found, problems = self._story_records(50)
            records.extend(found)
            warnings.extend(problems)
        records.sort(key=lambda pair: pair[0].updated_at, reverse=True)
        summaries = [summary for summary, _ in records]
        if state is not None:
            summaries = [record for record in summaries if record.state == state]
        return summaries[:limit], warnings[:20]

    def get(self, run_id: str) -> LabRunDetail | None:
        match = RUN_ID.fullmatch(run_id) if isinstance(run_id, str) else None
        if not match:
            raise ValueError("Invalid run ID")
        if match.group("kind") == "prep":
            records, _ = self._preparation_records(50, match.group("id"))
        else:
            records, _ = self._story_records(50, match.group("id"))
        return records[0][1] if records else None

    def _preparation_records(self, limit, identifier=None):
        if not self.preparation_db.exists():
            return [], [_warning("missing_source", "Preparation run records are unavailable.")]
        if self.preparation_db.is_symlink():
            return [], [_warning("invalid_source", "Preparation run records are invalid.")]
        try:
            resolved = self.preparation_db.resolve(strict=True)
            uri = f"file:{quote(str(resolved), safe='/')}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=2) as connection:
                connection.row_factory = sqlite3.Row
                if identifier:
                    rows = connection.execute(
                        "SELECT movie_id,id,state,payload,sequence FROM jobs WHERE id=? LIMIT 1",
                        (identifier,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT movie_id,id,state,payload,sequence FROM jobs ORDER BY sequence DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
        except (OSError, sqlite3.Error):
            return [], [_warning("invalid_source", "Preparation run records could not be read.")]
        records = []
        warnings = []
        for row in rows:
            try:
                records.append(self._preparation_record(row))
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                warnings.append(_warning("invalid_source", "A preparation run record was skipped."))
        return records, warnings

    def _preparation_record(self, row):
        body = row["payload"]
        if not isinstance(body, str) or len(body.encode("utf-8")) > 1_000_000:
            raise ValueError("Invalid checkpoint")
        record = json.loads(body)
        if not isinstance(record, dict):
            raise ValueError("Invalid checkpoint")
        identifier = record.get("id")
        movie_id = record.get("movie_id")
        state = record.get("state")
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[a-f0-9]{32}", identifier)
            or identifier != row["id"]
            or not isinstance(movie_id, int)
            or isinstance(movie_id, bool)
            or movie_id <= 0
            or movie_id != row["movie_id"]
            or state != row["state"]
            or state not in PREPARATION_STATES
        ):
            raise ValueError("Invalid checkpoint identity")
        report = record.get("report")
        report = report if isinstance(report, dict) else {}
        sources = _count_list(report.get("sources", []))
        retrieval = 0
        batches = report.get("batches", [])
        if isinstance(batches, list) and len(batches) <= 50:
            for batch in batches:
                if isinstance(batch, dict):
                    retrieval += _count_list(batch.get("evidence", []), maximum=500)
        degraded = report.get("degraded") is True
        updated_at = _timestamp(record.get("updated_at"))
        summary = LabRunSummary(
            id=f"prep_{identifier}",
            movie_id=movie_id,
            title=_safe_title(self.title_lookup, movie_id),
            workflow="preparation",
            state=state,
            updated_at=updated_at,
            duration_seconds=None,
            source_count=sources,
            retrieval_count=retrieval,
            degraded=degraded,
            warnings=[],
        )
        detail = LabRunDetail(**summary.model_dump(), stages=self._preparation_stages(record))
        return summary, detail

    @staticmethod
    def _preparation_stages(record):
        names = ["source", "retrieving", "generating", "reviewing", "finished"]
        messages = {
            "source": "Load registered movie sources.",
            "retrieving": "Select purpose-scoped evidence.",
            "generating": "Generate bounded candidate content.",
            "reviewing": "Apply deterministic and model-assisted reviews.",
            "finished": "Preserve the terminal checkpoint.",
        }
        phase = record.get("phase")
        current = names.index(phase) if phase in names else 0
        terminal = record.get("state") not in {"queued", "running"}
        failed = record.get("state") in {"failed", "cancelled", "interrupted", "incomplete"}
        stages = []
        for index, name in enumerate(names):
            if index < current or terminal and index <= current:
                status = "attention" if failed and index == current else "completed"
            elif index == current and record.get("state") == "running":
                status = "running"
            else:
                status = "pending"
            stages.append(LabRunStage(name=name, status=status, message=messages[name]))
        return stages

    def _story_records(self, limit, identifier=None):
        if not self.trace_root.exists():
            return [], [_warning("missing_source", "Story-RAG run records are unavailable.")]
        if self.trace_root.is_symlink() or not self.trace_root.is_dir():
            return [], [_warning("invalid_source", "Story-RAG run records are invalid.")]
        try:
            root = self.trace_root.resolve(strict=True)
            candidates = []
            for path in self.trace_root.iterdir():
                match = TRACE_NAME.fullmatch(path.name)
                if not match or identifier and match.group("id") != identifier:
                    continue
                if path.is_symlink():
                    candidates.append((0.0, path, match, False))
                    continue
                resolved = path.resolve(strict=True)
                valid = resolved.is_relative_to(root) and resolved.is_file() and resolved.stat().st_size <= 1_000_000
                candidates.append((resolved.stat().st_mtime if valid else 0.0, resolved, match, valid))
            candidates.sort(key=lambda item: item[0], reverse=True)
        except OSError:
            return [], [_warning("invalid_source", "Story-RAG run records could not be read.")]
        records = []
        warnings = []
        for modified, path, match, valid in candidates[:limit]:
            if not valid:
                warnings.append(_warning("invalid_source", "A story-RAG run record was skipped."))
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                records.append(self._story_record(payload, match, modified))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                warnings.append(_warning("invalid_source", "A story-RAG run record was skipped."))
        return records, warnings

    def _story_record(self, trace, match, modified):
        if not isinstance(trace, dict):
            raise ValueError("Invalid story trace")
        movie_id = trace.get("movie_id")
        if (
            not isinstance(movie_id, int)
            or isinstance(movie_id, bool)
            or movie_id != int(match.group("movie"))
        ):
            raise ValueError("Invalid story trace identity")
        wiki_hits = _count_list(trace.get("wiki_hits", []), maximum=100)
        script_hits = _count_list(trace.get("script_hits", []), maximum=100)
        decisions = _count_list(trace.get("decisions", []), maximum=100)
        index = trace.get("index") if isinstance(trace.get("index"), dict) else {}
        chunks = index.get("chunks", 0)
        if not isinstance(chunks, int) or isinstance(chunks, bool) or chunks < 0:
            chunks = 0
        initial = trace.get("initial_candidate_count", 0)
        if not isinstance(initial, int) or isinstance(initial, bool) or initial < 0:
            initial = 0
        failed = "error" in trace
        summary = LabRunSummary(
            id=f"story_{match.group('id')}",
            movie_id=movie_id,
            title=_safe_title(self.title_lookup, movie_id),
            workflow="story_rag",
            state="failed" if failed else "completed",
            updated_at=datetime.fromtimestamp(modified, timezone.utc),
            duration_seconds=None,
            source_count=int(isinstance(trace.get("wiki_revision"), str))
            + int(isinstance(trace.get("script_revision"), str)),
            retrieval_count=wiki_hits + script_hits,
            degraded=trace.get("degraded") is True,
            warnings=[],
        )
        stages = [
            LabRunStage(name="index", status="completed", count=chunks, message="Reuse or prepare the scoped evidence index."),
            LabRunStage(name="retrieve", status="completed", count=wiki_hits + script_hits, message="Rank movie-scoped plot and optional script passages."),
            LabRunStage(name="generate", status="completed", count=initial, message="Generate bounded story candidates."),
            LabRunStage(name="verify", status="attention" if failed else "completed", count=decisions, message="Apply released-film and support checks."),
        ]
        return summary, LabRunDetail(**summary.model_dump(), stages=stages)
