# 43. Script ingestion and scene retrieval

## What now works

The backend can fetch and cache reviewed IMSDb scripts for Inception (27205), The Matrix (603), and Interstellar (157336), index them with local Ollama embeddings, and retrieve passages with exact movie, revision, scene and character offsets. Full screenplay text stays under ignored `backend/data/private/screenplays`; vectors stay under ignored `backend/data/content-evidence`.

This is a working retrieval foundation. It is not yet connected to the website's generated quizzes or discussion answers. Those still use the existing Wikipedia-based path. The draft workspace stays where it is; user accounts/admin tools remain deferred.

## The data flow

1. `screenplay_source.load_script` looks for a validated disk snapshot. A cache hit makes no internet request. `--refresh` explicitly fetches the fixed reviewed IMSDb URL again.
2. `parse_script` extracts only the first `<pre>` block. It excludes outside navigation and script/style markup, handles UTF-8 and legacy Windows-1252, and preserves lines while cleaning layout indentation.
3. Header checks enforce the mapped movie title, writer and reviewed version marker. A changed identity/version fails rather than quietly ingesting a different source.
4. `scene_sections` splits at recognizable interior/exterior scene headings. Opening material is retained separately. This is a formatting heuristic, not an understanding of the narrative.
5. `script_documents` groups complete scenes into documents under 80,000 characters. Each scene becomes a plot section; the existing chunker creates overlapping 600-character windows inside it. Windows never cross scenes, although they may split a sentence/dialogue turn.
6. `index_script` checks each exact snapshot in Chroma. Missing documents are embedded in batches of at most 32 using `search_document: ...` and `/api/embed`. A document is stored only after its full vector set is available. If interrupted, a later run reuses complete documents and retries missing ones.
7. `retrieve_script` embeds `search_query: ...`, loads only the requested movie's current snapshot, ranks with cosine similarity and returns up to six passages. Each returned text must equal its recorded span in the normalized script.

## How to run it

From `movie-companion/backend`, with Ollama running and the reviewed `nomic-embed-text:v1.5` model installed:

```sh
PYTHONPATH=src .venv/bin/python scripts/ingest_movie_script.py \
  --movie-id 27205 \
  --query 'What does the spinning top mean to Cobb?' \
  --allow-spoilers \
  --report ../evals/movie-rag/script-inception-inspection.json
```

Omit `--query` to index only. Use `--refresh` to check for changed source text. The CLI verifies the local model artifact, disables redirects, uses fixed hosts and caps the whole operation at 300 seconds by default. Retrieval requires explicit spoiler consent. Reports contain metadata/scene headings/offsets, not screenplay excerpts; actual passages are returned by the Python function.

## Why two persistent caches?

The source cache saves a normalized script and its provenance on disk, avoiding repeat downloads. The vector cache saves its embeddings in Chroma, avoiding repeat document embedding calls. These survive process restarts. A retrieval question still needs one new query embedding; cached document vectors cannot represent a new question.

The vector identity includes movie/source, normalized content, parser revision, chunk parameters and model tag. Changed content therefore creates a different snapshot. Older vectors may remain on disk, but retrieval loads only documents belonging to the selected snapshot. CLI model digest verification also prevents an unnoticed model-artifact replacement under the same tag.

## Why aren't scripts automatically used for quiz answers?

A screenplay may differ from the released movie. The reviewed Interstellar page is a 2008 early draft, The Matrix page is dated 1996, and Inception is labeled a shooting script. None of those labels proves every scene is in the final film.

Every script snapshot and retrieval hit therefore remains unverified against the released film. `eligible_for_quiz` is always false at this stage. Existing Wikipedia-only preparation and citation validation have not been loosened. Scripts also never enter the production/news fact evidence pool.

Next integration: retrieve script passages plus independent released-film plot evidence; accept a scored quiz answer only when that evidence supports the claimed event/answer. Keep ambiguity and draft contradictions out of scored questions. Narrative interpretations and hidden meanings should be presented as interpretations with supporting scenes, not as a single objectively correct answer. Add genuinely unseen movie/source evals for answer support, plausible distractors, repeated questions and source conflicts before enabling this path.

## What do the checks prove?

Synthetic tests check title/version validation, source limits, encoding, HTML handling, exact spans, scene isolation, disk/vector cache reuse, changed revisions, network failures, local-only embedding calls, spoiler consent and incomplete indexing. Real smoke traces confirm local Ollama indexing/retrieval. A broad real query ('Why is inception difficult?') ranked opening/title material second, so raw top-k results still need narrative-only relevance evaluation before generation integration. These checks do not establish semantic accuracy or released-film agreement. Cosine similarity is a ranking signal, not a truth probability.

## Questions and answers

**Is this RAG already?** It implements the retrieval part. Adding retrieved passages to a bounded generation prompt completes a RAG workflow. Here generation is deliberately kept outside the new adapter until source conflicts can be handled.

**Why not send the entire script to the LLM?** It is large, wastes context and makes supporting evidence harder to inspect. Retrieval chooses a few relevant passages with traceable origins. It can still miss necessary context; multi-scene questions need additional retrieval and evaluation.

**Does storing a script mean trusting it?** No. Retrieved text is untrusted data. This adapter never executes it, follows URLs found inside it, or grants it tool permissions. Removing HTML scripts is parser hygiene, not a complete prompt-injection defense for future generation.

**Why aren't these facts?** Screenplays describe story events. Behind-the-scenes facts need production articles, interviews and other corroborated background sources.
