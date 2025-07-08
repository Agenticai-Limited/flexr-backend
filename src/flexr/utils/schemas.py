# schemas.py (Updated Version)
from typing import List, Optional, Union
from pydantic import BaseModel, Field

# --- Input Schema from VectorDB / Reranker ---

class RerankedResult(BaseModel):
    """Represents a single search result after reranking."""
    original_index: int
    content: str
    relevance: float
    metadata: dict

class RerankedResults(BaseModel):
    """The full list of reranked search results passed to the first task."""
    results: List[RerankedResult]

# --- Intermediate Schema for Data Transfer Between Agents ---

class MediaInfo(BaseModel):
    """Structured information for a single media item, now with an explicit type."""
    media_type: str = Field(description="Type of media, must be either 'IMAGE' or 'TABLE'.")
    content: str = Field(description="The core content. For 'IMAGE', this is the URL. For 'TABLE', this is the full Markdown table string.")
    description: str = Field(description="The alt-text for an 'IMAGE' or a summary/caption for a 'TABLE'.")

class Step(BaseModel):
    """A single instructional step with optional associated media."""
    step_description: str = Field(description="The text of the instructional step.")
    media_info: Optional[MediaInfo] = Field(description="Associated media, if any.", default=None)

class SupplementaryNote(BaseModel):
    """A single supplementary note, which could be customer-specific."""
    note_description: str = Field(description="The text of the supplementary note.")
    media_info: Optional[MediaInfo] = Field(description="Associated media for this note, if any.", default=None)

class SupplementarySource(BaseModel):
    """A collection of notes from a single supplementary source document."""
    source_page: str = Field(description="The page_title of the supplementary document.")
    notes: List[SupplementaryNote]

class StructuredPlan(BaseModel):
    """The structured plan created by the first agent."""
    primary_steps: List[Step]
    supplementary_notes: List[SupplementarySource] = []
    all_sources: List[dict] = Field(description="A list of all unique metadata dictionaries for the sources block.")


class AgentOutput(BaseModel):
    """The output of the structuring task."""
    plan: Optional[StructuredPlan] = Field(default=None)
    final_answer: Optional[str] = Field(default=None)