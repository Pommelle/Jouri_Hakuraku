from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from agent.state import AgentState
from agent.nodes.triage import triage_node
from agent.nodes.analyze import red_team_node, blue_team_node
from agent.nodes.synthesize import synthesize_node

def decide_next_step_after_triage(state: AgentState):
    """Conditional edge after triage."""
    if state.get("triage_result"):
        # If it's valuable, run both red and blue team analysis
        return ["red_team", "blue_team"]
    else:
        # If not valuable, end workflow
        return END

def build_graph() -> CompiledStateGraph:
    """Build and compile the LangGraph workflow."""
    
    # 1. Initialize StateGraph
    workflow = StateGraph(AgentState)
    
    # 2. Add nodes
    workflow.add_node("triage", triage_node)
    workflow.add_node("red_team", red_team_node)
    workflow.add_node("blue_team", blue_team_node)
    workflow.add_node("synthesize", synthesize_node)
    
    # 3. Define the edges
    # Standard entry point
    workflow.set_entry_point("triage")
    
    # After triage, conditionally go to analysis or end
    workflow.add_conditional_edges(
        "triage",
        decide_next_step_after_triage,
        {
            "red_team": "red_team",
            "blue_team": "blue_team",
            END: END
        }
    )
    
    # After red & blue team, go to synthesize
    # LangGraph will automatically wait for both parallel branches to finish
    workflow.add_edge("red_team", "synthesize")
    workflow.add_edge("blue_team", "synthesize")
    
    # After synthesis, end
    workflow.add_edge("synthesize", END)
    
    # 4. Compile the graph
    app = workflow.compile()
    
    return app

if __name__ == "__main__":
    app_graph = build_graph()
    print("Graph built successfully.")
    
    # Mock run
    test_state = {"raw_content": "This is a test message from a suspect source.", "source": "test_script"}
    results = app_graph.invoke(test_state)
    print("Execution Result:", results)
