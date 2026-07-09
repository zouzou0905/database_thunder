"""Quick speed comparison after ANALYZE."""
import sys, time
sys.path.insert(0, r"D:\database\database_thunder-main\backend")
from app.pool import get_pool
from psycopg.rows import dict_row

conn = get_pool().getconn()
conn.autocommit = True
conn.row_factory = dict_row
cur = conn.cursor()

baseline = {
    "metrics count UK": 0.208,
    "candidate count": 12.853,
    "snapshot count UK": 1.077,
}

tests = [
    ("metrics count UK", "SELECT count(*) FROM keyword_monthly_metrics WHERE marketplace = 'UK'"),
    ("candidate count", "SELECT count(*) FROM keyword_selection_candidates_monthly WHERE marketplace = 'UK' AND is_product_selection_candidate = true"),
    ("snapshot count UK", "SELECT count(*) FROM keyword_compare_snapshot WHERE marketplace = 'UK'"),
    ("monthly trends count UK", "SELECT count(*) FROM keyword_monthly_trends WHERE marketplace = 'UK'"),
]

print(f"{'Query':40s} {'Before':>8s}  {'After':>8s}  {'Change':>8s}")
print("-" * 70)

for label, sql in tests:
    t0 = time.time()
    cur.execute(sql)
    elapsed = time.time() - t0
    before = baseline.get(label)
    if before:
        change = f"{(elapsed/before - 1)*100:+.0f}%"
        print(f"{label:40s} {before:>7.3f}s  {elapsed:>7.3f}s  {change:>8s}")
    else:
        print(f"{label:40s} {'N/A':>8s}  {elapsed:>7.3f}s")

get_pool().putconn(conn)
