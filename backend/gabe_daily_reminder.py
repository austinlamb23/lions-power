import os, sys, json, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE = "http://127.0.0.1:8000"
BOT_ID = os.environ["GROUPME_BOT_ID"]
SITE_URL = "https://lionspower3.duckdns.org/games"

GAME_LABELS = {
    "hangman": "Hangman",
    "name-match": "Name Match",
    "draft-match": "Draft Match",
}


def build_message():
    game = requests.get(f"{BASE}/api/leaderboard/today-game", timeout=10).json()["game"]
    daily = requests.get(f"{BASE}/api/leaderboard/daily", timeout=10).json()
    rows = daily.get("rows", [])
    label = GAME_LABELS.get(game, game)

    lines = [f"\U0001F3AE Today's game is {label} — go get your score in: {SITE_URL}"]

    if rows:
        board = sorted(rows, key=lambda r: -r["score"])
        lines.append("")
        lines.append("Today's leaderboard so far:")
        for i, r in enumerate(board, 1):
            lines.append(f"{i}. {r['player']} — {r['score']} pts")
        lines.append("")
        lines.append("Everyone else — get in there and knock them off the top.")
    else:
        lines.append("")
        lines.append("Nobody's played yet today — be the first one on the board.")

    return "\n".join(lines)


def main():
    text = build_message()
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print(text)
        return
    resp = requests.post(
        "https://api.groupme.com/v3/bots/post",
        json={"bot_id": BOT_ID, "text": text},
        timeout=10,
    )
    print("posted, status:", resp.status_code)


if __name__ == "__main__":
    main()
