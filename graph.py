from langgraph.graph import StateGraph, END
from state import ArticleWorkflowState
from agents import (
    researcher_node,
    voice_analyst_node,
    outline_generator_node,
    outline_critic_node,
    section_writer_node,
    section_critic_node,
    assembler_node,
    final_editor_node,
    should_continue_outlining,
    should_continue_writing
)

def build_workflow():
    workflow = StateGraph(ArticleWorkflowState)

    workflow.add_node("researcher", researcher_node)
    workflow.add_node("voice_analyst", voice_analyst_node)
    workflow.add_node("outline_generator", outline_generator_node)
    workflow.add_node("outline_critic", outline_critic_node)
    workflow.add_node("section_writer", section_writer_node)
    workflow.add_node("section_critic", section_critic_node)
    workflow.add_node("assembler", assembler_node)
    workflow.add_node("final_editor", final_editor_node)

    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "voice_analyst")
    workflow.add_edge("voice_analyst", "outline_generator")

    workflow.add_edge("outline_generator", "outline_critic")
    workflow.add_conditional_edges(
        "outline_critic",
        should_continue_outlining,
        {
            "revise_outline": "outline_generator",
            "start_writing": "section_writer"
        }
    )

    workflow.add_edge("section_writer", "section_critic")
    workflow.add_conditional_edges("section_critic", should_continue_writing, {"write_section": "section_writer", "assemble_article": "assembler"})

    workflow.add_edge("assembler", "final_editor")
    workflow.add_edge("final_editor", END)

    return workflow.compile()

if __name__ == "__main__":
    # Example usage (for testing purposes)
    app = build_workflow()
    print("Workflow compiled successfully.")
    # You can add more testing logic here if needed


