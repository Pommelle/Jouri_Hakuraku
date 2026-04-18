from agent.state import AgentState
from agent.llm_factory import get_llm
from database.crud import (
    insert_daily_summary,
    get_center_intel_by_date,
    delete_center_intel_by_date,
)
from langchain_core.messages import SystemMessage, HumanMessage
import json


def summarize_node(state: AgentState) -> dict:
    """
    Daily rollup: aggregate all center intel from a given date into a single
    daily_summary, then purge the original entries.
    Called by scheduler/daily_rollup.py with date in state['target_date'].
    """
    llm = get_llm()
    target_date = state.get("target_date")
    if not target_date:
        return {"error": "No target_date provided to summarize_node"}

    intel_list = get_center_intel_by_date(target_date)
    if not intel_list:
        print(f"[Summarize] No center intel found for {target_date}, skipping.")
        return {"date": target_date, "summary_id": None, "deleted": 0}

    combined_parts = []
    for item in intel_list:
        line = f"- [{item.get('intel_type','mixed')}] {item.get('title','No title')}: {item.get('synthesis', item.get('summary',''))}"
        combined_parts.append(line)

    combined = "\n".join(combined_parts)

    system_prompt = """You are the 'Nexus Daily Rollup AI'.
Your task is to distill a full day's worth of cyber intelligence into ONE concise daily briefing.
The briefing should cover:
1. Top threats of the day (2-4 bullet points)
2. Key trends observed
3. Any critical items requiring immediate attention
4. Overall threat sentiment for the day

Keep it to 300-500 words. Write in an executive briefing style.
Return a JSON:
{
    "content": "The full daily briefing text (300-500 words)"
}"""

    human_prompt = f"""Intelligence collected on {target_date} ({len(intel_list)} items):

{combined}

Generate the daily briefing."""

    print(f"[Summarize] Processing {len(intel_list)} items for {target_date}...")

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])

        raw = response.content
        if isinstance(raw, list):
            part = raw[0]
            raw = part['text'] if isinstance(part, dict) and 'text' in part else str(part)
        elif hasattr(raw, 'text'):
            raw = raw.text

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        result = json.loads(raw)
        content = result.get("content", raw[:2000])

        source_hints = list(set([i.get('intel_type', 'mixed') for i in intel_list]))
        source_hint = ",".join(source_hints)

        summary_id = insert_daily_summary(
            date=target_date,
            content=content,
            source_hint=source_hint,
            raw_count=len(intel_list)
        )

        deleted = delete_center_intel_by_date(target_date)

        print(f"[Summarize] Summary id={summary_id} for {target_date} ({len(intel_list)} items) | deleted {deleted} raw entries.")
        return {"date": target_date, "summary_id": summary_id, "deleted": deleted, "content": content}

    except Exception as e:
        print(f"[Summarize] Error generating daily summary: {e}")
        return {"date": target_date, "summary_id": None, "error": str(e)}
