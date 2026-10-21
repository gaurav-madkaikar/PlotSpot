"""Build draft evidence from classified source snapshots, never model labels."""
import re

from .content_proposals import EvidenceOrigin, ProposalEvidence
from .source_sections import matches_purpose
from .wikipedia_source import MOVIE_ARTICLES


def evidence_pools(source):
    """Return complete sentence groups for ranking, with validated provenance."""
    title = MOVIE_ARTICLES.get(source.movie_id)
    revision = re.fullmatch(r'enwiki-([1-9][0-9]*)-sections-v3-body', source.revision)
    from .web_corpus_store import registered_source_match
    acquired=registered_source_match(source)
    if not acquired and (not title or not source.sections or not revision
            or source.source_label != f'English Wikipedia contributors: {title}'
            or source.source_ref != f'https://en.wikipedia.org/w/index.php?oldid={revision[1]}'):
        raise ValueError('A registered section-aware Wikipedia snapshot is required')
    pools = {'story': [], 'background': []}
    for section in source.sections:
        purpose = next((p for p in pools if matches_purpose(section.category, p)), None)
        if purpose is None:
            continue
        # Cast listings mix actor metadata with character/plot descriptions;
        # they are not production anecdotes. Casting-process sections remain.
        if purpose == 'background' and section.title.casefold().strip() == 'cast':
            continue
        body = source.text[section.start:section.end]
        for paragraph in re.finditer(r'[^\n]+', body):
            # Preserve complete sentences and original document offsets. Long
            # sentences are skipped rather than cut into misleading fragments.
            text = paragraph.group()
            if text.strip().startswith(('Main article:', 'See also:', 'Further information:')):
                continue
            boundaries = [0, *[m.end() for m in re.finditer(
                r'[.!?](?:\[[^\]\n]+\])*(?::\s*[0-9–-]+)?\s+(?=[A-Z“"])', text
            )], len(text)]
            start = boundaries[0]
            for end in boundaries[1:]:
                if end - start > 600:
                    start = end
                    continue
                # Pack adjacent sentences up to the context limit.
                next_end = boundaries[boundaries.index(end)+1] if end != boundaries[-1] else None
                if next_end is not None and next_end - start <= 600:
                    continue
                raw = text[start:end]
                stripped = raw.strip()
                offset = section.start + paragraph.start() + start + len(raw) - len(raw.lstrip())
                if len(stripped) >= 20:
                    pools[purpose].append((stripped, EvidenceOrigin(
                        movie_id=source.movie_id, source_id=source.source_id,
                        source_ref=source.source_ref, revision=source.revision,
                        section_title=section.title, section_category=section.category,
                        start=offset, end=offset+len(stripped),
                    )))
                start = end
    # Round-robin production sections so early writing paragraphs cannot consume
    # every background slot. Document order stays intact inside each section.
    groups = {}
    for entry in pools['background']:
        groups.setdefault((entry[1].section_title, entry[1].section_category), []).append(entry)
    pools['background'] = [group[i] for i in range(max(map(len, groups.values()), default=0))
                           for group in groups.values() if i < len(group)]
    return pools


def evidence_batches(source, *, max_batches=8):
    if type(max_batches) is not int or not 1 <= max_batches <= 8:
        raise ValueError('Use one to eight evidence batches')
    pools = evidence_pools(source)
    batches = []
    for index in range(max_batches):
        entries = [(purpose, entry) for purpose, pool in pools.items()
                   for entry in pool[index*2:index*2+2]]
        if not entries:
            break
        batches.append([ProposalEvidence(passage_id=f'P{i+1}', purpose=purpose, text=text, origin=origin)
                        for i, (purpose, (text, origin)) in enumerate(entries)])
    if not batches:
        raise ValueError('No bounded classified passages available')
    return batches


def verify_origins(source, evidence):
    """Recheck persisted context against the actual snapshot before model calls."""
    for passage in evidence:
        origin = passage.origin
        if (origin is None or origin.movie_id != source.movie_id
                or origin.source_id != source.source_id or origin.revision != source.revision
                or origin.source_ref != source.source_ref
                or source.text[origin.start:origin.end] != passage.text
                or not any(s.start <= origin.start < origin.end <= s.end
                           and s.title == origin.section_title and s.category == origin.section_category
                           for s in source.sections)
                or not matches_purpose(origin.section_category, passage.purpose)):
            raise ValueError('Evidence provenance does not match the source snapshot')
