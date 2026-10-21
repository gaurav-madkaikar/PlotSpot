"""Conservative English sentence spans; quotes always retain original source bytes."""
import re

ABBREVIATION = re.compile(r'\b(?:mr|mrs|ms|dr|prof|sr|jr|st|vs|fig|no|vol|inc|ltd|co|bros)\.$', re.I)
INITIAL = re.compile(r'(?<!\w)[A-Z]\.$')
DOTTED = re.compile(r'(?<!\w)(?:[A-Za-z]\.){2,}$')
REFERENCE = re.compile(r'\[(?:[0-9]+(?:[–,-][0-9]+)*|[a-z])\]')
CLOSERS = '\"\'”’)]'


def complete_sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return exact offsets, skipping headings and incomplete trailing fragments.

    Paragraphs are newline-delimited in the source readers. Abbreviations may
    conservatively merge adjacent sentences; this is not a general NLP parser.
    Character windows must be trimmed using the whole source, not split alone.
    """
    spans = []
    for paragraph in re.finditer(r'[^\n]+', text):
        body = paragraph.group()
        cursor = 0
        for punctuation in re.finditer(r'[.!?]+', body):
            mark = punctuation.group()
            stop = punctuation.end()
            if mark == '.':
                before = body[:stop]
                # Decimal points, titles, personal initials and dotted abbreviations
                # are not trusted as complete-sentence endings.
                if (punctuation.start() > 0 and stop < len(body)
                        and body[punctuation.start()-1].isdigit() and body[stop].isdigit()):
                    continue
                if ABBREVIATION.search(before) or INITIAL.search(before) or DOTTED.search(before):
                    continue
            elif '.' in mark:  # Ellipses do not prove completion.
                continue
            while stop < len(body) and body[stop] in CLOSERS:
                stop += 1
            following = stop
            while match := REFERENCE.match(body, following):
                following = match.end()
            if following < len(body) and not body[following].isspace():
                continue
            start = cursor
            while start < stop and body[start].isspace():
                start += 1
            if start < stop:
                spans.append((paragraph.start()+start, paragraph.start()+stop))
            cursor = following
    return spans
