"""Baseline measurement before optimization — saves to baseline.json"""
from __future__ import annotations
import sys, json, time
from datetime import datetime, timezone
sys.path.insert(0, r"D:\database\database_thunder-main\backend")
from psycopg.rows import dict_row
from app.pool import get_pool

conn = get_pool().getconn()
conn.autocommit = True
conn.row_factory = dict_row
cur = conn.cursor()

baseline = {"timestamp": datetime.now(timezone.utc).isoformat(), "measurements": {}}

# 1. Index scan counts
print("1/5 Recording index scan counts...")
cur.execute("""
    SELECT relname, indexrelname,
           pg_size_pretty(pg_relation_size(indexrelid)) AS idx_size,
           idx_scan, idx_tup_read, idx_tup_fetch
    FROM pg_stat_user_indexes
    WHERE schemaname = 'public' AND idx_scan > 0
    ORDER BY pg_relation_size(indexrelid) DESC
""")
baseline["measurements"]["active_indexes"] = cur.fetchall()
print(f"   Indexes with scans > 0: {len(baseline['measurements']['active_indexes'])}")

# 2. Table sizes + dead tuples
print("2/5 Recording table stats...")
cur.execute("""
    SELECT relname, n_live_tup, n_dead_tup,
           pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
           last_autovacuum, last_autoanalyze
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY pg_total_relation_size(relid) DESC
""")
baseline["measurements"]["tables"] = cur.fetchall()

# 3. Test a simple count query (warm cache)
print("3/5 Testing simple query speed...")
t0 = time.time()
cur.execute("SELECT count(*) FROM keyword_monthly_metrics WHERE marketplace = 'UK'")
elapsed = time.time() - t0
baseline["measurements"]["simple_count_query_s"] = round(elapsed, 3)
print(f"   count(*) metrics UK: {elapsed:.3f}s")

# 4. Test candidate query (cached)
print("4/5 Testing candidate query speed...")
t0 = time.time()
cur.execute("""
    SELECT count(*) FROM keyword_selection_candidates_monthly
    WHERE marketplace = 'UK' AND is_product_selection_candidate = true
""")
elapsed = time.time() - t0
baseline["measurements"]["cached_candidate_count_s"] = round(elapsed, 3)
print(f"   candidate count: {elapsed:.3f}s")

# 5. Test compare snapshot query
print("5/5 Testing compare snapshot query speed...")
t0 = time.time()
cur.execute("""
    SELECT count(*) FROM keyword_compare_snapshot
    WHERE marketplace = 'UK'
""")
elapsed = time.time() - t0
baseline["measurements"]["snapshot_count_s"] = round(elapsed, 3)
print(f"   snapshot count UK: {elapsed:.3f}s")

# 6. Range cache row count
cur.execute("SELECT count(*) AS c FROM keyword_compare_range_cache")
baseline["measurements"]["range_cache_rows"] = cur.fetchone()["c"]
print(f"   range_cache rows: {baseline['measurements']['range_cache_rows']}")

# Save
with open("data/reports/baseline_before_optimize.json", "w", encoding="utf-8") as f:
    json.dump(baseline, f, indent=2, default=str, ensure_ascii=False)
print(f"\nBaseline saved to data/reports/baseline_before_optimize.json")

get_pool().putconn(conn)
