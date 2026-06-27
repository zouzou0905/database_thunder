"""Quick database lock / connection debug helper."""
from __future__ import annotations

import psycopg
import os
import time

DB = os.environ.get("DATABASE_URL", "postgresql://keyword_user:keyword_password@localhost:5432/keyword_trends")

conn = psycopg.connect(DB, options="-c statement_timeout=5000")
conn.autocommit = True

print("=== pg_stat_activity ===")
with conn.cursor() as cur:
    cur.execute("""
        SELECT pid, state, wait_event_type, wait_event,
               EXTRACT(EPOCH FROM now() - query_start)::int AS s,
               pg_blocking_pids(pid) AS blocked_by,
               LEFT(query, 250) AS q
        FROM pg_stat_activity
        WHERE state != 'idle' AND pid != pg_backend_pid()
        ORDER BY query_start
    """)
    rows = cur.fetchall()
    if not rows:
        print("  No active queries (clean)")
    for r in rows:
        print(f"  PID={r[0]} state={r[1]} wait={r[2]}/{r[3]} running={r[4]}s blocked_by={r[5]}")
        print(f"    Q: {r[6][:200]}")

print("\n=== pg_locks (exclusive only) ===")
with conn.cursor() as cur:
    cur.execute("""
        SELECT l.pid, l.mode, l.locktype, l.relation::regclass::text AS rel,
               l.granted, a.state, LEFT(a.query, 120) AS q
        FROM pg_locks l
        LEFT JOIN pg_stat_activity a ON a.pid = l.pid
        WHERE NOT l.granted
           OR l.mode IN ('AccessExclusiveLock', 'ExclusiveLock')
        ORDER BY l.granted, l.pid
        LIMIT 30
    """)
    rows = cur.fetchall()
    if not rows:
        print("  No problematic locks")
    for r in rows:
        print(f"  PID={r[0]} mode={r[1]} type={r[2]} rel={r[3]} granted={r[4]} state={r[5]}")
        if r[6]:
            print(f"    Q: {r[6][:120]}")

print("\n=== Quick cache table query ===")
with conn.cursor() as cur:
    try:
        t0 = time.perf_counter()
        cur.execute("SELECT COUNT(*) FROM keyword_selection_candidates_monthly WHERE marketplace = 'UK'")
        cnt = cur.fetchone()[0]
        print(f"  COUNT UK: {cnt} rows, {time.perf_counter()-t0:.3f}s")
    except Exception as exc:
        print(f"  FAILED: {exc}")

conn.close()
print("Done")
