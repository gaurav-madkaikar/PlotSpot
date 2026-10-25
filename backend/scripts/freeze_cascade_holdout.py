"""Freeze the v2 cascade holdout from already reviewed saved movie content."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from movie_companion.evidence_store import SourceDocument, snapshot_key
from movie_companion.movie_questions import MovieQuestionService
from movie_companion.orchestration_benchmark import CASCADE_POLICY, BenchmarkDataset
from movie_companion.source_sections import source_chunks


ROOT = Path(__file__).resolve().parents[2]
MOVIES = {
    129: ("Spirited Away", [("parents-transformed", [["pigs", "pig"]]), ("boiler-worker", [["Kamaji"]])]),
    155: ("The Dark Knight", [("last-bank-robber", [["Joker"]]), ("bruces-exit-plan", [["retire as Batman", "retire"]])]),
    603: ("The Matrix", [("neo-name", [["Thomas Anderson"]]), ("pill-choice", [["red pill"]])]),
    27205: ("Inception", [("fischer-plan", [["dissolve"], ["father's company", "father’s company", "father's conglomerate"]]), ("cobb-reward", [["home", "children"]])]),
    37165: ("The Truman Show", [("seahaven-secret", [["soundstage"]]), ("world-controller", [["Christof"]])]),
    120467: ("The Grand Budapest Hotel", [("zero-first-job", [["lobby boy"]]), ("famous-bequest", [["Boy with Apple"]])]),
    157336: ("Interstellar", [("dust-coordinates", [["NASA facility"]]), ("mann-motive", [["rescued", "rescue"]])]),
    329865: ("Arrival", [("louise-profession", [["linguist", "linguistics"]]), ("ship-count", [["Twelve", "12"]])]),
    438631: ("Dune", [("new-fief", [["Arrakis"]]), ("spice-purpose", [["interstellar travel"]])]),
    496243: ("Parasite", [("scholars-gift", [["scholar's rock", "scholar’s rock"]]), ("first-position", [["English tutor"]])]),
    546554: ("Knives Out", [("marta-role", [["nurse"]]), ("lie-reaction", [["vomit", "vomits"]])]),
}
MISSING = [
    (129, "private-voice-actor-phone", "What is the private mobile number of Chihiro's voice actor?"),
    (155, "unpublished-director-notes", "What did Christopher Nolan write in his unpublished private notes about the ending?"),
    (603, "private-bank-account", "What is Keanu Reeves's private bank account number?"),
    (27205, "viewer-watch-history", "On what date did the current viewer first watch Inception?"),
    (37165, "private-actor-email", "What is Jim Carrey's private email address?"),
    (120467, "studio-payroll-record", "What exact private payroll amount was paid to every background actor?"),
    (329865, "unreleased-sequel-ending", "How does the unreleased Arrival sequel end?"),
    (438631, "private-medical-record", "What confidential medical diagnosis appears in Timothée Chalamet's private records?"),
]


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def supporting_ids(source, excerpt, snapshot):
    start = source.text.find(excerpt)
    if start < 0:
        raise ValueError("Reviewed excerpt is absent from the frozen source")
    end = start + len(excerpt)
    return [f"{snapshot[:32]}_{index:03}" for index, chunk in enumerate(
        source_chunks(source, **MovieQuestionService.chunk_settings)
    ) if min(end, chunk.end) > max(start, chunk.start)]


def main():
    output = ROOT / "evals/movie-rag/orchestration-benchmark/holdout-v2-cascade.json"
    if output.exists():
        raise ValueError("The cascade holdout is already frozen")
    connection = sqlite3.connect(ROOT / "data/movie-content.db")
    source_models, cases = [], []
    for movie_id, (title, selections) in MOVIES.items():
        path = ROOT / f".cache/expanded20/sources/{movie_id}.json"
        raw = path.read_bytes()
        source = SourceDocument(**json.loads(raw))
        snapshot = snapshot_key(source, model=MovieQuestionService.embedding_model,
                                **MovieQuestionService.chunk_settings)
        source_models.append({"movie_id": movie_id,
            "path": f".cache/expanded20/sources/{movie_id}.json",
            "sha256": sha256(raw).hexdigest(), "revision": source.revision, "snapshot": snapshot})
        row = connection.execute("SELECT payload FROM collections WHERE movie_id = ?", (movie_id,)).fetchone()
        if row is None:
            raise ValueError(f"Movie {movie_id} has no reviewed published bank")
        items = {item["id"]: item for item in json.loads(row[0])["quiz"]["items"]}
        for item_id, phrase_groups in selections:
            item = items[item_id]
            citations = [citation for citation in item["citations"]
                         if citation["source_label"].startswith("English Wikipedia")
                         and citation["excerpt"] in source.text]
            if not citations:
                raise ValueError(f"{movie_id}:{item_id} lacks exact frozen Wikipedia support")
            excerpt = citations[0]["excerpt"]
            cases.append({"id": f"{slug(title)}-{item_id}", "movie_id": movie_id, "title": title,
                "question": item["question"], "expected_status": "answered",
                "reference_answer": item["options"][item["correct_index"]],
                "reference_excerpt": excerpt,
                "relevant_passage_ids": supporting_ids(source, excerpt, snapshot),
                "required_phrase_groups": phrase_groups})
    for movie_id, case_id, question in MISSING:
        cases.append({"id": case_id, "movie_id": movie_id, "title": MOVIES[movie_id][0],
            "question": question, "expected_status": "insufficient_evidence",
            "reference_answer": None, "reference_excerpt": None,
            "relevant_passage_ids": [], "required_phrase_groups": []})
    data = {"policy": CASCADE_POLICY, "created_at": datetime.now(timezone.utc).isoformat(),
        "split": "holdout",
        "label_origin": "Objective answer labels and exact spans were copied from human-reviewed published quiz items before the direct-first fallback was implemented or run. Missing-evidence controls were authored before execution. These are reviewed project labels, not new independent human annotations.",
        "embedding_model": MovieQuestionService.embedding_model,
        "chat_model": MovieQuestionService.chat_model,
        "chunk_settings": MovieQuestionService.chunk_settings,
        "sources": source_models, "cases": cases}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(BenchmarkDataset.model_validate(data).model_dump(), indent=2,
                                 ensure_ascii=False) + "\n")
    print(f"Frozen {len(cases)} cases across {len(MOVIES)} unseen answerable films: {output}")


if __name__ == "__main__":
    main()
