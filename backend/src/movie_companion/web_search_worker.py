"""A killable DDGS call, without inheriting application credentials or user data."""
import contextlib
import io
import json
import sys

def main():
    data=json.loads(sys.stdin.buffer.read(4000))
    if set(data)!={'query','provider','limit'} or data['provider'] not in ('duckduckgo','startpage') or not 1<=data['limit']<=15:
        raise ValueError('Invalid provider call')
    from ddgs import DDGS
    with contextlib.redirect_stdout(io.StringIO()):
        rows=DDGS(timeout=8).text(data['query'],region='us-en',safesearch='off',max_results=data['limit'],backend=data['provider'])
    results=[]
    for row in rows[:data['limit']]:
        if not isinstance(row,dict):continue
        title,url,snippet=row.get('title'),row.get('href'),row.get('body','')
        if isinstance(title,str) and isinstance(url,str) and isinstance(snippet,str):
            results.append({'title':title[:500],'url':url[:2000],'snippet':snippet[:2000]})
    print(json.dumps(results))

if __name__=='__main__':main()
