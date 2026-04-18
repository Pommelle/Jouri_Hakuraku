import os
import subprocess
import sys
import time
import threading
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(__file__))
from scheduler.daily_rollup import run_daily_rollup


def _next_rollup_time():
    """Return seconds until next 00:05."""
    now = datetime.now()
    next_run = now.replace(hour=0, minute=5, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()


def _rollup_loop():
    """Background thread: wait until 00:05, run rollup, repeat."""
    while True:
        wait = _next_rollup_time()
        print(f"[Scheduler] Next daily rollup in {int(wait//3600)}h {int((wait%3600)//60)}m")
        time.sleep(wait)
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"[Scheduler] Triggering rollup for {yesterday}...")
            run_daily_rollup(yesterday)
        except Exception as e:
            print(f"[Scheduler] Rollup error: {e}")


def start_scheduler():
    t = threading.Thread(target=_rollup_loop, daemon=True)
    t.start()
    print("[Scheduler] Background rollup scheduler started.")


def start_services():
    print("Initiating Jouri Hakuraku (常理伯乐) Services...")

    start_scheduler()

    print("-> Starting Frontend UI...")
    frontend_process = subprocess.Popen(
        ["streamlit", "run", "frontend/app.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )

    try:
        print("Services are running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down services...")
        frontend_process.terminate()
        frontend_process.wait()
        print("Shutdown complete.")


if __name__ == "__main__":
    start_services()
