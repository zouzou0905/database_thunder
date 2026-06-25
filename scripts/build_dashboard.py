from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from common import get_database_url


DEFAULT_OUTPUT = "dashboard/keyword_dashboard.html"


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m")
    return value


def fetch_all(conn: psycopg.Connection, sql: str, params: dict | None = None) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or {})
        return list(cur.fetchall())


def load_dashboard_data(marketplace: str, limit: int) -> dict[str, Any]:
    with psycopg.connect(get_database_url()) as conn:
        month_summary = fetch_all(
            conn,
            """
            SELECT
                analysis_month,
                COUNT(*) AS total_keywords,
                COUNT(*) FILTER (WHERE trend_label = 'new') AS new_keywords,
                COUNT(*) FILTER (WHERE trend_label = 'rising') AS rising_keywords,
                COUNT(*) FILTER (WHERE trend_label = 'falling') AS falling_keywords,
                ROUND(AVG(opportunity_score), 2) AS avg_opportunity,
                ROUND(AVG(conversion_score), 2) AS avg_conversion,
                ROUND(SUM(search_volume), 0) AS total_search_volume
            FROM keyword_ops_monthly
            WHERE marketplace = %(marketplace)s
            GROUP BY analysis_month
            ORDER BY analysis_month
            """,
            {"marketplace": marketplace},
        )
        trend_counts = fetch_all(
            conn,
            """
            SELECT analysis_month, trend_label, COUNT(*) AS count
            FROM keyword_ops_monthly
            WHERE marketplace = %(marketplace)s
            GROUP BY analysis_month, trend_label
            ORDER BY analysis_month, trend_label
            """,
            {"marketplace": marketplace},
        )
        category_summary = fetch_all(
            conn,
            """
            WITH ranked AS (
                SELECT
                    analysis_month,
                    COALESCE(NULLIF(category, ''), '-') AS category,
                    COUNT(*) AS keywords,
                    ROUND(AVG(opportunity_score), 2) AS avg_opportunity,
                    ROW_NUMBER() OVER (
                        PARTITION BY analysis_month
                        ORDER BY COUNT(*) DESC
                    ) AS rn
                FROM keyword_ops_monthly
                WHERE marketplace = %(marketplace)s
                GROUP BY analysis_month, COALESCE(NULLIF(category, ''), '-')
            )
            SELECT analysis_month, category, keywords, avg_opportunity
            FROM ranked
            WHERE rn <= 10
            ORDER BY analysis_month, keywords DESC
            """,
            {"marketplace": marketplace},
        )
        keywords = fetch_all(
            conn,
            """
            WITH ranked AS (
                SELECT
                    o.keyword,
                    m.keyword_translation,
                    o.analysis_month,
                    o.category,
                    o.search_rank,
                    o.search_volume,
                    o.click_share,
                    o.conversion_share,
                    o.rank_change_mom,
                    o.volume_growth_rate_mom,
                    o.trend_label,
                    o.keyword_level,
                    o.opportunity_score,
                    o.conversion_score,
                    o.recommended_action,
                    ROW_NUMBER() OVER (
                        PARTITION BY o.analysis_month
                        ORDER BY o.opportunity_score DESC NULLS LAST, o.search_volume DESC NULLS LAST
                    ) AS rn
                FROM keyword_ops_monthly o
                LEFT JOIN keyword_monthly_metrics m
                  ON m.keyword_id = o.keyword_id
                 AND m.data_month = o.analysis_month
                 AND m.marketplace = o.marketplace
                WHERE o.marketplace = %(marketplace)s
                  AND o.opportunity_score IS NOT NULL
            )
            SELECT
                keyword,
                keyword_translation,
                analysis_month,
                category,
                search_rank,
                search_volume,
                click_share,
                conversion_share,
                rank_change_mom,
                volume_growth_rate_mom,
                trend_label,
                keyword_level,
                opportunity_score,
                conversion_score,
                recommended_action
            FROM ranked
            WHERE rn <= %(limit)s
            ORDER BY analysis_month, opportunity_score DESC NULLS LAST
            """,
            {"marketplace": marketplace, "limit": limit},
        )
        rising = fetch_all(
            conn,
            """
            WITH ranked AS (
                SELECT
                    o.keyword,
                    m.keyword_translation,
                    o.analysis_month,
                    o.category,
                    o.search_rank,
                    o.search_volume,
                    o.click_share,
                    o.conversion_share,
                    o.rank_change_mom,
                    o.volume_growth_rate_mom,
                    o.trend_label,
                    o.opportunity_score,
                    o.recommended_action,
                    ROW_NUMBER() OVER (
                        PARTITION BY o.analysis_month
                        ORDER BY o.opportunity_score DESC NULLS LAST, o.search_volume DESC NULLS LAST
                    ) AS rn
                FROM keyword_ops_monthly o
                LEFT JOIN keyword_monthly_metrics m
                  ON m.keyword_id = o.keyword_id
                 AND m.data_month = o.analysis_month
                 AND m.marketplace = o.marketplace
                WHERE o.marketplace = %(marketplace)s
                  AND o.trend_label = 'rising'
            )
            SELECT
                keyword,
                keyword_translation,
                analysis_month,
                category,
                search_rank,
                search_volume,
                click_share,
                conversion_share,
                rank_change_mom,
                volume_growth_rate_mom,
                trend_label,
                opportunity_score,
                recommended_action
            FROM ranked
            WHERE rn <= %(limit)s
            ORDER BY analysis_month, opportunity_score DESC NULLS LAST
            """,
            {"marketplace": marketplace, "limit": limit},
        )
        falling = fetch_all(
            conn,
            """
            WITH ranked AS (
                SELECT
                    o.keyword,
                    m.keyword_translation,
                    o.analysis_month,
                    o.category,
                    o.search_rank,
                    o.search_volume,
                    o.click_share,
                    o.conversion_share,
                    o.rank_change_mom,
                    o.volume_growth_rate_mom,
                    o.trend_label,
                    o.opportunity_score,
                    o.recommended_action,
                    ROW_NUMBER() OVER (
                        PARTITION BY o.analysis_month
                        ORDER BY o.opportunity_score DESC NULLS LAST, o.search_volume DESC NULLS LAST
                    ) AS rn
                FROM keyword_ops_monthly o
                LEFT JOIN keyword_monthly_metrics m
                  ON m.keyword_id = o.keyword_id
                 AND m.data_month = o.analysis_month
                 AND m.marketplace = o.marketplace
                WHERE o.marketplace = %(marketplace)s
                  AND o.trend_label = 'falling'
            )
            SELECT
                keyword,
                keyword_translation,
                analysis_month,
                category,
                search_rank,
                search_volume,
                click_share,
                conversion_share,
                rank_change_mom,
                volume_growth_rate_mom,
                trend_label,
                opportunity_score,
                recommended_action
            FROM ranked
            WHERE rn <= %(limit)s
            ORDER BY analysis_month, opportunity_score DESC NULLS LAST
            """,
            {"marketplace": marketplace, "limit": limit},
        )
    return {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "marketplace": marketplace,
        "monthSummary": month_summary,
        "trendCounts": trend_counts,
        "categorySummary": category_summary,
        "keywords": keywords,
        "rising": rising,
        "falling": falling,
    }


def build_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=json_default)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>关键词趋势运营看板</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #667085;
      --line: #dde2ea;
      --green: #16835b;
      --red: #b42318;
      --amber: #b54708;
      --blue: #155eef;
      --teal: #0e9384;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Arial, "Microsoft YaHei", sans-serif;
      font-size: 14px;
    }}
    header {{
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 18px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      line-height: 1.3;
      letter-spacing: 0;
    }}
    .subtle {{ color: var(--muted); }}
    .shell {{
      max-width: 1500px;
      margin: 0 auto;
      padding: 22px 28px 36px;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: minmax(240px, 1fr) 170px 170px 170px;
      gap: 12px;
      margin-bottom: 18px;
      align-items: end;
    }}
    label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    input, select {{
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      padding: 8px 10px;
      border-radius: 6px;
      font: inherit;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 108px;
    }}
    .metric .label {{ color: var(--muted); font-size: 12px; }}
    .metric .value {{ margin-top: 10px; font-size: 26px; font-weight: 700; }}
    .metric .note {{ margin-top: 12px; color: var(--muted); font-size: 12px; }}
    .grid {{
      display: grid;
      grid-template-columns: 1.1fr .9fr;
      gap: 16px;
      margin-bottom: 18px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .panel h2 {{
      margin: 0 0 12px;
      font-size: 16px;
      letter-spacing: 0;
    }}
    .bars {{ display: grid; gap: 10px; }}
    .bar-row {{
      display: grid;
      grid-template-columns: 92px 1fr 72px;
      gap: 10px;
      align-items: center;
    }}
    .bar {{
      height: 10px;
      background: #eef1f5;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar > span {{
      display: block;
      height: 100%;
      background: var(--blue);
      border-radius: 999px;
    }}
    .trend-pill {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 68px;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 12px;
      font-weight: 700;
    }}
    .new {{ color: var(--blue); background: #eaf0ff; }}
    .rising {{ color: var(--green); background: #e9f7ef; }}
    .falling {{ color: var(--red); background: #fff0ee; }}
    .stable {{ color: var(--muted); background: #f2f4f7; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: middle;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      background: #fbfcfd;
    }}
    tbody tr:hover {{ background: #f9fafb; }}
    .keyword-cell {{ font-weight: 700; white-space: normal; line-height: 1.35; }}
    .translation {{ margin-top: 3px; color: var(--muted); font-size: 12px; font-weight: 400; }}
    .code-label {{ margin-left: 4px; color: var(--muted); font-size: 11px; font-weight: 400; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .tabs {{
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }}
    button {{
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      padding: 8px 11px;
      cursor: pointer;
      font: inherit;
    }}
    button.active {{
      border-color: #155eef;
      background: #eef4ff;
      color: #155eef;
      font-weight: 700;
    }}
    .warning {{
      border-left: 4px solid var(--amber);
      background: #fff7ed;
      color: #7a2e0e;
      padding: 10px 12px;
      border-radius: 6px;
      margin-bottom: 16px;
    }}
    @media (max-width: 980px) {{
      .toolbar, .summary-grid, .grid {{ grid-template-columns: 1fr; }}
      header {{ align-items: flex-start; flex-direction: column; }}
      .shell {{ padding: 16px; }}
      th:nth-child(4), td:nth-child(4),
      th:nth-child(6), td:nth-child(6) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>关键词趋势运营看板</h1>
      <div class="subtle">Marketplace: <span id="marketplace"></span> · 生成时间: <span id="generatedAt"></span></div>
    </div>
    <div class="subtle">数据源：PostgreSQL / keyword_ops_monthly</div>
  </header>

  <main class="shell">
    <div class="warning">当前是本地试用看板。若某个月数据明显偏少，该月趋势只能作为样例观察，不建议直接做运营结论。</div>

    <section class="toolbar">
      <div>
        <label for="searchInput">关键词搜索</label>
        <input id="searchInput" placeholder="输入关键词、类目或动作">
      </div>
      <div>
        <label for="monthSelect">分析月份</label>
        <select id="monthSelect"></select>
      </div>
      <div>
        <label for="trendSelect">趋势</label>
        <select id="trendSelect">
          <option value="">全部趋势</option>
          <option value="new">新词 new</option>
          <option value="rising">上升 rising</option>
          <option value="falling">下滑 falling</option>
          <option value="stable">稳定 stable</option>
        </select>
      </div>
      <div>
        <label for="scoreSelect">机会分</label>
        <select id="scoreSelect">
          <option value="0">全部</option>
          <option value="60">>= 60</option>
          <option value="70">>= 70</option>
          <option value="80">>= 80</option>
          <option value="90">>= 90</option>
        </select>
      </div>
    </section>

    <section class="summary-grid" id="summaryGrid"></section>

    <section class="grid">
      <div class="panel">
        <h2>月份规模与趋势分布</h2>
        <div class="bars" id="trendBars"></div>
      </div>
      <div class="panel">
        <h2>类目关键词分布 Top 10</h2>
        <div class="bars" id="categoryBars"></div>
      </div>
    </section>

    <section class="panel">
      <div class="tabs">
        <button class="active" data-list="keywords">机会词</button>
        <button data-list="rising">上升词</button>
        <button data-list="falling">下滑词</button>
      </div>
      <table>
        <thead>
          <tr>
            <th style="width: 26%">关键词 / 中文释义</th>
            <th style="width: 10%">月份</th>
            <th class="num" style="width: 10%">排名</th>
            <th class="num" style="width: 11%">搜索量</th>
            <th style="width: 10%">趋势</th>
            <th style="width: 16%">类目</th>
            <th class="num" style="width: 9%">机会分</th>
            <th style="width: 8%">动作</th>
          </tr>
        </thead>
        <tbody id="keywordRows"></tbody>
      </table>
    </section>
  </main>

  <script>
    const dashboardData = {payload};
    let activeList = 'keywords';

    const fmt = new Intl.NumberFormat('zh-CN');
    const pct = new Intl.NumberFormat('zh-CN', {{ style: 'percent', maximumFractionDigits: 1 }});
    const trendLabels = {{
      new: '新词',
      rising: '上升',
      falling: '下滑',
      stable: '稳定',
      volatile: '波动',
      disappeared: '消失',
      seasonal_candidate: '疑似季节词'
    }};
    const actionLabels = {{
      add_to_ads: '加广告',
      increase_budget: '提预算',
      decrease_budget: '降预算',
      add_to_listing: '加入Listing',
      add_to_watchlist: '加入关注',
      observe: '观察',
      discard: '淘汰'
    }};

    function trendLabel(value) {{
      return trendLabels[value] || value || '-';
    }}

    function actionLabel(value) {{
      return actionLabels[value] || value || '-';
    }}

    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, char => ({{
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }}[char]));
    }}

    function monthLabel(value) {{
      return String(value).slice(0, 7);
    }}

    function clsTrend(value) {{
      return ['new', 'rising', 'falling', 'stable'].includes(value) ? value : 'stable';
    }}

    function getMonths() {{
      return dashboardData.monthSummary.map(row => monthLabel(row.analysis_month));
    }}

    function currentMonth() {{
      return document.getElementById('monthSelect').value;
    }}

    function rowMonth(row) {{
      return monthLabel(row.analysis_month);
    }}

    function renderMonthSelect() {{
      const select = document.getElementById('monthSelect');
      const months = getMonths();
      select.innerHTML = months.map(month => `<option value="${{month}}">${{month}}</option>`).join('');
      select.value = months[months.length - 1] || '';
    }}

    function renderSummary() {{
      const month = currentMonth();
      const row = dashboardData.monthSummary.find(item => monthLabel(item.analysis_month) === month) || {{}};
      const items = [
        ['关键词数', fmt.format(row.total_keywords || 0), '去重后的月度指标数量'],
        ['上升词', fmt.format(row.rising_keywords || 0), '与上月相比排名或搜索量提升'],
        ['下滑词', fmt.format(row.falling_keywords || 0), '与上月相比排名或搜索量下降'],
        ['平均机会分', row.avg_opportunity ?? '-', '用于运营优先级筛选']
      ];
      document.getElementById('summaryGrid').innerHTML = items.map(item => `
        <div class="metric">
          <div class="label">${{item[0]}}</div>
          <div class="value">${{item[1]}}</div>
          <div class="note">${{item[2]}}</div>
        </div>
      `).join('');
    }}

    function renderTrendBars() {{
      const month = currentMonth();
      const rows = dashboardData.trendCounts.filter(row => monthLabel(row.analysis_month) === month);
      const max = Math.max(...rows.map(row => row.count), 1);
      document.getElementById('trendBars').innerHTML = rows.map(row => `
        <div class="bar-row">
          <span class="trend-pill ${{clsTrend(row.trend_label)}}">${{trendLabel(row.trend_label)}}<span class="code-label">${{row.trend_label}}</span></span>
          <div class="bar"><span style="width: ${{Math.max(2, row.count / max * 100)}}%"></span></div>
          <span class="num">${{fmt.format(row.count)}}</span>
        </div>
      `).join('');
    }}

    function renderCategoryBars() {{
      const month = currentMonth();
      const rows = dashboardData.categorySummary.filter(row => monthLabel(row.analysis_month) === month);
      const max = Math.max(...rows.map(row => row.keywords), 1);
      document.getElementById('categoryBars').innerHTML = rows.map(row => `
        <div class="bar-row">
          <span title="${{escapeHtml(row.category)}}">${{escapeHtml(row.category)}}</span>
          <div class="bar"><span style="width: ${{Math.max(2, row.keywords / max * 100)}}%; background: var(--teal)"></span></div>
          <span class="num">${{fmt.format(row.keywords)}}</span>
        </div>
      `).join('');
    }}

    function filteredRows() {{
      const q = document.getElementById('searchInput').value.trim().toLowerCase();
      const month = currentMonth();
      const trend = document.getElementById('trendSelect').value;
      const score = Number(document.getElementById('scoreSelect').value);
      return dashboardData[activeList]
        .filter(row => rowMonth(row) === month)
        .filter(row => !trend || row.trend_label === trend)
        .filter(row => Number(row.opportunity_score || 0) >= score)
        .filter(row => {{
          if (!q) return true;
          const text = [
            row.keyword,
            row.keyword_translation,
            row.category,
            row.recommended_action,
            actionLabel(row.recommended_action),
            row.trend_label,
            trendLabel(row.trend_label)
          ].join(' ').toLowerCase();
          return text.includes(q);
        }})
        .slice(0, 120);
    }}

    function renderRows() {{
      const rows = filteredRows();
      document.getElementById('keywordRows').innerHTML = rows.map(row => `
        <tr>
          <td class="keyword-cell" title="${{escapeHtml((row.keyword || '') + ' ' + (row.keyword_translation || ''))}}">
            <div>${{escapeHtml(row.keyword || '-')}}</div>
            <div class="translation">${{escapeHtml(row.keyword_translation || '暂无中文释义')}}</div>
          </td>
          <td>${{rowMonth(row)}}</td>
          <td class="num">${{row.search_rank ? fmt.format(row.search_rank) : '-'}}</td>
          <td class="num">${{row.search_volume ? fmt.format(row.search_volume) : '-'}}</td>
          <td><span class="trend-pill ${{clsTrend(row.trend_label)}}">${{trendLabel(row.trend_label)}}<span class="code-label">${{row.trend_label || ''}}</span></span></td>
          <td title="${{escapeHtml(row.category || '')}}">${{escapeHtml(row.category || '-')}}</td>
          <td class="num">${{row.opportunity_score == null ? '-' : Number(row.opportunity_score).toFixed(1)}}</td>
          <td title="${{escapeHtml(row.recommended_action || '')}}">${{escapeHtml(actionLabel(row.recommended_action))}}</td>
        </tr>
      `).join('') || `<tr><td colspan="8" class="subtle">没有匹配的数据</td></tr>`;
    }}

    function renderAll() {{
      renderSummary();
      renderTrendBars();
      renderCategoryBars();
      renderRows();
    }}

    document.getElementById('marketplace').textContent = dashboardData.marketplace;
    document.getElementById('generatedAt').textContent = dashboardData.generatedAt;
    renderMonthSelect();
    renderAll();

    ['monthSelect', 'trendSelect', 'scoreSelect', 'searchInput'].forEach(id => {{
      document.getElementById(id).addEventListener('input', renderAll);
    }});
    document.querySelectorAll('[data-list]').forEach(button => {{
      button.addEventListener('click', () => {{
        document.querySelectorAll('[data-list]').forEach(item => item.classList.remove('active'));
        button.classList.add('active');
        activeList = button.dataset.list;
        renderRows();
      }});
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a static keyword operations dashboard from PostgreSQL data.")
    parser.add_argument("--marketplace", default="UK")
    parser.add_argument("--limit", type=int, default=1000, help="Keyword rows to embed for each list.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data = load_dashboard_data(args.marketplace, args.limit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(data), encoding="utf-8-sig")
    print(f"Dashboard generated: {output.resolve()}")


if __name__ == "__main__":
    main()
