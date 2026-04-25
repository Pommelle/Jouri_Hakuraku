"""
Daily rollup scheduler.

Each function is a thin orchestrator — all the real work happens inside the
corresponding node in agent.nodes.summarize.
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from agent.nodes.summarize import (
    chunk_summary_node,
    summarize_node,
    summarize_memory_node,
    memory_chunks_summary_node,
)


def run_memory_chunks():
    """
    Drain ALL unsummarized sidebar memories into chunk summaries.
    All looping is handled inside memory_chunks_summary_node.
    Returns {"chunks": N, "chunk_ids": [...]}.
    """
    print("[DailyRollup] Starting memory chunk processing...")
    result = memory_chunks_summary_node({})
    chunks = result.get("chunks", 0)
    if result.get("chunk_ids"):
        print(f"[DailyRollup] Memory chunk processing done: {chunks} chunk(s), IDs={result['chunk_ids']}")
    elif result.get("error"):
        print(f"[DailyRollup] Memory chunk processing failed: {result['error']}")
    else:
        print("[DailyRollup] No unsummarized memories found.")
    return result


def run_chunk_summaries(target_date: str = None, team: str = "center"):
    """
    Drain ALL intel for the given date and team as chunk summaries.
    All looping is handled inside chunk_summary_node.
    Returns {"chunks": N, "chunk_ids": [...]}.
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    print(f"[DailyRollup] Starting chunk summaries for {target_date} (team={team})...")
    result = chunk_summary_node({"target_date": target_date}, team=team)
    chunks = result.get("chunks", 0)
    if result.get("chunk_ids"):
        print(f"[DailyRollup] Chunk summaries done for {target_date} (team={team}): "
              f"{chunks} chunk(s), IDs={result['chunk_ids']}")
    elif result.get("error"):
        print(f"[DailyRollup] Chunk summaries failed for {target_date} (team={team}): "
              f"{result['error']}")
    else:
        print(f"[DailyRollup] No {team} items for {target_date}.")
    return result


def run_memory_rollup():
    """
    Roll up all existing memory chunks into a single daily_summary (date='memory').
    """
    print("[DailyRollup] Starting memory rollup...")
    result = summarize_memory_node()
    if result.get("summary_id"):
        print(f"[DailyRollup] SUCCESS (memory): summary_id={result['summary_id']}, "
              f"chars={len(result.get('content', ''))}")
    else:
        print(f"[DailyRollup] Memory rollup skipped: {result.get('error', 'no chunks')}")
    return result


def run_daily_rollup(target_date: str = None, teams=None):
    """
    Full daily rollup pipeline:
      1. Drain ALL intel (regardless of team) into chunk summaries.
      2. Run joint red+blue rollup — both teams read the same chunks,
         each generates its own structured briefing (Red Dossier / Blue Brief).
      3. Run memory chunk drain + rollup separately.

    Returns a dict mapping team -> summarize result (memory included under "memory" key).
    """
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if teams is None:
        teams = ["red", "blue"]

    results = {}

    # ── Joint chunk + rollup (red + blue share the same intel view) ──────────
    print(f"\n[DailyRollup] ===== {target_date} | DRAINING ALL TEAMS =====")
    for team in teams:
        run_chunk_summaries(target_date, team=team)

    print(f"\n[DailyRollup] ===== {target_date} | JOINT RED+BLUE ROLLUP =====")
    joint_result = summarize_node({"target_date": target_date}, team="joint")

    results["red"] = {
        "summary_id": joint_result.get("red_summary_id"),
        "content": joint_result.get("red_content"),
        "deleted": joint_result.get("deleted", 0),
    }
    results["blue"] = {
        "summary_id": joint_result.get("blue_summary_id"),
        "content": joint_result.get("blue_content"),
        "deleted": joint_result.get("deleted", 0),
    }

    if joint_result.get("red_summary_id"):
        print(f"[DailyRollup] SUCCESS (red): summary_id={joint_result['red_summary_id']}")
    else:
        print(f"[DailyRollup] Red rollup skipped: {joint_result.get('error', 'no chunks')}")

    if joint_result.get("blue_summary_id"):
        print(f"[DailyRollup] SUCCESS (blue): summary_id={joint_result['blue_summary_id']}")
    else:
        print(f"[DailyRollup] Blue rollup skipped: {joint_result.get('error', 'no chunks')}")

    # ── Memory sidebar pipeline (independent of date/team) ────────────────────
    results["memory"] = {
        "chunks": run_memory_chunks(),
        "rollup": run_memory_rollup(),
    }
    return results


if __name__ == "__main__":
    import argparse
    import schedule
    import time
    import traceback

    parser = argparse.ArgumentParser(description="Daily intelligence rollup")
    parser.add_argument("--date", type=str, default=None,
                        help="Target date YYYY-MM-DD (defaults to yesterday)")
    parser.add_argument("--teams", type=str, default="red,blue",
                        help="Comma-separated teams to process (default: red,blue)")
    parser.add_argument("--memory-only", action="store_true",
                        help="Run only the memory sidebar pipeline")
    # 【新增】一个后台挂机模式参数
    parser.add_argument("--daemon", action="store_true",
                        help="Run continuously in the background (Scheduler mode)")
    args = parser.parse_args()

    # 提取队伍
    teams = [t.strip() for t in args.teams.split(",") if t.strip()]

    if args.daemon:
        # ==========================================
        # 守护进程模式（永远不死，每天定时执行）
        # ==========================================
        def scheduled_job():
            print(f"\n⏰ [Scheduler] 定时任务触发！当前时间: {datetime.now()}", flush=True)
            try:
                # 默认不传 date，让它自动抓取“昨天”的数据
                run_daily_rollup(None, teams=teams)
            except Exception as e:
                print(f"❌ [Scheduler] 定时任务遭遇未捕获异常: {e}", flush=True)
                traceback.print_exc()

        # 设定每天晚上 23:55 执行大盘点（你可以自己改时间）
        schedule.every().day.at("23:55").do(scheduled_job)
        
        print("🚀 [Scheduler] 定时汇总守护进程已启动！设定每天 23:55 执行...", flush=True)
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60) # 每分钟检查一次时间
            except Exception as e:
                print(f"⚠️ [Scheduler] 调度器主循环报警: {e}", flush=True)
                time.sleep(60)
    else:
        # ==========================================
        # 临时工模式（手动执行一次就退出，用于测试）
        # ==========================================
        print("🛠️ [CLI] 执行单次手动汇总...", flush=True)
        if args.memory_only:
            run_memory_chunks()
            run_memory_rollup()
        else:
            run_daily_rollup(args.date, teams=teams)
