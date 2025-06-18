from typing import List
from pydantic import BaseModel

class SearchResult(BaseModel):
    content: str
    similarity: float
    metadata: dict

class SearchResults(BaseModel):
    results: List[SearchResult]

class RerankedResult(BaseModel):
    original_index: int
    content: str
    similarity: float
    relevance: float
    metadata: dict

class RerankedResults(BaseModel):
    results: List[RerankedResult] 