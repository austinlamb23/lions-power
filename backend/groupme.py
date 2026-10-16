from __future__ import annotations
import os
import requests

GROUP_ID = "42375986"  # Lions Power Fantasy Football

# owner_name (as stored in almanac.db) -> GroupMe user_id, resolved 2026-07-20
# from GET /groups/{GROUP_ID} member list. Gabe McGill has no entry here —
# he only owned a team for the 2013 season and isn't in the group chat.
OWNER_TO_GROUPME_ID = {
    "Vincent Zahm": "21040195",
    "Mark Safranek": "30237574",
    "Bubbleface Bob": "30234219",
    "pickle": "21968146",
    "Luke Rabideau": "32732540",
    "Dan Watza": "32732538",
    "Josh Frey": "54232338",
    "Austin Lamb": "32509479",
    "Alex Ziolkowski": "41042600",
    "steve": "95441496",
    "John Yocum": "117168294",
}


def post_groupme_message(text: str, mentions: list[tuple[str, str]] | None = None) -> requests.Response:
    """Post a message as Gabe. `mentions` is a list of (owner_name, display_text)
    pairs — display_text must appear verbatim in `text` (e.g. "@Austin Lamb");
    it's used to compute the GroupMe mention attachment's character offsets
    automatically. Unknown owner_names (no GroupMe account, e.g. Gabe McGill)
    are silently skipped — the text still posts, just without a real tag."""
    bot_id = os.environ["GROUPME_BOT_ID"]

    attachments = []
    if mentions:
        user_ids = []
        loci = []
        for owner_name, display_text in mentions:
            uid = OWNER_TO_GROUPME_ID.get(owner_name)
            if not uid:
                continue
            idx = text.find(display_text)
            if idx == -1:
                continue
            user_ids.append(uid)
            loci.append([idx, len(display_text)])
        if user_ids:
            attachments.append({"type": "mentions", "user_ids": user_ids, "loci": loci})

    payload = {"bot_id": bot_id, "text": text}
    if attachments:
        payload["attachments"] = attachments

    return requests.post("https://api.groupme.com/v3/bots/post", json=payload, timeout=10)


GROUPME_MAX_LEN = 1000


def split_message(text: str, max_len: int = GROUPME_MAX_LEN) -> list[str]:
    """Split text into chunks of at most max_len chars, breaking on
    whitespace so words (and any trailing caveat) never get cut off
    mid-sentence — sent as separate sequential GroupMe posts instead.

    Splits line-by-line rather than text.split() on the whole string —
    a plain .split() breaks on ANY whitespace including newlines, and
    rejoining words with a single space silently collapses every line
    break into a wall of text, even for a message short enough to need
    no splitting at all (found 2026-08-11 after a multi-paragraph
    announcement posted with zero line breaks)."""
    lines = text.split("\n")
    chunks = []
    current = ""
    for line in lines:
        while len(line) > max_len:
            cut = line.rfind(" ", 0, max_len)
            if cut == -1:
                cut = max_len
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:cut])
            line = line[cut:].lstrip()
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_len:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def post_long_message(text: str, mentions: list[tuple[str, str]] | None = None) -> None:
    """post_groupme_message, but safe for text longer than GroupMe's ~1000
    char cap -- splits and posts sequentially. A mention only ever lands on
    whichever chunk actually contains its display_text (post_groupme_message
    already no-ops a mention it can't find in the given text)."""
    for chunk in split_message(text):
        post_groupme_message(chunk, mentions=mentions).raise_for_status()
