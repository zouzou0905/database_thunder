"""Run VACUUM ANALYZE on entire database with progress reporting."""
from __future__ import annotations
import sys, time
sys.path.insert(0, r"D:\database\database_thunder-main\backend")
from app.core.config import get_settings
import psycopg

settings = get_settings()
conn = psycopg.connect(settings.database_url)
conn.autocommit = True
cur = conn.cursor()

print(f"Starting VACUUM ANALYZE at {time.strftime('%H:%M:%S')}...")
print("This will reclaim dead tuples and update planner statistics.")
print("Expected: 10–20 minutes for 25 GB database.\n")

t0 = time.time()
try:
    cur.execute("VACUUM ANALYZE")
    elapsed = time.time() - t0
    print(f"\nVACUUM ANALYZE completed in {elapsed/60:.1f} minutes ({elapsed:.0f}s)")
except Exception as e:
    elapsed = time.time() - t0
    print(f"\nVACUUM ANALYZE FAILED after {elapsed/60:.1f} minutes: {e}")
    sys.exit(1)

# Verify statistics are now populated
print("\nVerifying statistics...")
cur.execute("""
    SELECT relname, last_autoanalyze, n_live_tup, n_dead_tup
    FROM pg_stat_user_tables
    WHERE schemaname = 'public' AND relname LIKE 'keyword_%'
    ORDER BY relname
""")
for r in cur.fetchall():
    print(f"  {r[0]:45s} analyze={str(r[1])[:19]}  live={r[2]:>10,}  dead={r[3]:>6,}")

conn.close()
print("\nDone.")
