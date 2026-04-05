#!/usr/bin/env python3
"""
MLB The Show - Diamond Dynasty Team Builder
Fetches the top-rated player cards and assembles the greatest team of all time.
Run this during the day; review the report before you play at night.
"""

import json
import time
import datetime
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing dependency: run  pip install -r requirements.txt")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = "https://mlb25.theshow.com"
ITEMS_ENDPOINT = f"{BASE_URL}/apis/items.json"
LISTINGS_ENDPOINT = f"{BASE_URL}/apis/listings.json"

# Positions that make up a full 26-man roster
LINEUP_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
SP_SLOTS = 5
RP_SLOTS = 7

REQUEST_DELAY = 0.4   # seconds between pages (be polite to the API)
MAX_PAGES = 80        # cap to avoid runaway loops (~2 000 cards)
REPORT_FILE = Path("team_report.txt")

# Hitter attributes used to score position players (equal weights)
HITTER_ATTRS = [
    "contact_left", "contact_right",
    "power_left", "power_right",
    "plate_vision", "plate_discipline",
    "speed", "fielding_ability",
    "arm_strength",
]

# Pitcher attributes used to score pitchers
PITCHER_ATTRS = [
    "pitch_velocity", "pitch_control", "pitch_movement",
    "stamina", "pitching_clutch",
    "hits_per_bf", "k_per_bf", "bb_per_bf", "hr_per_bf",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_page(page: int, item_type: str = "mlb_card") -> dict:
    """Fetch one page of items from the API."""
    params = {"type": item_type, "page": page}
    resp = requests.get(ITEMS_ENDPOINT, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_listing_price(uuid: str) -> int | None:
    """Return the current best-buy price for a card (stubs). Returns None if unlisted."""
    try:
        resp = requests.get(
            f"{BASE_URL}/apis/listing.json",
            params={"uuid": uuid},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("best_buy_price") or data.get("listing", {}).get("best_buy_price")
    except Exception:
        pass
    return None


def score_hitter(card: dict) -> float:
    """Score a position player card by averaging its key attributes."""
    vals = [card.get(attr, 0) or 0 for attr in HITTER_ATTRS]
    return sum(vals) / len(vals)


def score_pitcher(card: dict) -> float:
    """
    Score a pitcher. Velocity/control/movement/stamina are 'higher is better';
    hits_per_bf / bb_per_bf / hr_per_bf are 'lower is better' so we invert them.
    """
    good = ["pitch_velocity", "pitch_control", "pitch_movement", "stamina", "pitching_clutch", "k_per_bf"]
    bad  = ["hits_per_bf", "bb_per_bf", "hr_per_bf"]
    score = 0.0
    for attr in good:
        score += card.get(attr, 0) or 0
    for attr in bad:
        # Invert: treat as (99 - value) so a low value is rewarded
        score += 99 - (card.get(attr, 0) or 0)
    return score / (len(good) + len(bad))


def display_position(card: dict) -> str:
    return card.get("display_position", "").strip()


def is_starter(card: dict) -> bool:
    return card.get("is_hitter") is False and card.get("stamina", 0) >= 60


def is_reliever(card: dict) -> bool:
    return card.get("is_hitter") is False and card.get("stamina", 0) < 60


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------

def fetch_all_cards(max_pages: int = MAX_PAGES) -> list[dict]:
    """Fetch all Diamond player cards, paginating through the API."""
    all_cards: list[dict] = []
    print(f"[{_ts()}] Fetching player cards from MLB The Show API…")

    try:
        first = fetch_page(1)
    except requests.exceptions.ProxyError:
        print("ERROR: Proxy connection failed. Check your network/proxy settings.")
        return []
    except requests.exceptions.ConnectionError as exc:
        print(f"ERROR: Could not connect to {BASE_URL}\n  {exc}")
        print("  Make sure you have internet access and try again.")
        return []

    total_pages = min(first.get("total_pages", 1), max_pages)
    all_cards.extend(first.get("items", []))
    print(f"  Total pages available: {first.get('total_pages', '?')}  |  fetching up to {total_pages}")

    for page in range(2, total_pages + 1):
        try:
            data = fetch_page(page)
            items = data.get("items", [])
            if not items:
                break
            all_cards.extend(items)
            print(f"  Page {page}/{total_pages}  ({len(all_cards)} cards so far)", end="\r")
            time.sleep(REQUEST_DELAY)
        except (requests.HTTPError, requests.exceptions.ConnectionError) as exc:
            print(f"\n  Warning: error on page {page}: {exc}")
            break

    print(f"\n[{_ts()}] Fetched {len(all_cards)} cards total.")
    return all_cards


# ---------------------------------------------------------------------------
# Team builder
# ---------------------------------------------------------------------------

def build_team(cards: list[dict]) -> dict:
    """
    Pick the highest-scoring card for each roster slot.
    Returns a dict with keys: lineup, rotation, bullpen, bench.
    """
    # Keep only player cards (no equipment, stadiums, etc.)
    players = [c for c in cards if c.get("type") == "mlb_card"]

    # Split hitters and pitchers
    hitters  = [c for c in players if c.get("is_hitter") is True]
    starters = [c for c in players if is_starter(c)]
    relievers= [c for c in players if is_reliever(c)]

    # Score everyone
    for c in hitters:
        c["_score"] = score_hitter(c)
    for c in starters:
        c["_score"] = score_pitcher(c)
    for c in relievers:
        c["_score"] = score_pitcher(c)

    # --- Lineup: best card per position ---------------------------------
    lineup: dict[str, dict] = {}
    used_uuids: set[str] = set()

    for pos in LINEUP_POSITIONS:
        eligible = [
            c for c in hitters
            if pos in c.get("display_position", "") and c["uuid"] not in used_uuids
        ]
        if not eligible:
            # Fallback: any hitter not yet placed (multi-position flexibility)
            eligible = [c for c in hitters if c["uuid"] not in used_uuids]
        if eligible:
            best = max(eligible, key=lambda c: (c.get("ovr", 0), c["_score"]))
            lineup[pos] = best
            used_uuids.add(best["uuid"])

    # --- Starting rotation (SP_SLOTS) -----------------------------------
    rotation: list[dict] = []
    sp_used: set[str] = set()
    for c in sorted(starters, key=lambda c: (c.get("ovr", 0), c["_score"]), reverse=True):
        if len(rotation) >= SP_SLOTS:
            break
        if c["uuid"] not in sp_used:
            rotation.append(c)
            sp_used.add(c["uuid"])

    # --- Bullpen (RP_SLOTS) ---------------------------------------------
    bullpen: list[dict] = []
    rp_used: set[str] = set()
    for c in sorted(relievers, key=lambda c: (c.get("ovr", 0), c["_score"]), reverse=True):
        if len(bullpen) >= RP_SLOTS:
            break
        if c["uuid"] not in rp_used:
            bullpen.append(c)
            rp_used.add(c["uuid"])

    # --- Bench: top hitters not in lineup --------------------------------
    bench_pool = [c for c in hitters if c["uuid"] not in used_uuids]
    bench = sorted(bench_pool, key=lambda c: (c.get("ovr", 0), c["_score"]), reverse=True)[:4]

    return {"lineup": lineup, "rotation": rotation, "bullpen": bullpen, "bench": bench}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def _card_line(card: dict, slot: str = "") -> str:
    name  = card.get("name", "Unknown")
    ovr   = card.get("ovr", "??")
    pos   = card.get("display_position", "")
    team  = card.get("team_short_name", card.get("team", ""))
    rarity= card.get("rarity", "")
    score = card.get("_score", 0)
    label = f"[{slot}]" if slot else f"[{pos}]"
    return f"  {label:<6} OVR {ovr:>3}  {name:<28} {team:<5} {rarity:<10} attr_avg={score:.1f}"


def generate_report(team: dict) -> str:
    now = datetime.datetime.now().strftime("%A, %B %d %Y  %I:%M %p")
    lines = [
        "=" * 70,
        "  MLB THE SHOW — DIAMOND DYNASTY GREATEST TEAM REPORT",
        f"  Generated: {now}",
        "=" * 70,
        "",
        "── STARTING LINEUP ────────────────────────────────────────────────",
    ]
    for pos in LINEUP_POSITIONS:
        card = team["lineup"].get(pos)
        if card:
            lines.append(_card_line(card, slot=pos))
        else:
            lines.append(f"  [{pos}]   — no card found —")

    lines += ["", "── STARTING ROTATION ──────────────────────────────────────────────"]
    for i, card in enumerate(team["rotation"], 1):
        lines.append(_card_line(card, slot=f"SP{i}"))

    lines += ["", "── BULLPEN ─────────────────────────────────────────────────────────"]
    for i, card in enumerate(team["bullpen"], 1):
        lines.append(_card_line(card, slot=f"RP{i}"))

    lines += ["", "── BENCH ───────────────────────────────────────────────────────────"]
    for card in team["bench"]:
        lines.append(_card_line(card))

    lines += [
        "",
        "=" * 70,
        "  Scoring: position players ranked by OVR then avg of 9 hitting/fielding",
        "  attributes; pitchers ranked by OVR then avg of velocity/control/movement",
        "  /stamina/clutch/K-rate (inverted: hits/walks/HR per BF).",
        "=" * 70,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  MLB The Show — Diamond Dynasty Team Builder")
    print("=" * 60)

    cards = fetch_all_cards()

    if not cards:
        print("No cards fetched. Check your internet connection and try again.")
        sys.exit(1)

    print(f"[{_ts()}] Building optimal team…")
    team = build_team(cards)

    report = generate_report(team)
    print("\n" + report)

    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"\n[{_ts()}] Report saved to: {REPORT_FILE.resolve()}")

    # Also save raw card data for the top picks
    snapshot = {
        "generated_at": datetime.datetime.now().isoformat(),
        "lineup": {pos: card for pos, card in team["lineup"].items()},
        "rotation": team["rotation"],
        "bullpen": team["bullpen"],
        "bench": team["bench"],
    }
    snapshot_file = Path("team_snapshot.json")
    snapshot_file.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"[{_ts()}] Full card data saved to: {snapshot_file.resolve()}")


if __name__ == "__main__":
    main()
