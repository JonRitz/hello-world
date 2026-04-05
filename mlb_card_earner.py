#!/usr/bin/env python3
"""
MLB The Show 25 - Automated Card Earner
Earns cards and stubs through:
  1. Market flipping  - buy underpriced cards, relist at market value
  2. Program rewards  - claim any unlocked program / milestone rewards
  3. Daily missions   - claim completed daily mission rewards
  4. Login reward     - grab the daily login bonus

Authentication
--------------
Log in to mlb25.theshow.com in your browser, open DevTools → Application →
Cookies, and copy the value of the  _session_id  cookie.  Pass it via
--session or the MLB_SESSION environment variable.

Usage
-----
    python mlb_card_earner.py --session <cookie> --mode daily
    python mlb_card_earner.py --session <cookie> --mode flip --budget 75000
    python mlb_card_earner.py --session <cookie> --mode programs
    python mlb_card_earner.py --session <cookie> --mode missions
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Missing dependency: run  pip install -r requirements.txt")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = "https://mlb25.theshow.com"
REQUEST_DELAY = 0.6          # seconds between API calls — be polite
MARKETPLACE_TAX = 0.10       # MLB The Show charges 10 % on sales
LOG_FILE = Path("card_earner.log")
RESULTS_FILE = Path("earning_results.json")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core earner
# ---------------------------------------------------------------------------
class MLBCardEarner:
    """Authenticated bot that actively earns cards and stubs."""

    def __init__(self, session_cookie: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept": "application/json, text/javascript, */*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://mlb25.theshow.com/",
            }
        )
        self.session.cookies.set("_session_id", session_cookie, domain="mlb25.theshow.com")

        # Running totals for the session summary
        self.cards_earned: list[str] = []
        self.stubs_spent: int = 0
        self.stubs_expected_back: int = 0

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> Optional[dict]:
        url = BASE_URL + path
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return resp.json()
        except requests.HTTPError as exc:
            log.error("GET %s → HTTP %s", path, exc.response.status_code)
        except Exception as exc:  # noqa: BLE001
            log.error("GET %s failed: %s", path, exc)
        return None

    def _post(self, path: str, data: dict | None = None) -> Optional[dict]:
        url = BASE_URL + path
        try:
            resp = self.session.post(url, json=data, timeout=15)
            resp.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return resp.json()
        except requests.HTTPError as exc:
            log.error("POST %s → HTTP %s", path, exc.response.status_code)
        except Exception as exc:  # noqa: BLE001
            log.error("POST %s failed: %s", path, exc)
        return None

    # ------------------------------------------------------------------
    # 1. Market flipper
    # ------------------------------------------------------------------

    def _fetch_listings_page(self, page: int) -> list[dict]:
        data = self._get("/apis/listings.json", {"page": page, "type": "mlb_card"})
        if not data:
            return []
        return data.get("listings", [])

    def scan_market_opportunities(
        self, min_profit: int = 300, max_buy_price: int = 100_000, pages: int = 8
    ) -> list[dict]:
        """
        Scan the marketplace for cards listed below recent-sale average.
        Returns opportunities sorted by expected profit (highest first).
        """
        log.info(
            "Scanning %d listing pages  (min profit %s stubs, max buy %s stubs)…",
            pages,
            f"{min_profit:,}",
            f"{max_buy_price:,}",
        )
        opportunities: list[dict] = []

        for page in range(1, pages + 1):
            listings = self._fetch_listings_page(page)
            if not listings:
                log.warning("No listings on page %d — stopping scan", page)
                break

            for listing in listings:
                item = listing.get("item", {})
                best_sell = listing.get("best_sell_price", 0)

                if best_sell == 0 or best_sell > max_buy_price:
                    continue

                completed = listing.get("completed_orders", [])
                recent_prices = [o["price"] for o in completed[:10] if "price" in o]
                if len(recent_prices) < 3:
                    # Not enough sales history to trust the average
                    continue

                avg_sale = sum(recent_prices) / len(recent_prices)
                net_sale = avg_sale * (1 - MARKETPLACE_TAX)
                profit = net_sale - best_sell

                if profit >= min_profit:
                    opportunities.append(
                        {
                            "uuid": item.get("uuid", ""),
                            "name": item.get("name", "Unknown"),
                            "rarity": item.get("rarity", ""),
                            "ovr": item.get("ovr", 0),
                            "buy_at": best_sell,
                            "avg_sale": round(avg_sale),
                            "expected_profit": round(profit),
                        }
                    )

            log.info(
                "  page %d/%d — %d opportunities so far", page, pages, len(opportunities)
            )

        opportunities.sort(key=lambda x: x["expected_profit"], reverse=True)
        log.info("Scan complete: %d flip opportunities found", len(opportunities))
        return opportunities

    def _buy_card(self, uuid: str, price: int) -> bool:
        """Buy a single card at the given price."""
        result = self._post("/apis/buy_now", {"uuid": uuid, "price": price})
        if result and result.get("status") == "success":
            log.info("  ✔ Bought  %-40s for %10s stubs", uuid[:40], f"{price:,}")
            self.stubs_spent += price
            return True
        log.warning("  ✘ Buy failed for %s: %s", uuid, result)
        return False

    def _list_for_sale(self, uuid: str, price: int) -> bool:
        """List a card on the marketplace at the given price."""
        result = self._post("/apis/create_listing", {"uuid": uuid, "price": price, "type": "sell"})
        if result and result.get("status") == "success":
            log.info("  ✔ Listed  %-40s at  %10s stubs", uuid[:40], f"{price:,}")
            self.stubs_expected_back += price
            return True
        log.warning("  ✘ List failed for %s: %s", uuid, result)
        return False

    def run_market_flipper(self, budget: int = 50_000, min_profit: int = 300) -> list[dict]:
        """
        Buy underpriced cards and immediately relist them for profit.
        Stops when budget is exhausted.  Returns the list of completed flips.
        """
        log.info("=== Market Flipper  |  budget: %s stubs ===", f"{budget:,}")
        remaining = budget
        flipped: list[dict] = []

        opportunities = self.scan_market_opportunities(
            min_profit=min_profit, max_buy_price=remaining
        )

        for opp in opportunities:
            if opp["buy_at"] > remaining:
                log.info(
                    "  Skipping %s — costs %s but only %s left",
                    opp["name"],
                    f"{opp['buy_at']:,}",
                    f"{remaining:,}",
                )
                continue

            log.info(
                "Flipping  %s  (buy %s → sell ~%s, profit ~%s)",
                opp["name"],
                f"{opp['buy_at']:,}",
                f"{opp['avg_sale']:,}",
                f"{opp['expected_profit']:,}",
            )

            if not self._buy_card(opp["uuid"], opp["buy_at"]):
                continue

            remaining -= opp["buy_at"]

            # Undercut the average sale by ~5 % so we sell quickly
            sell_price = max(opp["buy_at"] + 1, int(opp["avg_sale"] * 0.95))
            time.sleep(0.5)
            self._list_for_sale(opp["uuid"], sell_price)
            flipped.append({**opp, "listed_at": sell_price})

            if remaining <= 0:
                log.info("Budget exhausted — stopping flipper")
                break

        est_return = sum(f["listed_at"] * (1 - MARKETPLACE_TAX) for f in flipped)
        est_profit = est_return - self.stubs_spent
        log.info(
            "Flipper done: %d cards bought | spent %s | expected return %s | est. profit %s",
            len(flipped),
            f"{self.stubs_spent:,}",
            f"{round(est_return):,}",
            f"{round(est_profit):,}",
        )
        return flipped

    # ------------------------------------------------------------------
    # 2. Program reward claimer
    # ------------------------------------------------------------------

    def _get_programs(self) -> list[dict]:
        data = self._get("/apis/programs.json")
        return data.get("programs", []) if data else []

    def _get_program_progress(self, program_id: str) -> Optional[dict]:
        return self._get(f"/apis/programs/{program_id}/progress.json")

    def _claim_reward(self, program_id: str, reward_id: str, reward_name: str) -> bool:
        result = self._post(
            f"/apis/programs/{program_id}/claim", {"reward_id": reward_id}
        )
        if result and result.get("status") == "success":
            log.info("  ✔ Claimed program reward: %s", reward_name)
            self.cards_earned.append(reward_name)
            return True
        log.warning("  ✘ Failed to claim %s (program %s): %s", reward_name, program_id, result)
        return False

    def claim_all_program_rewards(self) -> int:
        """Iterate every active program and claim any unlocked rewards."""
        log.info("=== Program Reward Claimer ===")
        programs = self._get_programs()
        if not programs:
            log.warning("No programs returned (auth issue or off-season?)")
            return 0

        log.info("Checking %d programs…", len(programs))
        claimed = 0

        for prog in programs:
            pid = prog.get("id") or prog.get("uuid")
            pname = prog.get("name", pid)
            if not pid:
                continue

            progress = self._get_program_progress(pid)
            if not progress:
                continue

            rewards = progress.get("rewards", [])
            for reward in rewards:
                if reward.get("claimed") or not reward.get("claimable"):
                    continue
                rid = reward.get("id") or reward.get("uuid", "")
                rname = reward.get("name", rid) or f"{pname} reward"
                if self._claim_reward(pid, rid, rname):
                    claimed += 1

        log.info("Program rewards claimed: %d", claimed)
        return claimed

    # ------------------------------------------------------------------
    # 3. Daily mission completer
    # ------------------------------------------------------------------

    def complete_daily_missions(self) -> int:
        """Claim rewards for any daily missions whose objectives are met."""
        log.info("=== Daily Missions ===")
        data = self._get("/apis/daily_missions.json")
        if not data:
            log.warning("Could not fetch daily missions")
            return 0

        missions = data.get("missions", data.get("daily_missions", []))
        log.info("%d daily missions found", len(missions))
        claimed = 0

        for m in missions:
            if m.get("completed") or m.get("claimed"):
                continue
            progress = m.get("progress", 0)
            target = m.get("target", m.get("objective_count", 1))
            if progress < target:
                log.info(
                    "  ○ Not yet complete: %s  (%s/%s)",
                    m.get("name", m.get("id", "?")),
                    progress,
                    target,
                )
                continue

            result = self._post("/apis/daily_missions/claim", {"mission_id": m.get("id", m.get("uuid"))})
            if result and result.get("status") == "success":
                reward_name = (
                    result.get("reward", {}).get("name")
                    or m.get("reward_description", "daily reward")
                )
                log.info("  ✔ Claimed mission reward: %s", reward_name)
                self.cards_earned.append(reward_name)
                claimed += 1
            else:
                log.warning("  ✘ Claim failed for mission %s: %s", m.get("id"), result)

        log.info("Daily missions claimed: %d", claimed)
        return claimed

    # ------------------------------------------------------------------
    # 4. Login reward
    # ------------------------------------------------------------------

    def collect_login_reward(self) -> Optional[dict]:
        """Grab today's daily login reward if it hasn't been collected yet."""
        log.info("=== Daily Login Reward ===")
        data = self._get("/apis/login_reward.json")
        if not data:
            log.warning("Could not fetch login reward info")
            return None

        if not data.get("available", False):
            log.info("Login reward already collected today")
            return None

        result = self._post("/apis/login_reward/claim")
        if result and result.get("status") == "success":
            reward = result.get("reward", {})
            name = reward.get("name", "daily login bonus")
            log.info("  ✔ Collected login reward: %s", name)
            self.cards_earned.append(name)
            return reward

        log.warning("  ✘ Login reward claim failed: %s", result)
        return None

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def run_daily(self, flip_budget: int = 50_000, min_flip_profit: int = 300) -> dict:
        """
        Full daily earning run:
          1. Login reward
          2. Program rewards
          3. Daily missions
          4. Market flipper
        """
        log.info("=" * 60)
        log.info("MLB Card Earner — daily run  %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
        log.info("=" * 60)

        login_reward = self.collect_login_reward()
        program_rewards = self.claim_all_program_rewards()
        daily_missions = self.complete_daily_missions()
        flips = self.run_market_flipper(budget=flip_budget, min_profit=min_flip_profit)

        est_flip_return = int(sum(f["listed_at"] * (1 - MARKETPLACE_TAX) for f in flips))
        est_flip_profit = est_flip_return - self.stubs_spent

        summary = {
            "timestamp": datetime.now().isoformat(),
            "login_reward": login_reward.get("name") if login_reward else None,
            "program_rewards_claimed": program_rewards,
            "daily_missions_claimed": daily_missions,
            "cards_earned": self.cards_earned,
            "market_flips": {
                "count": len(flips),
                "stubs_spent": self.stubs_spent,
                "est_return": est_flip_return,
                "est_profit": est_flip_profit,
                "items": flips,
            },
        }

        log.info("")
        log.info("=" * 60)
        log.info("DAILY RUN COMPLETE")
        log.info("  Login reward:          %s", login_reward.get("name") if login_reward else "none")
        log.info("  Program rewards:       %d", program_rewards)
        log.info("  Daily missions:        %d", daily_missions)
        log.info("  Cards / rewards total: %d", len(self.cards_earned))
        log.info("  Market flips:          %d", len(flips))
        log.info("  Stubs spent:           %s", f"{self.stubs_spent:,}")
        log.info("  Est. return:           %s", f"{est_flip_return:,}")
        log.info("  Est. flip profit:      %s", f"{est_flip_profit:,}")
        log.info("=" * 60)

        # Persist results
        existing: list = []
        if RESULTS_FILE.exists():
            try:
                existing = json.loads(RESULTS_FILE.read_text())
            except Exception:  # noqa: BLE001
                existing = []
        existing.append(summary)
        RESULTS_FILE.write_text(json.dumps(existing, indent=2))
        log.info("Results saved → %s", RESULTS_FILE)

        return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MLB The Show 25 — Automated Card Earner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--session",
        default=os.getenv("MLB_SESSION", ""),
        help="Value of _session_id cookie from mlb25.theshow.com "
             "(or set MLB_SESSION env var)",
    )
    parser.add_argument(
        "--mode",
        choices=["daily", "flip", "programs", "missions", "login"],
        default="daily",
        help="Which earning activity to run",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=50_000,
        help="Stub budget for market flipping",
    )
    parser.add_argument(
        "--min-profit",
        type=int,
        default=300,
        help="Minimum expected profit per flip (stubs)",
    )
    args = parser.parse_args()

    if not args.session:
        parser.error(
            "No session cookie provided.  "
            "Pass --session <value> or set MLB_SESSION=<value>."
        )

    earner = MLBCardEarner(session_cookie=args.session)

    if args.mode == "daily":
        earner.run_daily(flip_budget=args.budget, min_flip_profit=args.min_profit)
    elif args.mode == "flip":
        earner.run_market_flipper(budget=args.budget, min_profit=args.min_profit)
    elif args.mode == "programs":
        earner.claim_all_program_rewards()
    elif args.mode == "missions":
        earner.complete_daily_missions()
    elif args.mode == "login":
        earner.collect_login_reward()


if __name__ == "__main__":
    main()
