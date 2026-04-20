from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from agent.state import AgentState
from agent.nodes.triage import triage_node


def build_graph() -> CompiledStateGraph:
    """Build and compile the LangGraph workflow."""
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("triage", triage_node)
    
    workflow.set_entry_point("triage")
    workflow.add_edge("triage", END)
    
    app = workflow.compile()
    
    return app


if __name__ == "__main__":
    app_graph = build_graph()
    print("Graph built successfully.")
    
    test_state = {"raw_content": "This is a test message.", "source": "test_script"}
    results = app_graph.invoke(test_state)
    print("Execution Result:", results)
