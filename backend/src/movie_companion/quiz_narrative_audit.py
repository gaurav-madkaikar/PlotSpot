"""Non-destructive advisory audit of saved quiz-question wording."""
from datetime import datetime, timezone

from .quiz_narrative_quality import advisory_surface_flags

POLICY='published-quiz-narrative-advisory-v1'


def audit_questions(movies: list[dict]) -> dict:
    if not isinstance(movies,list) or not movies:
        raise ValueError('At least one movie collection is required')
    seen=set();rows=[]
    for movie in movies:
        if (not isinstance(movie,dict) or type(movie.get('movie_id')) is not int
                or movie['movie_id'] in seen or not isinstance(movie.get('questions'),list)):
            raise ValueError('Invalid movie audit input')
        seen.add(movie['movie_id'])
        for item in movie['questions']:
            if (not isinstance(item,dict) or not isinstance(item.get('id'),str)
                    or not isinstance(item.get('question'),str)):
                raise ValueError('Invalid saved question')
            flags=advisory_surface_flags(item['question'])
            rows.append({'movie_id':movie['movie_id'],'title':movie.get('title',str(movie['movie_id'])),
                         'question_id':item['id'],'question':item['question'],
                         'flags':flags,'review_priority':'review' if flags else 'unflagged'})
    flagged=[row for row in rows if row['flags']]
    counts={}
    for row in flagged:
        for flag in row['flags']:counts[flag]=counts.get(flag,0)+1
    return {'generated_at':datetime.now(timezone.utc).isoformat(),'policy':POLICY,
        'status':'advisory','movie_count':len(movies),'question_count':len(rows),
        'flagged_count':len(flagged),'flag_counts':dict(sorted(counts.items())),
        'items':rows,'limitations':[
            'A wording flag requests semantic review; it does not prove that a question is low value.',
            'An unflagged question is not automatically meaningful, accurate or publication-ready.',
            'This audit cannot delete, replace or publish saved content.',
        ]}


def render_markdown(report: dict) -> str:
    rows=['# Published quiz narrative-quality audit','',
          f"Generated: {report['generated_at']}",'',
          '**Status: ADVISORY**','',
          f"- Movies: {report['movie_count']}",f"- Scored questions: {report['question_count']}",
          f"- Questions flagged for semantic review: {report['flagged_count']}",'',
          '## Review queue','',
          '| Movie | Question | Surface flags |','|---|---|---|']
    for item in report['items']:
        if item['flags']:
            question=item['question'].replace('|','\\|')
            rows.append(f"| {item['title']} | {question} | {', '.join(item['flags'])} |")
    rows.extend(['','## Limits',''])
    rows.extend(f'- {item}' for item in report['limitations'])
    rows.append('')
    return '\n'.join(rows)
