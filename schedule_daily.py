#!/usr/bin/env python3
"""
Runs mlb_team_builder.py once a day at a specified time.
Usage:  python schedule_daily.py           # defaults to 9:00 AM
        python schedule_daily.py 08:30     # custom time (24-hour HH:MM)

Alternatively, add a cron job (Linux/Mac):
    0 9 * * * cd /path/to/hello-world && python mlb_team_builder.py >> mlb_builder.log 2>&1

Or Windows Task Scheduler pointing to:
    python C:\path\to\hello-world\mlb_team_builder.py
"""

import sys
import time
import datetime
import subprocess

RUN_TIME_DEFAULT = "09:00"


def next_run_at(target: datetime.time) -> datetime.datetime:
    now = datetime.datetime.now()
    candidate = datetime.datetime.combine(now.date(), target)
    if candidate <= now:
        candidate += datetime.timedelta(days=1)
    return candidate


def main():
    time_str = sys.argv[1] if len(sys.argv) > 1 else RUN_TIME_DEFAULT
    try:
        target = datetime.time.fromisoformat(time_str)
    except ValueError:
        print(f"Invalid time '{time_str}'. Use HH:MM format, e.g. 09:00")
        sys.exit(1)

    print(f"MLB Team Builder scheduler started — will run daily at {time_str}")
    print("Press Ctrl+C to stop.\n")

    while True:
        run_at = next_run_at(target)
        wait_sec = (run_at - datetime.datetime.now()).total_seconds()
        print(f"Next run scheduled for {run_at.strftime('%A %B %d at %I:%M %p')}  "
              f"({wait_sec/3600:.1f} h from now)")
        time.sleep(max(wait_sec, 0))

        print(f"\n[{datetime.datetime.now():%H:%M:%S}] Running team builder…")
        result = subprocess.run(
            [sys.executable, "mlb_team_builder.py"],
            capture_output=False,
        )
        if result.returncode != 0:
            print("  Team builder exited with an error. Check output above.")
        else:
            print("  Done! Check team_report.txt for today's greatest team.")

        # Sleep 60 s so we don't re-trigger in the same minute
        time.sleep(60)


if __name__ == "__main__":
    main()
