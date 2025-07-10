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
    
    # Dane składania artykułu
    assembled_body: Optional[str]  # Treść główna bez wstępu
    introduction: Optional[str]    # Dedykowany, chwytliwy wstęp
    h1_title: Optional[str]        # Nagłówek H1
    raw_article: Optional[str]     # NOWE: Kompletny artykuł przed final editorem
    
    # Dane końcowe
    final_article: str             # Artykuł po final editorze
    raw_research_data: Optional[dict]
