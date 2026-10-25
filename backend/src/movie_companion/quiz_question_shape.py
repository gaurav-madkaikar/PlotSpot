"""Small explicit language rules; unknown forms still need semantic review."""
import re

OBJECT_TYPES = {
    'spacecraft': {'spacecraft','spaceship','spaceships','vessel'},
    'clothing': {'uniform','uniforms','jacket','coat','clothes'},
    'road_vehicle': {'car','cars','automobile','automobiles','truck'},
}
NUMBERS = set('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million'.split())
COLORS = set('red blue green black white yellow orange purple pink brown grey gray silver gold'.split())
DISJOINT_PROPERTIES = {frozenset(pair) for pair in (
    ('age','profession'),('age','actor'),('age','location'),
    ('color','age'),('color','profession'),('color','actor'),('color','location'),
    ('actor','location'),('profession','location'))}


def relation(question):
    text=question.casefold().strip()
    if re.match(r'^how old\b',text):return 'age'
    if re.match(r'^how many\b',text):return 'count'
    if re.match(r'^what (?:colou?r|shade)\b',text):return 'color'
    if text.startswith('why ') or re.search(r'\b(?:reason|motivat\w*|future need|need explains)\b',text):return 'reason'
    if text.startswith('what ') and re.search(r'\b(?:profession|occupation|expertise)\b',text):return 'profession'
    if text.startswith('where '):return 'location'
    if re.match(r'^who (?!is\b|was\b|are\b|were\b)',text):return 'actor'
    if re.match(r'^how (?:does|do|did)\b',text):return 'method'
    return None


def object_type(question):
    words=set(re.findall(r'\w+',question.casefold()))
    matches=[kind for kind,tokens in OBJECT_TYPES.items() if words & tokens]
    return matches[0] if len(matches)==1 else None


def distinctly_tested(left,right):
    """Sufficient narrow distinctions, never a universal topic comparator.

    Different explicit properties are distinct; color comparisons can distinguish
    disjoint object types. Unknown/alias scopes cannot force novelty acceptance.
    """
    a,b=relation(left),relation(right)
    if a is None or b is None:return False
    if a!=b:return frozenset((a,b)) in DISJOINT_PROPERTIES
    if a=='color':
        first,second=object_type(left),object_type(right)
        return first is not None and second is not None and first!=second
    return False


def recognized_wording(question,answer):
    """Recognize a few ordinary stems/answer types without asking an LLM.

    Necessary content/answer checks still run elsewhere. Bare pronouns and other
    syntax are left to the wording reviewer; this is not a grammar proof.
    """
    text=question.strip()
    words=re.findall(r'\w+',answer.casefold())
    if not text.endswith('?') or not words:return False
    if re.search(r'\b(?:he|she|they|it)\b',text.casefold().split(' when ')[0]):return False
    kind=relation(text)
    if kind in ('age','count'):
        return bool(re.match(r'^how (?:old|many)\b.+\?$',text,re.I)) and (
            words[0].isdigit() or words[0] in NUMBERS)
    if kind=='color':return bool(re.match(r'^what (?:colou?r|shade) (?:is|are) .+\?$',text,re.I)) and words[0] in COLORS
    if kind=='location':return bool(re.match(r'^where (?:is|are|was|were) .+\?$',text,re.I)) and words[0] in {'in','on','at','below','above','inside','outside','near','under','between'}
    if kind=='reason':return bool(re.match(r'^why (?:does|do|did|is|are|was|were) .+\?$',text,re.I))
    if kind=='method':return bool(re.match(r'^how (?:does|do|did) .+\?$',text,re.I)) and words[0] in {'by','using','through'}
    return False
