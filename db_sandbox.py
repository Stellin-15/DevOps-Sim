"""
Database sandbox — a real SQL database, not pre-written output. Each state
is an in-memory SQLite copy of a small shop database (customers, orders,
order_items, products, addresses, a daily_sales reporting table, and the
app's own job_runs, schema_migrations, and query_stats tables), seeded with
two of four real data problems:
  missing_index      a migration dropped the index behind the 'My orders' query
  duplicate_load     a manual re-run loaded one day of daily_sales twice
  orphaned_items     a cleanup job deleted orders but left their order_items
  deleted_addresses  a support script deleted saved addresses; a backup
                     table exists, but some rows changed after it was taken

The player types real SQL (one statement per line), sqlite3 dot-commands
(.tables, .schema, .indexes), or psql-style \\dt, \\d, \\di. Transactions are
explicit (BEGIN / COMMIT / ROLLBACK), as in psql.

Sandbox states must be JSON-saveable, so the state holds a SQL dump of the
last committed data; the live connection lives in _CONNS and is rebuilt
from the dump when a saved state is loaded.
"""

import random
import sqlite3
import uuid
from datetime import datetime, timedelta

from sandbox_common import render_table, run_loop

PROBLEMS = ["missing_index", "duplicate_load", "orphaned_items", "deleted_addresses"]

REPORTS = {
    "missing_index": "The 'My orders' page has been slow since yesterday's release.",
    "duplicate_load": "Finance says October 1st's revenue in daily_sales looks about double.",
    "orphaned_items": "The order-items export lists items whose order can't be found.",
    "deleted_addresses": "Support ran a cleanup script this morning, and customers report missing saved "
                         "addresses. Last night's copy is in addresses_backup_20261002.",
}

# The query behind the 'My orders' page; missing_index makes it a full scan.
MY_ORDERS_SQL = "SELECT * FROM orders WHERE customer_id = 42 ORDER BY created_at DESC LIMIT 20"
DOUBLE_DAY = "2026-10-01"
BACKUP_TABLE = "addresses_backup_20261002"
MAX_ROWS_SHOWN = 40

HELP_TEXT = """This is a real SQL database (SQLite). Type one SQL statement per line; the trailing ; is optional.
  SELECT ... / INSERT ... / UPDATE ... / DELETE ... / CREATE INDEX ... / DROP INDEX ...
  BEGIN   COMMIT   ROLLBACK          (transactions are explicit, as in psql)
  EXPLAIN QUERY PLAN <select>        (SQLite's version of PostgreSQL's EXPLAIN)
  PRAGMA foreign_keys   PRAGMA index_list(<table>)   PRAGMA table_info(<table>)
Meta-commands:
  .tables   .schema [table]   .indexes [table]      (sqlite3 style)
  \\dt       \\d <table>        \\di                   (psql style)
  check     which of the reported problems are fixed (sandbox only, not SQL)
  help | exit          (pipes work on the output: SELECT * FROM job_runs | grep manual)"""

SCHEMA = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE addresses (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
                        city TEXT NOT NULL, postcode TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                       price_cents INTEGER NOT NULL, stock INTEGER NOT NULL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
                     status TEXT NOT NULL, total_cents INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
                          product_id INTEGER NOT NULL REFERENCES products(id), qty INTEGER NOT NULL,
                          price_cents INTEGER NOT NULL);
CREATE TABLE daily_sales (order_id INTEGER NOT NULL, sale_date TEXT NOT NULL, amount_cents INTEGER NOT NULL,
                          loaded_at TEXT NOT NULL);
CREATE TABLE job_runs (id INTEGER PRIMARY KEY, job TEXT NOT NULL, run_for TEXT, started_at TEXT NOT NULL,
                       triggered_by TEXT NOT NULL, status TEXT NOT NULL, note TEXT);
CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, name TEXT NOT NULL, statements TEXT NOT NULL,
                                applied_at TEXT NOT NULL);
CREATE TABLE query_stats (query TEXT NOT NULL, calls INTEGER NOT NULL, mean_ms REAL NOT NULL);
CREATE INDEX idx_orders_created_at ON orders(created_at);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_addresses_customer_id ON addresses(customer_id);
"""

FIRST = ["Ana", "Ben", "Chen", "Dana", "Eli", "Fatima", "Gus", "Hana", "Ivan", "Jo", "Kofi", "Lena",
         "Mo", "Nina", "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tariq"]
LAST = ["Silva", "Okafor", "Novak", "Park", "Reyes", "Haddad", "Kowalski", "Mensah", "Ito", "Brennan",
        "Duarte", "Larsen", "Mehta", "Quist", "Sato", "Varga"]
CITIES = ["Leeds", "Porto", "Lyon", "Gdansk", "Bremen", "Turin", "Ghent", "Cork", "Malmo", "Brno"]
PRODUCTS = ["Mug", "Notebook", "Desk lamp", "Backpack", "Water bottle", "Headphones", "Keyboard",
            "Phone stand", "Tote bag", "Pen set", "Monitor arm", "Cable kit", "Plant pot", "Clock",
            "Blanket", "Candle", "Coaster set", "Poster", "Umbrella", "Wallet"]

# db_key -> {"state_id", "conn", "issues"}; see the module docstring.
_CONNS = {}


# --------------------------------------------------------------- generation

def generate_state(seed=None, problems=None) -> dict:
    """Random 2 problems by default; mystery incidents pass an explicit
    list so the root cause is known in advance."""
    rng = random.Random(seed)
    problems = list(problems) if problems is not None else rng.sample(PROBLEMS, k=2)
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.executescript(SCHEMA)
    expected = {}

    customers = []
    for cid in range(1, 151):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        created = datetime(2025, 1, 1) + timedelta(days=rng.randint(0, 600))
        customers.append((cid, f"{first.lower()}.{last.lower()}{cid}@mail.example", f"{first} {last}",
                          created.strftime("%Y-%m-%d")))
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", customers)

    addresses, aid = [], 0
    for cid, *_ in customers:
        for _ in range(2 if rng.random() < 0.3 else 1):
            aid += 1
            addresses.append((aid, cid, rng.choice(CITIES), f"{rng.randint(10, 99)}-{rng.randint(100, 999)}",
                              "2026-09-14 10:00:00"))
    conn.executemany("INSERT INTO addresses VALUES (?, ?, ?, ?, ?)", addresses)

    products = [(pid, f"SKU{1000 + pid}", name, rng.randint(5, 120) * 100 - 1, rng.randint(0, 400))
                for pid, name in enumerate(PRODUCTS, start=1)]
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", products)

    orders, items, iid = [], [], 0
    start = datetime(2026, 9, 1)
    for oid in range(1, 1801):
        created = start + timedelta(days=rng.randint(0, 31), seconds=rng.randint(0, 86399))
        status = rng.choices(["paid", "shipped", "refunded", "cancelled"], weights=[30, 55, 5, 10])[0]
        total = 0
        for _ in range(rng.randint(1, 4)):
            iid += 1
            product = rng.choice(products)
            qty = rng.randint(1, 3)
            items.append((iid, oid, product[0], qty, product[3]))
            total += qty * product[3]
        orders.append((oid, rng.randint(1, 150), status, total, created.strftime("%Y-%m-%d %H:%M:%S")))
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)
    conn.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", items)

    sales = []
    for oid, _, status, total, created in orders:
        day = created[:10]
        if status in ("paid", "shipped") and day >= "2026-09-25" and day <= "2026-10-02":
            loaded = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1, hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            sales.append((oid, day, total, loaded))
    conn.executemany("INSERT INTO daily_sales VALUES (?, ?, ?, ?)", sales)

    jobs = []
    for offset in range(8):
        day = (datetime(2026, 9, 25) + timedelta(days=offset)).strftime("%Y-%m-%d")
        nxt = (datetime(2026, 9, 26) + timedelta(days=offset)).strftime("%Y-%m-%d")
        jobs.append(("load_daily_sales", day, f"{nxt} 02:00:00", "scheduler", "success", None))
    conn.executemany("INSERT INTO job_runs (job, run_for, started_at, triggered_by, status, note) "
                     "VALUES (?, ?, ?, ?, ?, ?)", jobs)

    conn.executemany("INSERT INTO schema_migrations VALUES (?, ?, ?, ?)", [
        ("20260811_0900", "create_daily_sales", "CREATE TABLE daily_sales (...)", "2026-08-11 09:00:41"),
        ("20260902_1400", "add_addresses_updated_at", "ALTER TABLE addresses ADD COLUMN updated_at TEXT",
         "2026-09-02 14:02:10"),
    ])
    conn.executemany("INSERT INTO query_stats VALUES (?, ?, ?)", [
        ("SELECT * FROM products WHERE id = ?", 912004, 0.04),
        ("SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT 20", 41208, 0.9),
        ("SELECT * FROM addresses WHERE customer_id = ?", 38114, 0.05),
        ("INSERT INTO orders (...) VALUES (...)", 1800, 1.2),
    ])

    for problem in problems:
        _APPLY[problem](conn, rng, expected)
    if "missing_index" not in problems:
        conn.execute("CREATE INDEX idx_orders_customer_id ON orders(customer_id)")

    expected["customers"] = _scalar(conn, "SELECT count(*) FROM customers")
    expected["orders"] = _scalar(conn, "SELECT count(*) FROM orders")
    expected["real_items"] = _scalar(conn, "SELECT count(*) FROM order_items WHERE order_id IN (SELECT id FROM orders)")
    expected["sales_orders"] = _scalar(conn, "SELECT count(DISTINCT order_id) FROM daily_sales")

    state = {"seed": seed, "problems": problems, "expected": expected,
             "db_key": uuid.uuid4().hex, "dump": "\n".join(conn.iterdump())}
    _CONNS[state["db_key"]] = {"state_id": id(state), "conn": conn, "issues": None}
    return state


def _missing_index(conn, rng, expected):
    conn.execute("INSERT INTO schema_migrations VALUES (?, ?, ?, ?)",
                 ("20261002_0900", "drop_unused_indexes",
                  "DROP INDEX idx_orders_customer_id; DROP INDEX idx_products_legacy_code",
                  "2026-10-02 09:00:12"))
    conn.execute("UPDATE query_stats SET mean_ms = 3912.4 WHERE query LIKE 'SELECT * FROM orders WHERE customer_id%'")


def _duplicate_load(conn, rng, expected):
    conn.execute("UPDATE job_runs SET status = 'failed', note = 'timed out notifying finance after the load' "
                 "WHERE job = 'load_daily_sales' AND run_for = ?", (DOUBLE_DAY,))
    conn.execute("INSERT INTO job_runs (job, run_for, started_at, triggered_by, status, note) VALUES "
                 "('load_daily_sales', ?, '2026-10-02 09:41:02', 'dana (manual re-run)', 'success', NULL)",
                 (DOUBLE_DAY,))
    conn.execute("INSERT INTO daily_sales SELECT order_id, sale_date, amount_cents, '2026-10-02 09:41:07' "
                 "FROM daily_sales WHERE sale_date = ?", (DOUBLE_DAY,))


def _orphaned_items(conn, rng, expected):
    cancelled = [r[0] for r in conn.execute("SELECT id FROM orders WHERE status = 'cancelled' ORDER BY id")]
    victims = rng.sample(cancelled, k=min(24, len(cancelled)))
    conn.executemany("DELETE FROM orders WHERE id = ?", [(v,) for v in victims])
    conn.execute("INSERT INTO job_runs (job, run_for, started_at, triggered_by, status, note) VALUES "
                 "('cleanup_cancelled_orders', NULL, '2026-10-02 03:00:00', 'cron', 'success', ?)",
                 (f"deleted {len(victims)} orders",))


def _deleted_addresses(conn, rng, expected):
    conn.execute(f"CREATE TABLE {BACKUP_TABLE} AS SELECT * FROM addresses")
    ids = [r[0] for r in conn.execute("SELECT id FROM addresses ORDER BY id")]
    updated = rng.choice(ids)
    old_city = _scalar(conn, "SELECT city FROM addresses WHERE id = ?", (updated,))
    new_city = next(c for c in CITIES if c != old_city)
    conn.execute("UPDATE addresses SET city = ?, updated_at = '2026-10-02 08:12:40' WHERE id = ?", (new_city, updated))
    new_ids = []
    for _ in range(3):
        cur = conn.execute("INSERT INTO addresses (customer_id, city, postcode, updated_at) "
                           "VALUES (?, ?, ?, '2026-10-02 08:30:00')",
                           (rng.randint(1, 150), rng.choice(CITIES), f"{rng.randint(10, 99)}-{rng.randint(100, 999)}"))
        new_ids.append(cur.lastrowid)
    victims = rng.sample([i for i in ids if i != updated], k=40)
    conn.executemany("DELETE FROM addresses WHERE id = ?", [(v,) for v in victims])
    conn.execute("INSERT INTO job_runs (job, run_for, started_at, triggered_by, status, note) VALUES "
                 "('support_cleanup_addresses', NULL, '2026-10-02 09:15:00', 'support-script', 'success', "
                 "'removed 40 addresses of inactive customers')")
    expected["address_ids"] = sorted(ids + new_ids)
    expected["updated_address"] = {"id": updated, "city": new_city}


_APPLY = {
    "missing_index": _missing_index,
    "duplicate_load": _duplicate_load,
    "orphaned_items": _orphaned_items,
    "deleted_addresses": _deleted_addresses,
}


# --------------------------------------------------------------- connection

def _conn(state: dict) -> sqlite3.Connection:
    entry = _CONNS.get(state["db_key"])
    if entry is None or entry["state_id"] != id(state):
        conn = sqlite3.connect(":memory:", isolation_level=None)
        conn.executescript(state["dump"])
        entry = {"state_id": id(state), "conn": conn, "issues": None}
        _CONNS[state["db_key"]] = entry
    return entry["conn"]


def _scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _safe_scalar(conn, sql, params=()):
    try:
        return _scalar(conn, sql, params)
    except sqlite3.Error:
        return None


def _save(state: dict, conn) -> None:
    """Persist committed data only: a dump taken mid-transaction would make
    uncommitted changes permanent when the state is reloaded."""
    if not conn.in_transaction:
        state["dump"] = "\n".join(conn.iterdump())


# ----------------------------------------------------------------- commands

def _format_value(v):
    return "NULL" if v is None else v


def _render_rows(cursor) -> str:
    headers = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    shown = [[_format_value(v) for v in r] for r in rows[:MAX_ROWS_SHOWN]]
    out = render_table(headers, shown) if rows else render_table(headers, [])
    if len(rows) > MAX_ROWS_SHOWN:
        return f"{out}\n... ({len(rows)} rows; showing {MAX_ROWS_SHOWN}, add a LIMIT or an aggregate)"
    return f"{out}\n({len(rows)} row{'s' if len(rows) != 1 else ''})"


def _render_plan(rows) -> str:
    depth = {0: -1}
    lines = ["QUERY PLAN"]
    for node, parent, _, detail in rows:
        depth[node] = depth.get(parent, -1) + 1
        lines.append("   " * depth[node] + "|--" + detail)
    return "\n".join(lines)


def _tables(conn) -> list:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _schema(conn, table=None) -> str:
    if table:
        rows = conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name = ? AND sql IS NOT NULL "
                            "ORDER BY type DESC, name", (table,)).fetchall()
        return "\n".join(r[0] + ";" for r in rows) or f"Error: no such table: {table}"
    rows = conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
                        "ORDER BY tbl_name, type DESC").fetchall()
    return "\n".join(r[0] + ";" for r in rows)


def _indexes(conn, table=None) -> str:
    sql = ("SELECT tbl_name, name, sql FROM sqlite_master WHERE type = 'index' "
           + ("AND tbl_name = ? " if table else "") + "ORDER BY tbl_name, name")
    rows = conn.execute(sql, (table,) if table else ()).fetchall()
    if not rows:
        return f"(no indexes{' on ' + table if table else ''})"
    return render_table(["TABLE", "INDEX", "DEFINITION"],
                        [(t, n, s or "(automatic: primary key or UNIQUE constraint)") for t, n, s in rows])


def _describe_table(conn, table) -> str:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if not cols:
        return f'Did not find any relation named "{table}".'
    out = render_table(["Column", "Type", "Nullable", "Default"],
                       [(c[1], c[2], "not null" if c[3] else "", "" if c[4] is None else c[4]) for c in cols])
    idx = conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name = ? ORDER BY name",
                       (table,)).fetchall()
    lines = [f'Table "{table}"', out, "Indexes:"]
    lines += [f"    {n}: {s or 'automatic (primary key / UNIQUE)'}" for n, s in idx] or ["    (none)"]
    return "\n".join(lines)


def _meta(state, conn, raw) -> str:
    parts = raw.split()
    cmd, arg = parts[0], (parts[1] if len(parts) > 1 else None)
    if cmd in (".tables", "\\dt"):
        return "  ".join(_tables(conn))
    if cmd == ".schema":
        return _schema(conn, arg)
    if cmd in (".indexes", ".indices", "\\di"):
        return _indexes(conn, arg)
    if cmd == "\\d":
        return _describe_table(conn, arg) if arg else "  ".join(_tables(conn))
    if cmd in (".help", "\\?"):
        return HELP_TEXT
    if cmd in (".quit", ".exit", "\\q"):
        return "Type 'exit' to leave the sandbox."
    return f"{cmd}: not simulated in the sandbox. Type 'help' for supported commands."


BLOCKED = ("attach", "detach", "vacuum into", "load_extension")


def _sql(state, conn, raw) -> str:
    sql = raw.strip().rstrip(";").strip()
    lowered = " ".join(sql.lower().split())
    if any(lowered.startswith(b) or f" {b}" in lowered for b in BLOCKED):
        return "Error: not allowed in the sandbox (it would touch files outside the database)."
    if lowered.startswith("explain analyze") or (lowered.startswith("explain") and
                                                 not lowered.startswith("explain query plan")):
        return ("Error: SQLite shows plans with EXPLAIN QUERY PLAN <query>. (PostgreSQL's equivalent is "
                "EXPLAIN, or EXPLAIN ANALYZE to run it and time it.)")
    try:
        cursor = conn.execute(sql)
    except sqlite3.Warning:
        return "Error: one statement at a time, please (split them over several lines)."
    except sqlite3.Error as e:
        return f"Error: {e}"
    if lowered.startswith("explain query plan"):
        return _render_plan(cursor.fetchall())
    if cursor.description:
        return _render_rows(cursor)
    _save(state, conn)
    verb = lowered.split()[0].upper()
    if verb in ("INSERT", "UPDATE", "DELETE", "REPLACE"):
        return f"{verb} {cursor.rowcount}"
    if verb in ("BEGIN", "COMMIT", "END", "ROLLBACK"):
        return {"END": "COMMIT"}.get(verb, verb)
    # CREATE UNIQUE INDEX -> CREATE INDEX, DROP TABLE IF EXISTS -> DROP TABLE
    words = [w for w in lowered.split() if w not in ("unique", "temp", "temporary", "virtual")]
    return " ".join(words[:2]).upper()


def handle_command(state: dict, raw: str) -> str:
    raw = raw.strip()
    conn = _conn(state)
    lowered = raw.lower().rstrip(";")
    if lowered in ("help", "?"):
        return HELP_TEXT
    if lowered == "check":
        return _check_report(state)
    if raw.startswith(".") or raw.startswith("\\"):
        return _meta(state, conn, raw)
    return _sql(state, conn, raw)


# ------------------------------------------------------- mystery/sandbox hooks

def _query_uses_index(state, goal=None) -> bool:
    try:
        plan = _conn(state).execute("EXPLAIN QUERY PLAN " + MY_ORDERS_SQL).fetchall()
    except sqlite3.Error:
        return False
    return any(row[3].startswith("SEARCH orders") for row in plan)


def _no_duplicates(state, goal=None) -> bool:
    conn = _conn(state)
    total = _safe_scalar(conn, "SELECT count(*) FROM daily_sales")
    distinct = _safe_scalar(conn, "SELECT count(DISTINCT order_id) FROM daily_sales")
    return total is not None and total == distinct == state["expected"]["sales_orders"]


def _unique_guard(state, goal=None) -> bool:
    """A unique index that stops the same order being loaded twice: on
    order_id, optionally with sale_date (not with loaded_at, which differs
    between the two loads and so guards nothing)."""
    conn = _conn(state)
    try:
        for _, name, unique, *_ in conn.execute("PRAGMA index_list(daily_sales)").fetchall():
            cols = {r[2] for r in conn.execute(f"PRAGMA index_info('{name}')").fetchall()}
            if unique and "order_id" in cols and cols <= {"order_id", "sale_date"}:
                return True
    except sqlite3.Error:
        pass
    return False


def _no_orphans(state, goal=None) -> bool:
    conn = _conn(state)
    orphans = _safe_scalar(conn, "SELECT count(*) FROM order_items WHERE order_id NOT IN (SELECT id FROM orders)")
    total = _safe_scalar(conn, "SELECT count(*) FROM order_items")
    return orphans == 0 and total == state["expected"]["real_items"]


def _addresses_restored(state, goal=None) -> bool:
    conn = _conn(state)
    try:
        ids = [r[0] for r in conn.execute("SELECT id FROM addresses ORDER BY id")]
    except sqlite3.Error:
        return False
    updated = state["expected"]["updated_address"]
    city = _safe_scalar(conn, "SELECT city FROM addresses WHERE id = ?", (updated["id"],))
    return ids == state["expected"]["address_ids"] and city == updated["city"]


def _committed(state, goal=None) -> bool:
    return not _conn(state).in_transaction


GOAL_CHECKS = {
    "query_uses_index": _query_uses_index,
    "no_duplicates": _no_duplicates,
    "unique_guard": _unique_guard,
    "no_orphans": _no_orphans,
    "addresses_restored": _addresses_restored,
    "committed": _committed,
    # Generic: a query whose first column must equal a value.
    "sql_equals": lambda state, g: _safe_scalar(_conn(state), g["sql"]) == g["value"],
}

PROBLEM_GOALS = {
    "missing_index": [_query_uses_index],
    "duplicate_load": [_no_duplicates, _unique_guard],
    "orphaned_items": [_no_orphans],
    "deleted_addresses": [_addresses_restored],
}


def _check_report(state) -> str:
    lines = []
    for p in state["problems"]:
        fixed = all(check(state) for check in PROBLEM_GOALS[p])
        lines.append(f"[{'fixed' if fixed else 'open '}] {REPORTS[p]}")
    if _conn(state).in_transaction:
        lines.append("Note: a transaction is open. Nothing is final until you COMMIT (or ROLLBACK).")
    return "\n".join(lines)


def placeholders(state: dict) -> dict:
    return {}


def collateral_issues(state: dict) -> set:
    """Damage that's easy to do while fixing data by hand. Judged on
    committed data: inside a transaction the last committed verdict
    stands, so BEGIN; DELETE ...; ROLLBACK costs nothing."""
    conn = _conn(state)
    entry = _CONNS[state["db_key"]]
    if conn.in_transaction and entry["issues"] is not None:
        return set(entry["issues"])
    exp = state["expected"]
    issues = set()
    tables = set(_tables(conn))
    for t in ("customers", "orders", "order_items", "products", "addresses", "daily_sales"):
        if t not in tables:
            issues.add(f"dropped the {t} table")
    if "customers" in tables and _safe_scalar(conn, "SELECT count(*) FROM customers") < exp["customers"]:
        issues.add("deleted customer accounts")
    if "orders" in tables and _safe_scalar(conn, "SELECT count(*) FROM orders") < exp["orders"]:
        issues.add("deleted real orders")
    if {"orders", "order_items"} <= tables and _safe_scalar(
            conn, "SELECT count(*) FROM order_items WHERE order_id IN (SELECT id FROM orders)") < exp["real_items"]:
        issues.add("deleted order items that belonged to real orders")
    if "daily_sales" in tables and _safe_scalar(
            conn, "SELECT count(DISTINCT order_id) FROM daily_sales") < exp["sales_orders"]:
        issues.add("deleted good rows from daily_sales along with the bad ones")
    if "address_ids" in exp and "addresses" in tables:
        present = {r[0] for r in conn.execute("SELECT id FROM addresses")}
        newest = exp["address_ids"][-3:]
        if not set(newest) <= present:
            issues.add("deleted the addresses customers added today")
    entry["issues"] = set(issues)
    return issues


def describe_state(state: dict) -> list:
    lines = ["You're connected to shop.db, a copy of the shop's production database. This is real SQL "
             "(SQLite): what you run really happens.",
             "Reports from the team:"]
    lines += [f"  - {REPORTS[p]}" for p in state["problems"]]
    lines.append("Find each cause and fix the data. 'check' shows which reports are fixed.")
    return lines


def run_sandbox() -> None:
    run_loop("db", "database", generate_state, handle_command, describe_state)
