#!/usr/bin/env python3
"""
Daily scheduler for the MLB Card Earner.
Runs mlb_card_earner.py once per day at a configurable time.

Usage
-----
    python schedule_daily.py --session <cookie>              # runs at 09:00
    python schedule_daily.py --session <cookie> --time 07:30
    python schedule_daily.py --session <cookie> --time 22:00 --budget 100000

Or set MLB_SESSION in the environment and omit --session entirely.

Cron alternative (Linux/Mac) — add via  crontab -e :
    0 9 * * * cd /path/to/project && MLB_SESSION=<cookie> python mlb_card_earner.py --mode daily

Windows Task Scheduler alternative:
    Action: python C:\path\to\mlb_card_earner.py --session <cookie> --mode daily
    Trigger: Daily at 09:00
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

EARNER_SCRIPT = Path(__file__).parent / "mlb_card_earner.py"


def next_run_at(target_time_str: str) -> datetime:
    """Return the next datetime matching HH:MM (today if still in future, else tomorrow)."""
    hour, minute = map(int, target_time_str.split(":"))
    now = datetime.now()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def run_earner(session: str, budget: int, min_profit: int, mode: str) -> int:
    """Invoke mlb_card_earner.py as a subprocess and return its exit code."""
    cmd = [
        sys.executable,
        str(EARNER_SCRIPT),
        "--session", session,
        "--mode", mode,
        "--budget", str(budget),
        "--min-profit", str(min_profit),
    ]
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily scheduler for the MLB Card Earner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--session",
        default=os.getenv("MLB_SESSION", ""),
        help="Value of _session_id cookie (or set MLB_SESSION env var)",
    )
    parser.add_argument(
        "--time",
        default="09:00",
        metavar="HH:MM",
        help="Time of day to run (24-hour format)",
    )
    parser.add_argument("--budget", type=int, default=50_000, help="Stub budget for flipping")
    parser.add_argument("--min-profit", type=int, default=300, help="Min profit per flip")
    parser.add_argument(
        "--mode",
        choices=["daily", "flip", "programs", "missions", "login"],
        default="daily",
        help="Earning mode passed to mlb_card_earner.py",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute once immediately before entering the daily loop",
    )
    args = parser.parse_args()

    if not args.session:
        parser.error("No session cookie.  Pass --session or set MLB_SESSION.")

    if not EARNER_SCRIPT.exists():
        log.error("Cannot find %s", EARNER_SCRIPT)
        sys.exit(1)

    log.info("Scheduler started — daily run at %s", args.time)

    if args.run_now:
        log.info("--run-now flag set — executing immediately")
        rc = run_earner(args.session, args.budget, args.min_profit, args.mode)
        log.info("Immediate run finished with exit code %d", rc)

    while True:
        target = next_run_at(args.time)
        wait_seconds = (target - datetime.now()).total_seconds()
        log.info("Next run at %s (in %.0f seconds)", target.strftime("%Y-%m-%d %H:%M"), wait_seconds)

        time.sleep(max(0, wait_seconds))

        log.info("Starting scheduled run at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        rc = run_earner(args.session, args.budget, args.min_profit, args.mode)
        if rc == 0:
            log.info("Run completed successfully")
        else:
            log.error("Run finished with exit code %d — will retry tomorrow", rc)


if __name__ == "__main__":
    main()
