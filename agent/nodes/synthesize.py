from agent.state import AgentState
from agent.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
import json

SYSTEM_PROMPTS = {
    "news": """You are the 'Nexus Synthesis AI' for cyber threat intelligence.
Your role is to evaluate the conflicting perspectives of the Red Team (skeptical) and Blue Team (defensive) and provide a high-level executive synthesis.
Focus on: threat indicators, vulnerability severity, attack vectors, affected systems, defensive posture.
Return a JSON:
{
    "title": "A concise, impactful title for the report",
    "final_synthesis": "The detailed synthesis merging both views with an actionable conclusion.",
    "tags": "comma, separated, tags"
}""",
    "chat": """You are the 'Nexus Synthesis AI' for community chat summarization.
Your role is to distill trending topics, emerging concerns, and notable discussions from a batch of chat messages.
Focus on: key themes, consensus vs disagreement, emerging threats discussed, notable opinions.
Return a JSON:
{
    "title": "A concise title summarizing this chat batch topic",
    "final_synthesis": "A summary of the key discussion points and community sentiment.",
    "tags": "comma, separated, tags"
}""",
    "mixed": """You are the 'Nexus Synthesis AI'.
Your role is to evaluate the conflicting perspectives of the Red Team (skeptical) and Blue Team (defensive) and provide a high-level executive synthesis.
Return a JSON:
{
    "title": "A concise, impactful title for the report",
    "final_synthesis": "The detailed synthesis merging both views with an actionable conclusion.",
    "tags": "comma, separated, tags"
}"""
}


def synthesize_node(state: AgentState) -> dict:
    llm = get_llm()

    red = state.get("red_team_analysis", "N/A")
    blue = state.get("blue_team_analysis", "N/A")
    raw = state.get("raw_content", "N/A")
    intel_type = state.get("intel_type", "mixed")

    print("Executing Synthesis node...")

    system_prompt = SYSTEM_PROMPTS.get(intel_type, SYSTEM_PROMPTS["mixed"])

    human_prompt = f"""
    Raw Intel: {raw}

    RED TEAM ANALYSIS:
    {red}

    BLUE TEAM ANALYSIS:
    {blue}

    Synthesize these views into a final executive summary.
    """

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])

    try:
        raw_resp = response.content
        if isinstance(raw_resp, list):
            part = raw_resp[0]
            raw_resp = part['text'] if isinstance(part, dict) and 'text' in part else str(part)
        elif hasattr(raw_resp, 'text'):
            raw_resp = raw_resp.text

        if "```json" in raw_resp:
            raw_resp = raw_resp.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_resp:
            raw_resp = raw_resp.split("```")[1].split("```")[0].strip()

        result = json.loads(raw_resp)

        result["team_assignment"] = "center"
        return result
    except Exception as e:
        print(f"Error parsing synthesis output: {e}\nRaw response: {raw_resp}")
        return {
            "title": "Executive Summary (Synthesis Error)",
            "final_synthesis": response.content if hasattr(response, 'content') else str(response),
            "tags": "error, synthesis",
            "team_assignment": "center"
        }
