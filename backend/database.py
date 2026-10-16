import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "almanac.db"


def get_db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()
