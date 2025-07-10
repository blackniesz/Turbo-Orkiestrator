from typing import TypedDict, List, Optional
from langchain_core.runnables import Runnable

class Section(TypedDict):
    title: str
    draft: Optional[str]
    critique: Optional[str]
    is_approved: bool
    revision_count: int

class ArticleWorkflowState(TypedDict):
    # Dane wejściowe
    keyword: str
    website_url: str
    persona: dict
    llm: Runnable
    
    # Dane generowane w trakcie procesu
    research_summary: str
    tone_of_voice_guidelines: str
    outline: List[Section]
    outline_critique: Optional[str]
    outline_revision_count: int
    
    # Nowe pola dla lepszej kontroli nad treścią
    assembled_body: Optional[str]  # Treść główna bez wstępu
    introduction: Optional[str]    # Dedykowany, chwytliwy wstęp
    
    # Dane końcowe
    final_article: str
    raw_research_data: Optional[dict]
