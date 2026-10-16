from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException

AUTH_SECRET = os.environ.get("PUNISHMENT_AUTH_SECRET", "")
MIN_PASSWORD_LEN = 4

INACTIVE_OWNERS = {"Alex Ziolkowski", "Gabe McGill"}


# ── Password hashing (stdlib pbkdf2, no extra deps) ─────────────────────────

def hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    actual = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(actual, expected_hash_hex)


# ── Signed bearer tokens (HMAC over owner_name, no expiry — "log in once,
# stay logged in", shared across every feature that needs an owner login) ──

def make_token(owner_name: str) -> str:
    payload = base64.urlsafe_b64encode(owner_name.encode()).decode().rstrip("=")
    sig = hmac.new(AUTH_SECRET.encode(), owner_name.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token: str) -> str | None:
    try:
        payload, sig = token.split(".", 1)
        padded = payload + "=" * (-len(payload) % 4)
        owner_name = base64.urlsafe_b64decode(padded.encode()).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    expected_sig = hmac.new(AUTH_SECRET.encode(), owner_name.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    return owner_name


def get_current_owner(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not logged in")
    owner_name = verify_token(authorization[len("Bearer "):])
    if owner_name is None:
        raise HTTPException(401, "Invalid session, please log in again")
    return owner_name


def get_optional_owner(authorization: str | None = Header(default=None)) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return verify_token(authorization[len("Bearer "):])


# Flagged for suspected unauthorized access (2026-09-03) — logins still work
# so the account holder sees the message, but every write action is blocked.
FLAGGED_OWNERS = {"John Yocum"}
FLAGGED_MESSAGE = "We know it's you Mark."


def get_active_owner(owner: str = Depends(get_current_owner)) -> str:
    if owner in FLAGGED_OWNERS:
        raise HTTPException(423, FLAGGED_MESSAGE)
    return owner


COMMISSIONER = os.environ.get("COMMISSIONER_NAME", "Austin Lamb")


def require_commissioner(owner: str = Depends(get_active_owner)) -> str:
    if owner != COMMISSIONER:
        raise HTTPException(403, "Only the commissioner can do that")
    return owner


def get_all_owners(db: sqlite3.Connection) -> list:
    rows = db.execute("SELECT DISTINCT owner_name FROM teams ORDER BY owner_name").fetchall()
    return [r["owner_name"] for r in rows if r["owner_name"] not in INACTIVE_OWNERS]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
