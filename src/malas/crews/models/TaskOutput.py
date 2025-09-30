from typing import Dict, List, Optional
from pydantic import BaseModel


class Subbab(BaseModel):
    sections: List[str] = []

class Outline(BaseModel):
    subbabs : Dict[str, Subbab] = {}


class ReferenceItem(BaseModel):
    title: str
    authors: List[str]
    year: int
    link: Optional[str] = None
class References(BaseModel):
    references: List[ReferenceItem] = []
