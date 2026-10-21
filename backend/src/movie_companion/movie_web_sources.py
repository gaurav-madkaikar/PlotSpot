"""Full-page identity and purpose checks; search snippets never become evidence."""
from dataclasses import asdict,dataclass
from difflib import SequenceMatcher
import hashlib
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit
from .evidence_store import SourceDocument
from .public_web import SourceRejected,public_url
from .source_sections import SourceSection,heading_category

INJECTION=re.compile(r'(ignore (?:all |the )?(?:previous|prior|system) instructions|system prompt|developer message|(?:send|upload|exfiltrat)\w* (?:the |all )?(?:api key|password|secret|token)|<\|im_start\|>|\[INST\])',re.I)
BACKGROUND=re.compile(r'\b(production|filming|filmed|cinematograph\w*|behind.the.scenes|visual effects|practical effects|composer|soundtrack|costume|casting|screenwriter|shooting|budget|box.office|stunt\w*|interview|director|screenplay|set design|props)\b',re.I)
PRODUCTION_SIGNAL=re.compile(r'\b(production|filming|filmed|cinematograph\w*|behind.the.scenes|visual effects|practical effects|composer|soundtrack|costume|casting|screenwriter|shooting|budget|box.office|stunt\w*|set design|props)\b',re.I)
STORY=re.compile(r'\b(plot|ending|character|story|scene|narrative|protagonist|antagonist|twist|reveals?|discovers?|escapes?|sacrific\w*|rescue\w*)\b',re.I)
def normal(text):return ' '.join(re.findall(r'\w+',text.casefold()))

@dataclass(frozen=True)
class MovieIdentity:
    movie_id:int
    title:str
    year:int|None
    director:str|None=None
    cast:tuple[str,...]=()
    aliases:tuple[str,...]=()
    overview:str=''
    production_companies:tuple[str,...]=()
    original_title:str|None=None
    budget:int|None=None
    revenue:int|None=None
    def __post_init__(self):
        if type(self.movie_id)is not int or self.movie_id<=0 or not isinstance(self.title,str) or not 1<=len(self.title)<=200:raise ValueError('Invalid movie identity')
    @classmethod
    def from_movie(cls,m):
        metadata=m.detail_metadata
        return cls(m.id,m.title,m.year,m.director,tuple(m.cast[:6]),tuple(m.alternative_titles[:8]),
            m.overview,tuple(metadata.production_companies[:8]) if metadata else (),
            metadata.original_title if metadata else None,metadata.budget if metadata else None,
            metadata.revenue if metadata else None)
    @property
    def fingerprint(self):return hashlib.sha256(str(asdict(self)).encode()).hexdigest()
    def query(self,purpose):
        if purpose not in ('story','background'):raise ValueError('Unknown source purpose')
        title=re.sub(r'[^\w .,:!?()-]',' ',self.title)[:160]
        topic='plot story ending analysis' if purpose=='story' else 'behind the scenes production filming trivia interview'
        return f'"{title}" {self.year or ""} film {topic}'


def make_provider_source(movie:MovieIdentity)->SourceDocument:
    """Freeze trusted TMDB fields as citable evidence, independent of web search."""
    if not movie.overview.strip():raise SourceRejected('TMDB overview is unavailable')
    blocks=[]
    def add(text,title,category):
        text=' '.join(text.split()).strip()
        if text:blocks.append((text,title,category))
    add(movie.overview,'Overview','plot')
    if movie.director:add(f'{movie.title} was directed by {movie.director}.','Credits','production')
    if movie.production_companies:
        add(f"The production companies listed for {movie.title} are {', '.join(movie.production_companies)}.",'Production companies','production')
    if movie.original_title and normal(movie.original_title)!=normal(movie.title):
        add(f'The original title listed for {movie.title} is {movie.original_title}.','Original title','production')
    if movie.budget is not None:
        add(f'The reported production budget for {movie.title} is {movie.budget} US dollars.','Budget','production')
    if movie.revenue is not None:
        add(f'The reported worldwide revenue for {movie.title} is {movie.revenue} US dollars.','Revenue','production')
    text='';sections=[]
    for block,title,category in blocks:
        start=len(text);text+=block+'\n\n';sections.append(SourceSection(start,len(text),title,category))
    payload=asdict(movie);revision='tmdb-details-'+hashlib.sha256(str(payload).encode()).hexdigest()+'-v1'
    return SourceDocument(f'tmdb-{movie.movie_id}',movie.movie_id,text,
        f'The Movie Database (TMDB) · {movie.title}',f'https://www.themoviedb.org/movie/{movie.movie_id}',
        revision,'unknown',tuple(sections))

class ArticleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.parts=[];self.buffer=[];self.current=None;self.size=0
    def flush(self):
        text=re.sub(r'\s+',' ',''.join(self.buffer)).strip();self.buffer=[]
        if self.current and text:self.parts.append((self.current,text))
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        hidden=bool(self.stack and self.stack[-1][1]) or tag in {'script','style','nav','footer','aside','form','noscript','svg','button','select'} or 'hidden' in attrs or attrs.get('aria-hidden')=='true' or bool(re.search(r'display\s*:\s*none',attrs.get('style',''),re.I))
        if tag not in ('meta','link','br','img','input','hr','source','wbr'):self.stack.append((tag,hidden))
        if hidden:return
        if tag in ('title','h1','h2','h3','h4','p','blockquote','li'):self.flush();self.current=tag
        elif tag=='br':self.buffer.append('\n')
    def handle_endtag(self,tag):
        if not(self.stack and self.stack[-1][1]) and tag==self.current:self.flush();self.current=None
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break
    def handle_data(self,text):
        if self.stack and self.stack[-1][1]:return
        if self.current:
            self.size+=len(text)
            if self.size>250000:raise SourceRejected('Article extraction budget exceeded')
            self.buffer.append(text)

def extract_article(body,mime):
    if mime=='text/plain':return '',[('p',p.strip()) for p in re.split(r'\n\s*\n',body.decode('utf-8',errors='replace')) if p.strip()]
    parser=ArticleHTML();parser.feed(body.decode('utf-8',errors='replace'));parser.close();parser.flush()
    return ' '.join(t for tag,t in parser.parts if tag in ('title','h1'))[:1500],parser.parts

def identity_matches(movie,heading,body):
    titles=[normal(t) for t in (movie.title,*movie.aliases) if normal(t)]
    head,text=normal(heading),normal(body)
    if not any(' '+t+' ' in ' '+head+' ' for t in titles) or not any(' '+t+' ' in ' '+text+' ' for t in titles):return False
    dated=re.findall(r'\b(18\d{2}|19\d{2}|20\d{2})\s+(?:film|movie)\b',head)
    if movie.year and dated and str(movie.year) not in dated:return False
    if re.search(r'\b(versus|vs|top \d+ films|best movies)\b',head):return False
    year=movie.year and re.search(rf'\b{movie.year}\b',text[:20000])
    director=movie.director and normal(movie.director) in text[:20000]
    cast=sum(normal(n) in text[:20000] for n in movie.cast if n)>=2
    return bool(year or director or cast)

def make_web_source(movie,read,*,purpose):
    if purpose not in ('story','background'):raise SourceRejected('Unknown purpose')
    url=public_url(read.url);host=urlsplit(url).hostname
    if host in ('imsdb.com','en.wikipedia.org','www.imdb.com','imdb.com','reddit.com','www.reddit.com'):raise SourceRejected('Separate source-family policy')
    heading,blocks=extract_article(read.body,read.content_type)
    body='\n'.join(t for tag,t in blocks if tag not in ('title','h1'))
    if len(body)<700 or not identity_matches(movie,heading,body):raise SourceRejected('Wrong or unverified full-page movie identity')
    if INJECTION.search(body):raise SourceRejected('Instruction-like source content')
    category='plot' if purpose=='story' else 'other';title=heading[:180];selected=[]
    for tag,text in blocks:
        if tag in ('title','h1'):continue
        if tag.startswith('h'):
            mapped=heading_category(text);title=text[:180]
            category=mapped if mapped!='other' else 'plot' if STORY.search(text) else 'production' if BACKGROUND.search(text) else 'other'
            continue
        if not 40<=len(text)<=4000 or len(selected)>=80:continue
        background=bool(BACKGROUND.search(text))
        if purpose=='background':
            if not PRODUCTION_SIGNAL.search(text) or category=='plot':continue
            chosen=category if category in ('production','casting','filming','music','effects') else 'production'
        else:
            if category in ('production','casting','filming','music','effects') or (background and not STORY.search(text)):continue
            chosen='plot'
        selected.append((text,title,chosen))
    text='';sections=[]
    for paragraph,title,category in selected:
        if len(text)+len(paragraph)+2>60000:break
        start=len(text);text+=paragraph+'\n\n';sections.append(SourceSection(start,len(text),title,category))
    if len(text)<300:raise SourceRejected('Insufficient purpose-scoped full text')
    key=hashlib.sha256(url.encode()).hexdigest()[:20]
    sha=hashlib.sha256((hashlib.sha256(read.body).hexdigest()+purpose+text).encode()).hexdigest()
    return SourceDocument(f'web-{movie.movie_id}-{purpose[:1]}-{key}',movie.movie_id,text,f'{host} · {heading}'[:200],url,'web-'+sha,'unknown',tuple(sections))

def duplicates(source,others):
    text=normal(source.text)
    return any(source.source_ref==other.source_ref or SequenceMatcher(None,text[:18000],normal(other.text)[:18000],autojunk=False).ratio()>.9 for other in others)
