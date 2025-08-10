from langgraph.graph import StateGraph, END
from state import ArticleWorkflowState
from agents import (
    researcher_node,
    outline_generator_node,
    full_article_writer_node,
    final_editor_node,
    seo_generator_node
)

def build_workflow():
    g = StateGraph(ArticleWorkflowState)
    g.add_node("researcher", researcher_node)
    g.add_node("outline_generator", outline_generator_node)
    g.add_node("full_article_writer", full_article_writer_node)
    g.add_node("final_editor", final_editor_node)
    g.add_node("seo_generator", seo_generator_node)

    g.set_entry_point("researcher")
    g.add_edge("researcher", "outline_generator")
    g.add_edge("outline_generator", "full_article_writer")
    g.add_edge("full_article_writer", "final_editor")
    g.add_edge("final_editor", "seo_generator")
    g.add_edge("seo_generator", END)
    return g.compile()

if __name__ == "__main__":
    app = build_workflow()
    print("Workflow compiled successfully.")
