import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from agent.nodes.summarize import summarize_node


def run_daily_rollup(target_date: str = None):
    """
    Roll up yesterday's center intel into a daily summary.
    Calls summarize_node directly (no LangGraph needed, just the single node).
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    print(f"[DailyRollup] Starting rollup for {target_date}...")

    state = {"target_date": target_date}
    result = summarize_node(state)

    if result.get("summary_id"):
        print(f"[DailyRollup] SUCCESS: summary_id={result['summary_id']}, deleted={result['deleted']} entries.")
    else:
        print(f"[DailyRollup] No summary generated (no intel or error: {result.get('error', 'unknown')}).")

    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Daily intelligence rollup")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD (defaults to yesterday)")
    args = parser.parse_args()
    run_daily_rollup(args.date)
