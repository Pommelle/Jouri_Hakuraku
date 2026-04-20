"""
Weekly/Overall rollup node.

Every day after the daily rollup completes:
  1. Read the last 7 days of daily_summary (red + blue).
  2. Read the existing overall_summary (if any).
  3. Call DAILY_ROLLUP_LLM to synthesize: [existing_overall + today's red + today's blue]
     → new overall summary.
  4. Delete daily_summary rows older than 7 days (they've been absorbed).

The overall summary is a single row in `overall_summary` table, kept up to date
by this node on every run.
"""
from agent.state import AgentState
from agent.llm_factory import get_daily_rollup_llm
from database.crud import (
    get_daily_summaries,
    get_overall_summary,
    upsert_overall_summary,
    delete_daily_summaries_before,
)
from langchain_core.messages import SystemMessage, HumanMessage
import json
from datetime import datetime, timedelta


WINDOW_DAYS = 7


def weekly_rollup_node(state: AgentState) -> dict:
    """
    Main entry point. Call once per day, after the daily red+blue rollup is done.

    Reads last WINDOW_DAYS daily summaries, merges them with the existing overall
    summary, and writes back an updated overall. Old summaries (older than
    WINDOW_DAYS) are deleted.

    Returns a dict with summary_id, deleted_count, and date range processed.
    """
    llm = get_daily_rollup_llm()

    today = datetime.now().strftime('%Y-%m-%d')
    cutoff = (datetime.now() - timedelta(days=WINDOW_DAYS)).strftime('%Y-%m-%d')

    # Fetch last 7 days of red + blue summaries
    red_summaries = get_daily_summaries(days=WINDOW_DAYS, team="red")
    blue_summaries = get_daily_summaries(days=WINDOW_DAYS, team="blue")

    if not red_summaries and not blue_summaries:
        print(f"[WeeklyRollup] No daily summaries found, skipping.")
        return {"date": today, "summary_id": None, "deleted": 0, "skipped": True}

    # Build the per-day red+blue pairs
    all_dates = sorted(set(
        [s['date'] for s in red_summaries] + [s['date'] for s in blue_summaries]
    ), reverse=True)

    daily_blocks = []
    for date_str in all_dates:
        red_entry = next((s for s in red_summaries if s['date'] == date_str), None)
        blue_entry = next((s for s in blue_summaries if s['date'] == date_str), None)
        daily_blocks.append(_build_daily_block(date_str, red_entry, blue_entry))

    daily_intel_block = "\n\n".join(daily_blocks)

    # Fetch existing overall summary
    existing = get_overall_summary()
    existing_content = existing['content'] if existing else None

    # Call LLM
    result = _do_rollup(daily_intel_block, existing_content, llm, today)

    if result.get("summary_id"):
        deleted = delete_daily_summaries_before(cutoff)
        print(f"[WeeklyRollup] overall_summary id={result['summary_id']} written, "
              f"{deleted} old daily summaries deleted (before {cutoff}).")
        return {
            "date": today,
            "summary_id": result["summary_id"],
            "deleted": deleted,
            "days_covered": len(all_dates),
            "skipped": False,
        }
    else:
        print(f"[WeeklyRollup] LLM call failed: {result.get('error')}")
        return {"date": today, "summary_id": None, "error": result.get("error"), "deleted": 0}


def _build_daily_block(date_str: str, red_entry: dict | None, blue_entry: dict | None) -> str:
    """Format one day's red+blue summaries into a readable block."""
    lines = [f"=== {date_str} ==="]
    if red_entry:
        lines.append(f"[RED TEAM]\n{red_entry['content']}")
    else:
        lines.append("[RED TEAM] (no summary)")
    if blue_entry:
        lines.append(f"[BLUE TEAM]\n{blue_entry['content']}")
    else:
        lines.append("[BLUE TEAM] (no summary)")
    return "\n".join(lines)


def _do_rollup(daily_intel_block: str, existing_overall: str | None, llm, target_date: str) -> dict:
    """
    Call the rollup LLM to synthesize existing_overall + the last 7 days
    of red+blue summaries into an updated overall summary.
    """
    existing_section = (
        f"## Existing Overall Summary (carry forward important context)\n"
        f"{existing_overall or '(no prior overall summary — start from scratch)'}\n\n"
    ) if existing_overall else (
        "## Existing Overall Summary\n(no prior overall summary — start from scratch)\n\n"
    )

    system_prompt = f"""You are the 'Nexus Overall Analyst'.
Your task is to maintain a running intelligence overview that synthesizes multiple days of
Red Team and Blue Team daily briefings into a single coherent narrative.

The overall summary you produce should:
1. **Track key threads across days** — identify themes that persist, escalate, or evolve.
2. **Highlight turning points** — flag moments where the situation shifted meaningfully.
3. **Preserve nuance** — carry forward Red skepticism alongside Blue stabilizing signals.
4. **Be concise but dense** — this is the executive overview. No repetition of individual
   daily reports; instead, synthesize them into a unified picture.
5. **Mark the cutoff date** — note "As of [last date in this window]" to show temporal scope.

Format: plain text with section headers. No JSON. Aim for 400-700 words.
The existing overall summary (if present) is prior context — incorporate it but don't just append;
synthesize, revise, and update.

{existing_section}
Reference confidence anchors for known sources (do not exceed these)."""

    human_prompt = f"""## Daily Intelligence (last {WINDOW_DAYS} days — Red + Blue)

{daily_intel_block}

Synthesize the above into an updated overall summary. Preserve continuity with the existing
context above; revise and refine rather than just append."""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        raw = _extract_text(response)

        # Count total raw items roughly (sum raw_count from daily blocks)
        raw_total = 0

        summary_id = upsert_overall_summary(content=raw, source_hint="red+blue rolling window", raw_count=raw_total)
        return {"date": target_date, "summary_id": summary_id, "content": raw}

    except Exception as e:
        print(f"[WeeklyRollup] Error: {e}")
        return {"date": target_date, "summary_id": None, "error": str(e)}


def _extract_text(response) -> str:
    """Pull plain text out of an LLM response."""
    raw = response.content
    if isinstance(raw, dict):
        raw = raw.get("text", "") or str(raw)
    elif isinstance(raw, list):
        part = raw[0]
        raw = part['text'] if isinstance(part, dict) and 'text' in part else str(part)
    elif hasattr(raw, 'text'):
        raw = raw.text
    return raw.strip()
