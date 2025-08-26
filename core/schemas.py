from pydantic import BaseModel
from typing import List

class Citation(BaseModel):
    source: str
    page: int = 1
    snippet: str

class AnswerJSON(BaseModel):
    query: str
    answer: str
    citations: List[Citation]
