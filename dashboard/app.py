import os
import sqlite3
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import DB_PATH, dashboard_stats, init_db

init_db()

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


PAGE_SIZE = 50


def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def _list_tables(conn):
    return [
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


@app.get("/")
def index(request: Request):
    stats = dashboard_stats()
    return templates.TemplateResponse(request, "index.html", stats)


@app.get("/db")
def db_index(request: Request):
    with _conn() as conn:
        tables = []
        for name in _list_tables(conn):
            count = conn.execute(f'SELECT COUNT(*) AS c FROM "{name}"').fetchone()["c"]
            tables.append({"name": name, "count": count})
    return templates.TemplateResponse(request, "db_index.html", {"tables": tables})


@app.get("/db/{table}")
def db_table(request: Request, table: str, page: int = 1):
    with _conn() as conn:
        allowed = _list_tables(conn)
        if table not in allowed:
            raise HTTPException(404, f"unknown table: {table}")
        page = max(1, page)
        offset = (page - 1) * PAGE_SIZE
        total = conn.execute(f'SELECT COUNT(*) AS c FROM "{table}"').fetchone()["c"]
        rows_raw = conn.execute(
            f'SELECT * FROM "{table}" ORDER BY rowid DESC LIMIT ? OFFSET ?',
            (PAGE_SIZE, offset),
        ).fetchall()
        columns = rows_raw[0].keys() if rows_raw else [
            r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')
        ]
        rows = [[_truncate(r[c]) for c in columns] for r in rows_raw]
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse(
        request,
        "db_table.html",
        {
            "table": table,
            "columns": list(columns),
            "rows": rows,
            "page": page,
            "pages": pages,
            "total": total,
            "tables": allowed,
        },
    )


def _truncate(value, limit=300):
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= limit else s[:limit] + "…"
