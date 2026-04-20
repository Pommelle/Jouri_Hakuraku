"""
Weekly rollup scheduler.

Calls weekly_rollup_node once per day (after the daily red+blue rollup completes).
"""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from agent.nodes.weekly_rollup import weekly_rollup_node


def run_weekly_rollup():
    """
    Run the weekly/overall rollup:
      1. Read last 7 days of daily summaries (red + blue).
      2. Merge with existing overall summary → updated overall.
      3. Delete daily summaries older than 7 days.

    This should be called AFTER run_daily_rollup each day.
    """
    print("[WeeklyRollup] Starting weekly/overall rollup...")
    result = weekly_rollup_node({})
    if result.get("summary_id"):
        print(f"[WeeklyRollup] SUCCESS: overall_summary id={result['summary_id']}, "
              f"deleted={result.get('deleted', 0)} old rows, "
              f"days_covered={result.get('days_covered', '?')}")
    elif result.get("skipped"):
        print("[WeeklyRollup] No daily summaries found, skipped.")
    else:
        print(f"[WeeklyRollup] FAILED: {result.get('error', 'unknown error')}")
    return result


if __name__ == "__main__":
    run_weekly_rollup()
