from typing import List
from pydantic import BaseModel

class SearchResult(BaseModel):
    content: str
    metadata: dict

class SearchResults(BaseModel):
    results: List[SearchResult]

class RerankedResult(BaseModel):
    original_index: int
    content: str
    relevance: float
    metadata: dict

class RerankedResults(BaseModel):
    results: List[RerankedResult] 