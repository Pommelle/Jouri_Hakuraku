from agent.state import AgentState
from agent.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

def red_team_node(state: AgentState) -> dict:
    """Analyze the content from a red team (skeptical/adversarial) perspective."""
    llm = get_llm()
    content = state.get("raw_content", "")
    
    system_prompt = """
    You are the 'Red Team' lead for Jouri Hakuraku.
    Your persona: Highly skeptical, adversarial, and prone to finding flaws in logic, potential for disinformation, or hidden risks.
    Analyze the provided intel and point out why it might be unreliable, what the hidden risks are, or how an adversary could exploit this situation.
    Keep it concise but sharp.
    """
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Analyze this intel: {content}")
    ])
    
    raw_resp = response.content
    if isinstance(raw_resp, list):
        part = raw_resp[0]
        raw_resp = part['text'] if isinstance(part, dict) and 'text' in part else str(part)
    elif hasattr(raw_resp, 'text'):
        raw_resp = raw_resp.text

    intel_type = state.get("intel_type", "mixed")
    print(f"Executing Red Team analysis... [type={intel_type}]")
    return {"red_team_analysis": raw_resp}

def blue_team_node(state: AgentState) -> dict:
    """Analyze the content from a blue team (constructive/defensive) perspective."""
    llm = get_llm()
    content = state.get("raw_content", "")
    
    system_prompt = """
    You are the 'Blue Team' lead for Jouri Hakuraku.
    Your persona: Constructive, defensive-minded, focused on resilience and actionable remediation.
    Analyze the provided intel and suggest defensive measures, potential impact on security posture, and how to mitigate the risks described.
    Keep it professional and actionable.
    """
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Analyze this intel: {content}")
    ])
    
    raw_resp = response.content
    if isinstance(raw_resp, list):
        part = raw_resp[0]
        raw_resp = part['text'] if isinstance(part, dict) and 'text' in part else str(part)
    elif hasattr(raw_resp, 'text'):
        raw_resp = raw_resp.text

    intel_type = state.get("intel_type", "mixed")
    print(f"Executing Blue Team analysis... [type={intel_type}]")
    return {"blue_team_analysis": raw_resp}
