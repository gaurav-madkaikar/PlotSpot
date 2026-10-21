"""Create a read-only advisory narrative-quality audit of the saved quiz bank."""
import argparse
import json
from pathlib import Path
import sqlite3

from movie_companion.preparation_jobs import atomic_json
from movie_companion.quiz_narrative_audit import audit_questions,render_markdown


def load_titles(path: Path) -> dict[int,str]:
    if not path.is_file():return {}
    uri=f'file:{path.resolve()}?mode=ro'
    with sqlite3.connect(uri,uri=True) as db:
        rows=db.execute('SELECT movie_id,payload FROM movies').fetchall()
    return {movie_id:json.loads(raw).get('title',str(movie_id)) for movie_id,raw in rows}


def load_movies(path: Path, *, catalog: Path | None=None) -> list[dict]:
    if not path.is_file():raise ValueError('Content database does not exist')
    uri=f'file:{path.resolve()}?mode=ro'
    with sqlite3.connect(uri,uri=True) as db:
        rows=db.execute('SELECT movie_id,payload FROM collections ORDER BY movie_id').fetchall()
    movies=[];titles=load_titles(catalog) if catalog else {}
    for movie_id,raw in rows:
        payload=json.loads(raw)
        questions=[{'id':item['id'],'question':item['question']}
                   for item in payload['quiz']['items'] if item.get('kind')!='interpretation']
        movies.append({'movie_id':movie_id,'title':titles.get(movie_id,str(movie_id)),'questions':questions})
    return movies


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,default=Path('../data/movie-content.db'))
    parser.add_argument('--catalog',type=Path,default=Path('../data/private/movie-catalog.db'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--markdown',type=Path,required=True)
    args=parser.parse_args()
    if args.output.suffix!='.json' or args.markdown.suffix!='.md':parser.error('Use JSON and Markdown outputs')
    report=audit_questions(load_movies(args.database,catalog=args.catalog))
    atomic_json(args.output,report)
    args.markdown.parent.mkdir(parents=True,exist_ok=True)
    args.markdown.write_text(render_markdown(report))
    print(json.dumps({key:report[key] for key in ('movie_count','question_count','flagged_count','flag_counts')},indent=2))
