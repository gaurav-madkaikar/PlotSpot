"""Summarize compatible local critic development and held-out reports."""
import argparse
import json
from pathlib import Path

from movie_companion.content_quality_comparison import compare_quality
from prepare_content_drafts import write_checkpoint

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--revised',type=Path,required=True)
    parser.add_argument('--held-out',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    inputs=[args.baseline,args.revised,args.held_out]
    if args.output.suffix!='.json' or args.output.resolve() in {p.resolve() for p in inputs}:
        raise SystemExit('Use a separate JSON comparison output')
    report=compare_quality(*(json.loads(p.read_text()) for p in inputs))
    write_checkpoint(args.output,report)
    print(json.dumps({key:report[key] for key in ('baseline','revised','held_out')},indent=2))
