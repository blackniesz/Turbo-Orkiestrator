# src/state.py
from typing import TypedDict, List, Optional, Dict, Any
from langchain_core.runnables import Runnable

class OutlineItem(TypedDict, total=False):
    h2: str
    h3: List[str]

class ArticleWorkflowState(TypedDict, total=False):
    # Dane wejściowe
    keyword: str
    persona: dict
    llm: Runnable

    # Research
    research_corpus: str
    research_summary: str
    raw_research_data: Dict[str, Any]

    # Konspekt
    outline: List[OutlineItem]

    # Artykuł
    raw_article: str
    h1_title: str
    final_article: str

    # SEO
    meta_title: str
    meta_description: str
