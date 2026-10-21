"""Bounded private collection snapshots; owner identity never comes from JSON."""
from typing import Annotated
import unicodedata
from pydantic import Field,field_validator,model_validator
from .content_proposals import StrictRecord

MovieId=Annotated[int,Field(gt=0,le=2147483647)]

def clean_name(name):return ' '.join(unicodedata.normalize('NFKC',name).split())
def name_key(name):return clean_name(name).casefold()

class BrowserCollection(StrictRecord):
    id:str=Field(min_length=1,max_length=100)
    name:str=Field(min_length=1,max_length=120)
    movieIds:list[MovieId]=Field(max_length=2000)

    @field_validator('name')
    @classmethod
    def name_valid(cls,value):
        name=clean_name(value)
        if not 1<=len(name)<=60 or name_key(name)=='all saved':raise ValueError('Invalid or reserved collection name')
        return name

class PersonalCollection(BrowserCollection):
    id:str=Field(pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')

class ImportRequest(StrictRecord):
    revision:int=Field(ge=0,le=9007199254740991)
    saved:list[MovieId]=Field(max_length=2000)
    watched:list[MovieId]=Field(max_length=2000)
    collections:list[BrowserCollection]=Field(max_length=50)

    @model_validator(mode='after')
    def relationships(self):
        if len(self.saved)!=len(set(self.saved)) or len(self.watched)!=len(set(self.watched)):
            raise ValueError('Movie IDs must be unique')
        ids=[c.id for c in self.collections];names=[name_key(c.name) for c in self.collections]
        if len(ids)!=len(set(ids)) or len(names)!=len(set(names)):raise ValueError('Collection IDs and names must be unique')
        if sum(len(c.movieIds) for c in self.collections)>4000:raise ValueError('Collection membership budget exceeded')
        for c in self.collections:
            if len(c.movieIds)!=len(set(c.movieIds)) or not set(c.movieIds)<=set(self.saved):
                raise ValueError('Custom collections must contain unique saved movies')
        return self

class PersonalSnapshot(ImportRequest):
    collections:list[PersonalCollection]=Field(max_length=50)
