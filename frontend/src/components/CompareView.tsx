import {
  ArrowDownAZ,
  Check,
  Columns,
  GitCompareArrows,
  Search,
  Shield,
  Star,
  X,
} from "lucide-react";
import { useMemo, useRef, useState, useEffect } from "react";
import { createPortal } from "react-dom";
import type { CategoryItem, KeywordCompareFilters, KeywordCompareItem, MonthItem, Pagination as PaginationType } from "../types";
import { formatGrowthPercent, formatNumber, formatPercent, formatMonth, statusLabel } from "../utils";
import { AppleSelect } from "./AppleSelect";
import type { SelectOption } from "./AppleSelect";
import { Field } from "./Field";
import { Metric } from "./Metric";
import { Pagination } from "./Pagination";
import { Sparkline } from "./Sparkline";
import { Tag } from "./Tag";

const COMPARE_COLUMN_DEFS = [
  { key: "category" as const, label: "类目", defaultVisible: true },
  { key: "sparkline" as const, label: "趋势图", defaultVisible: true },
  { key: "end_search_volume" as const, label: "末月搜索量", defaultVisible: true },
  { key: "search_volume_change" as const, label: "搜索量增量", defaultVisible: true },
  { key: "growth_rate" as const, label: "增长率", defaultVisible: true },
  { key: "mom" as const, label: "环比", defaultVisible: true },
  { key: "yoy" as const, label: "同比", defaultVisible: true },
  { key: "rank_change" as const, label: "排名变化", defaultVisible: true },
  { key: "month_count" as const, label: "出现月数", defaultVisible: true },
  { key: "avg_search_volume" as const, label: "平均搜索量", defaultVisible: false },
  { key: "ppc" as const, label: "PPC", defaultVisible: true },
  { key: "spr" as const, label: "SPR", defaultVisible: true },
  { key: "trend_type" as const, label: "类型", defaultVisible: true },
  { key: "holiday" as const, label: "节日标签", defaultVisible: true },
  { key: "status" as const, label: "状态", defaultVisible: true },
  { key: "actions" as const, label: "操作", defaultVisible: true },
  { key: "history_rank" as const, label: "末月历史排名参考", defaultVisible: false },
  { key: "monthly_volume" as const, label: "月度搜索量", defaultVisible: false },
] as const;

type CompareColumnKey = (typeof COMPARE_COLUMN_DEFS)[number]["key"];
const COMPARE_VISIBLE_COLUMNS_STORAGE_KEY = "compare_visible_columns_v3";
const LEGACY_COMPARE_VISIBLE_COLUMNS_STORAGE_KEYS = [
  "compare_visible_columns_v2",
  "compare_visible_columns",
];

function defaultCompareVisibleColumns(): Set<CompareColumnKey> {
  return new Set(COMPARE_COLUMN_DEFS.filter((d) => d.defaultVisible).map((d) => d.key));
}

function normalizeCompareColumns(value: unknown, includeNewDefaults = false): Set<CompareColumnKey> | null {
  if (!Array.isArray(value)) return null;
  const validKeys = new Set(COMPARE_COLUMN_DEFS.map((d) => d.key));
  const next = new Set(value.filter((key): key is CompareColumnKey => validKeys.has(key as CompareColumnKey)));
  if (includeNewDefaults) {
    COMPARE_COLUMN_DEFS.forEach((col) => {
      if (col.defaultVisible) next.add(col.key);
    });
  }
  return next.size > 0 ? next : null;
}

function loadCompareVisibleColumns(): Set<CompareColumnKey> {
  try {
    const stored = localStorage.getItem(COMPARE_VISIBLE_COLUMNS_STORAGE_KEY);
    if (stored) {
      const columns = normalizeCompareColumns(JSON.parse(stored));
      if (columns) return columns;
    }
    for (const key of LEGACY_COMPARE_VISIBLE_COLUMNS_STORAGE_KEYS) {
      const legacyStored = localStorage.getItem(key);
      if (legacyStored) {
        const columns = normalizeCompareColumns(JSON.parse(legacyStored), true);
        if (columns) return columns;
      }
    }
  } catch { /* ignore */ }
  return defaultCompareVisibleColumns();
}

const statusOptions: SelectOption[] = [
  { value: "new", label: "新候选" },
  { value: "watching", label: "观察中" },
  { value: "researching", label: "调研中" },
  { value: "rejected", label: "已放弃" },
  { value: "approved", label: "进入开发" },
  { value: "launched", label: "已上架" },
];

interface CompareViewProps {
  compareFilters: KeywordCompareFilters;
  updateCompareFilter: <K extends keyof KeywordCompareFilters>(key: K, value: KeywordCompareFilters[K]) => void;
  setCompareFilters: React.Dispatch<React.SetStateAction<KeywordCompareFilters>>;
  months: MonthItem[];
  categories: CategoryItem[];
  compareItems: KeywordCompareItem[];
  compareMonths: string[];
  comparePagination: PaginationType;
  compareLoading: boolean;
  compareError: string;
  comparePageJump: string;
  setComparePageJump: (value: string) => void;
  compareTrendOptions: SelectOption[];
  compareSortOptions: SelectOption[];
  onLoadData: () => void;
  onChangeState: (item: KeywordCompareItem, status: string) => void;
  onToggleFavorite: (item: KeywordCompareItem) => void;
  onAddExclusion: (item: KeywordCompareItem) => void;
}

export function CompareView({
  compareFilters,
  updateCompareFilter,
  setCompareFilters,
  months,
  categories,
  compareItems,
  compareMonths,
  comparePagination,
  compareLoading,
  compareError,
  comparePageJump,
  setComparePageJump,
  compareTrendOptions,
  compareSortOptions,
  onLoadData,
  onChangeState,
  onToggleFavorite,
  onAddExclusion,
}: CompareViewProps) {
  // Column visibility state (local to CompareView)
  const [visibleColumns, setVisibleColumns] = useState<Set<CompareColumnKey>>(loadCompareVisibleColumns);
  const [columnPanelOpen, setColumnPanelOpen] = useState(false);
  const [columnPanelPosition, setColumnPanelPosition] = useState<{ top: number; right: number } | null>(null);
  const [draftColumns, setDraftColumns] = useState<Set<CompareColumnKey>>(new Set(visibleColumns));
  const columnToggleRef = useRef<HTMLButtonElement>(null);
  const columnPanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!columnPanelOpen) return;
    function onMouseDown(e: MouseEvent) {
      const target = e.target as Node;
      if (
        columnPanelRef.current &&
        columnToggleRef.current &&
        !columnPanelRef.current.contains(target) &&
        !columnToggleRef.current.contains(target)
      ) {
        setColumnPanelOpen(false);
      }
    }
    function onReposition() {
      const rect = columnToggleRef.current?.getBoundingClientRect();
      if (!rect) return;
      setColumnPanelPosition({
        top: rect.bottom + 8,
        right: Math.max(window.innerWidth - rect.right, 12),
      });
    }
    document.addEventListener("mousedown", onMouseDown);
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    onReposition();
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [columnPanelOpen]);

  const compareSummary = useMemo(() => {
    const avgEndSearchVolume =
      compareItems.length === 0
        ? 0
        : compareItems.reduce((sum, item) => sum + (item.end_search_volume ?? 0), 0) / compareItems.length;
    const avgGrowthRate =
      compareItems.length === 0
        ? 0
        : compareItems.reduce((sum, item) => sum + (item.search_volume_growth_rate ?? 0), 0) / compareItems.length;
    const continuousRate =
      compareItems.length === 0
        ? 0
        : compareItems.filter((item) => item.month_count === item.total_months).length / compareItems.length;
    return { avgEndSearchVolume, avgGrowthRate, continuousRate };
  }, [compareItems]);

  const compareTableMinWidth = useMemo(() => {
    const COL_WIDTHS: Record<CompareColumnKey, number> = {
      category: 180, sparkline: 140, end_search_volume: 100, search_volume_change: 100,
      growth_rate: 100, rank_change: 100, month_count: 80, avg_search_volume: 110, ppc: 80, spr: 80,
      trend_type: 80, holiday: 130, mom: 110, yoy: 110, history_rank: 240, status: 120, actions: 80, monthly_volume: 0,
    };
    let w = 280;
    for (const col of COMPARE_COLUMN_DEFS) {
      if (visibleColumns.has(col.key)) w += COL_WIDTHS[col.key];
    }
    if (visibleColumns.has("monthly_volume")) {
      w += (compareMonths.length || 6) * 72;
    }
    return w;
  }, [visibleColumns, compareMonths.length]);

  const compareTotalPrefix =
    comparePagination.total_label === "lower_bound"
      ? "至少 "
      : comparePagination.total_is_estimated
        ? "约 "
        : "";

  function submitComparePageJump(event: React.FormEvent) {
    event.preventDefault();
    const parsed = Number.parseInt(comparePageJump, 10);
    if (Number.isNaN(parsed)) {
      setComparePageJump(String(compareFilters.page));
      return;
    }
    const maxPage = Math.max(comparePagination.total_pages, 1);
    const targetPage = Math.min(Math.max(parsed, 1), maxPage);
    updateCompareFilter("page", targetPage);
    setComparePageJump(String(targetPage));
  }

  return (
    <section className="admin-grid">
      <section className="metric-grid">
        <Metric label="对比月份数" value={formatNumber(compareMonths.length)} />
        <Metric
          label={compareTotalPrefix ? "匹配关键词" : "总计关键词"}
          value={`${compareTotalPrefix}${formatNumber(comparePagination.total)}`}
        />
        <Metric
          label="当前页平均末月搜索量"
          value={compareItems.length ? formatNumber(compareSummary.avgEndSearchVolume) : "-"}
        />
        <Metric
          label="当前页平均增长率"
          value={compareItems.length ? formatGrowthPercent(compareSummary.avgGrowthRate) : "-"}
        />
        <Metric
          label="当前页连续出现占比"
          value={compareItems.length ? formatPercent(compareSummary.continuousRate) : "-"}
        />
      </section>

      <section className="filter-panel apple-panel">
        <div className="filter-title">
          <GitCompareArrows size={16} />
          横向对比条件
        </div>
        <div className="filter-grid">
          <Field label="起始月份">
            <AppleSelect
              value={compareFilters.start_month}
              options={months.map((item) => ({
                value: item.data_month.slice(0, 10),
                label: `${item.data_month.slice(0, 7)} / ${item.marketplace}`,
              }))}
              ariaLabel="起始月份"
              onChange={(value) => updateCompareFilter("start_month", value)}
            />
          </Field>
          <Field label="结束月份">
            <AppleSelect
              value={compareFilters.end_month}
              options={months.map((item) => ({
                value: item.data_month.slice(0, 10),
                label: `${item.data_month.slice(0, 7)} / ${item.marketplace}`,
              }))}
              ariaLabel="结束月份"
              onChange={(value) => updateCompareFilter("end_month", value)}
            />
          </Field>
          <Field label="关键词">
            <div className="input-icon">
              <Search size={15} />
              <input
                value={compareFilters.keyword}
                onChange={(event) =>
                  setCompareFilters((prev) => ({ ...prev, keyword: event.target.value }))
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter") updateCompareFilter("page", 1);
                }}
                placeholder="输入英文或中文"
              />
            </div>
          </Field>
          <Field label="类目">
            <AppleSelect
              value={compareFilters.category}
              options={[
                { value: "", label: "全部类目" },
                ...categories.slice(0, 160).map((item) => ({
                  value: item.category,
                  label: `${item.category} (${formatNumber(item.candidate_count)})`,
                })),
              ]}
              ariaLabel="类目"
              onChange={(value) => updateCompareFilter("category", value)}
            />
          </Field>
          <Field label="对比类型">
            <AppleSelect
              value={compareFilters.trend_type}
              options={compareTrendOptions}
              ariaLabel="对比类型"
              onChange={(value) => updateCompareFilter("trend_type", value)}
            />
          </Field>
          <Field label="末月搜索量">
            <div className="range-row">
              <input
                value={compareFilters.search_volume_min}
                onChange={(event) => updateCompareFilter("search_volume_min", event.target.value)}
              />
              <span>-</span>
              <input
                value={compareFilters.search_volume_max}
                onChange={(event) => updateCompareFilter("search_volume_max", event.target.value)}
              />
            </div>
          </Field>
          <Field label="增长率%">
            <div className="range-row">
              <input
                value={compareFilters.growth_rate_min}
                onChange={(event) => updateCompareFilter("growth_rate_min", event.target.value)}
              />
              <span>-</span>
              <input
                value={compareFilters.growth_rate_max}
                onChange={(event) => updateCompareFilter("growth_rate_max", event.target.value)}
              />
            </div>
          </Field>
          <Field label="出现月数">
            <div className="range-row">
              <input
                value={compareFilters.month_count_min}
                onChange={(event) => updateCompareFilter("month_count_min", event.target.value)}
                placeholder="最少"
              />
              <span>-</span>
              <input
                value={compareFilters.month_count_max}
                onChange={(event) => updateCompareFilter("month_count_max", event.target.value)}
                placeholder="最多"
              />
            </div>
          </Field>
          <Field label="PPC区间">
            <div className="range-row">
              <input
                value={compareFilters.ppc_min}
                onChange={(event) => updateCompareFilter("ppc_min", event.target.value)}
                placeholder="最低"
              />
              <span>-</span>
              <input
                value={compareFilters.ppc_max}
                onChange={(event) => updateCompareFilter("ppc_max", event.target.value)}
                placeholder="最高"
              />
            </div>
          </Field>
          <Field label="SPR区间">
            <div className="range-row">
              <input
                value={compareFilters.spr_min}
                onChange={(event) => updateCompareFilter("spr_min", event.target.value)}
                placeholder="最低"
              />
              <span>-</span>
              <input
                value={compareFilters.spr_max}
                onChange={(event) => updateCompareFilter("spr_max", event.target.value)}
                placeholder="最高"
              />
            </div>
          </Field>
          <Field label="排序">
            <AppleSelect
              value={compareFilters.sort_by}
              options={compareSortOptions}
              ariaLabel="排序"
              onChange={(value) => updateCompareFilter("sort_by", value)}
            />
          </Field>
        </div>
        <div className="filter-actions">
          <button
            className="button secondary"
            onClick={() =>
              setCompareFilters({
                ...compareFilters,
                keyword: "",
                category: "",
                trend_type: "",
                search_volume_min: "1000",
                search_volume_max: "",
                growth_rate_min: "",
                growth_rate_max: "",
                month_count_min: "",
                month_count_max: "",
                ppc_min: "",
                ppc_max: "",
                spr_min: "",
                spr_max: "",
                sort_by: "end_search_volume",
                sort_order: "desc",
                page: 1,
              })
            }
          >
            <X size={16} />
            重置
          </button>
          <button className="button primary" onClick={onLoadData}>
            <Search size={16} />
            查询
          </button>
        </div>
      </section>

      {compareError && <div className="alert">{compareError}</div>}

      <section className="table-shell compare-table-shell">
        <div className="table-toolbar">
          <div>
            <strong>同词横向对比清单</strong>
            <span>
              {compareTotalPrefix || "共 "}
              {formatNumber(comparePagination.total)} 条，当前第 {compareFilters.page} 页
            </span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div className="column-panel-wrapper">
              <button
                ref={columnToggleRef}
                className="column-toggle-btn"
                onClick={() => {
                  setDraftColumns(new Set(visibleColumns));
                  const rect = columnToggleRef.current?.getBoundingClientRect();
                  if (rect) {
                    setColumnPanelPosition({
                      top: rect.bottom + 8,
                      right: Math.max(window.innerWidth - rect.right, 12),
                    });
                  }
                  setColumnPanelOpen((prev) => !prev);
                }}
              >
                <Columns size={15} />
                列显示
              </button>
              {columnPanelOpen && columnPanelPosition &&
                createPortal(
                  <div
                    ref={columnPanelRef}
                    className="column-panel"
                    style={{
                      top: columnPanelPosition.top,
                      right: columnPanelPosition.right,
                    }}
                  >
                    {COMPARE_COLUMN_DEFS.map((col) => (
                      <label key={col.key} className="column-option">
                        <input
                          type="checkbox"
                          checked={draftColumns.has(col.key)}
                          onChange={() => {
                            setDraftColumns((prev) => {
                              const next = new Set(prev);
                              if (next.has(col.key)) next.delete(col.key);
                              else next.add(col.key);
                              return next;
                            });
                          }}
                        />
                        <span className="column-option-box" aria-hidden="true">
                          <Check size={13} strokeWidth={3} />
                        </span>
                        <span className="column-option-text">{col.label}</span>
                      </label>
                    ))}
                    <div className="column-panel-actions">
                      <button
                        onClick={() => {
                          setDraftColumns(new Set(COMPARE_COLUMN_DEFS.map((d) => d.key)));
                        }}
                      >
                        全选
                      </button>
                      <button onClick={() => setDraftColumns(new Set())}>取消全选</button>
                      <button
                        className="primary"
                        onClick={() => {
                          setVisibleColumns(draftColumns);
                          localStorage.setItem(
                            COMPARE_VISIBLE_COLUMNS_STORAGE_KEY,
                            JSON.stringify([...draftColumns]),
                          );
                          LEGACY_COMPARE_VISIBLE_COLUMNS_STORAGE_KEYS.forEach((key) => {
                            localStorage.removeItem(key);
                          });
                          setColumnPanelOpen(false);
                        }}
                      >
                        确定
                      </button>
                    </div>
                  </div>,
                  document.body,
                )}
            </div>
            <button
              className="button ghost"
              onClick={() =>
                setCompareFilters((prev) => ({
                  ...prev,
                  sort_order: prev.sort_order === "desc" ? "asc" : "desc",
                  page: 1,
                }))
              }
            >
              <ArrowDownAZ size={16} />
              {compareFilters.sort_order === "desc" ? "降序" : "升序"}
            </button>
          </div>
        </div>
        <div className="table-scroll">
          <table className="compare-table" style={{ minWidth: compareTableMinWidth }}>
            <thead>
              <tr>
                <th>关键词</th>
                {visibleColumns.has("category") && <th>类目</th>}
                {visibleColumns.has("sparkline") && <th className="sparkline-th">趋势图</th>}
                {visibleColumns.has("end_search_volume") && <th>末月搜索量</th>}
                {visibleColumns.has("search_volume_change") && <th>搜索量增量</th>}
                {visibleColumns.has("growth_rate") && <th>增长率</th>}
                {visibleColumns.has("mom") && <th>环比</th>}
                {visibleColumns.has("yoy") && <th>同比</th>}
                {visibleColumns.has("rank_change") && <th>排名变化</th>}
                {visibleColumns.has("month_count") && <th>出现月数</th>}
                {visibleColumns.has("avg_search_volume") && <th>平均搜索量</th>}
                {visibleColumns.has("ppc") && <th>PPC</th>}
                {visibleColumns.has("spr") && <th>SPR</th>}
                {visibleColumns.has("trend_type") && <th>类型</th>}
                {visibleColumns.has("holiday") && <th>节日标签</th>}
                {visibleColumns.has("status") && <th>状态</th>}
                {visibleColumns.has("actions") && <th>操作</th>}
                {visibleColumns.has("history_rank") && <th>末月历史排名</th>}
                {visibleColumns.has("monthly_volume") &&
                  compareMonths.map((month) => (
                    <th key={month} className="monthly-col">
                      {formatMonth(month)}搜索量
                    </th>
                  ))}
              </tr>
            </thead>
            <tbody>
              {compareLoading ? (
                Array.from({ length: 8 }).map((_, index) => (
                  <tr key={index}>
                    <td
                      colSpan={
                        1 +
                        visibleColumns.size +
                        (visibleColumns.has("monthly_volume") ? compareMonths.length - 1 : 0)
                      }
                    >
                      <div className="skeleton" />
                    </td>
                  </tr>
                ))
              ) : compareItems.length === 0 ? (
                <tr>
                  <td
                    colSpan={
                      1 +
                      visibleColumns.size +
                      (visibleColumns.has("monthly_volume") ? compareMonths.length - 1 : 0)
                    }
                    className="empty-cell"
                  >
                    没有符合条件的横向对比关键词
                  </td>
                </tr>
              ) : (
                compareItems.map((item) => {
                  const monthlyMap = new Map(
                    item.monthly.map((month) => [month.data_month.slice(0, 10), month]),
                  );
                  return (
                    <tr key={`${item.keyword_id}-${item.marketplace}`}>
                      <td className="keyword-cell">
                        <button className="keyword-button" type="button">
                          {item.keyword}
                        </button>
                        <span>{item.keyword_translation || "-"}</span>
                      </td>
                      {visibleColumns.has("category") && (
                        <td className="muted-cell">{item.category || "-"}</td>
                      )}
                      {visibleColumns.has("sparkline") && (
                        <td className="sparkline-cell">
                          <Sparkline monthly={item.monthly} width={120} height={32} />
                        </td>
                      )}
                      {visibleColumns.has("end_search_volume") && (
                        <td>{formatNumber(item.end_search_volume)}</td>
                      )}
                      {visibleColumns.has("search_volume_change") && (
                        <td>
                          <strong
                            className={
                              (item.search_volume_change ?? 0) >= 0 ? "positive" : "negative"
                            }
                          >
                            {(item.search_volume_change ?? 0) >= 0 ? "+" : ""}
                            {formatNumber(item.search_volume_change)}
                          </strong>
                        </td>
                      )}
                      {visibleColumns.has("growth_rate") && (
                        <td>
                          <strong
                            className={
                              (item.search_volume_growth_rate ?? 0) >= 0
                                ? "positive"
                                : "negative"
                            }
                          >
                            {formatGrowthPercent(item.search_volume_growth_rate)}
                          </strong>
                        </td>
                      )}
                      {visibleColumns.has("mom") && (
                        <td>
                          {item.mom_change !== null && item.mom_change !== undefined ? (
                            <>
                              <strong className={item.mom_change >= 0 ? "positive" : "negative"}>
                                {item.mom_change >= 0 ? "+" : ""}{formatNumber(item.mom_change)}
                              </strong>
                              <br />
                              <small className="muted-cell">{formatGrowthPercent(item.mom_rate)}</small>
                            </>
                          ) : (
                            "-"
                          )}
                        </td>
                      )}
                      {visibleColumns.has("yoy") && (
                        <td>
                          {item.yoy_change !== null && item.yoy_change !== undefined ? (
                            <>
                              <strong className={item.yoy_change >= 0 ? "positive" : "negative"}>
                                {item.yoy_change >= 0 ? "+" : ""}{formatNumber(item.yoy_change)}
                              </strong>
                              <br />
                              <small className="muted-cell">{formatGrowthPercent(item.yoy_rate)}</small>
                            </>
                          ) : (
                            "-"
                          )}
                        </td>
                      )}
                      {visibleColumns.has("rank_change") && (
                        <td>
                          {item.rank_change === null || item.rank_change === undefined
                            ? "-"
                            : item.rank_change > 0
                              ? `提升 ${formatNumber(item.rank_change)}`
                              : item.rank_change < 0
                                ? `下降 ${formatNumber(Math.abs(item.rank_change))}`
                                : "持平"}
                        </td>
                      )}
                      {visibleColumns.has("month_count") && (
                        <td>
                          {item.month_count} / {item.total_months}
                        </td>
                      )}
                      {visibleColumns.has("avg_search_volume") && <td>{formatNumber(item.avg_search_volume)}</td>}
                      {visibleColumns.has("ppc") && <td>{item.ppc_bid_mid ?? "-"}</td>}
                      {visibleColumns.has("spr") && <td>{item.spr ?? "-"}</td>}
                      {visibleColumns.has("trend_type") && (
                        <td>
                          <Tag
                            tone={
                              item.trend_type === "rising"
                                ? "success"
                                : item.trend_type === "falling"
                                  ? "danger"
                                  : item.trend_type === "stable"
                                    ? "info"
                                    : item.trend_type === "seasonal"
                                      ? "warning"
                                      : "neutral"
                            }
                          >
                            {item.trend_type_cn}
                          </Tag>
                        </td>
                      )}
                      {visibleColumns.has("holiday") && (
                        <td>
                          {item.holiday_label ? (
                            <Tag tone={item.holiday_tags?.some((t) => t.confidence === "confirmed") ? "success" : "warning"}>
                              {item.holiday_label}
                            </Tag>
                          ) : (
                            "-"
                          )}
                        </td>
                      )}
                      {visibleColumns.has("status") && (
                        <td>
                          <AppleSelect
                            compact
                            value={item.user_status || "new"}
                            options={statusOptions}
                            ariaLabel={`${item.keyword} 当前状态 ${statusLabel(item.user_status)}`}
                            onChange={(value) => onChangeState(item, value)}
                          />
                        </td>
                      )}
                      {visibleColumns.has("actions") && (
                        <td>
                          <div className="row-actions">
                            <button
                              className="icon-button"
                              onClick={() => onToggleFavorite(item)}
                              title="收藏"
                            >
                              <Star
                                size={16}
                                fill={item.user_is_favorite ? "currentColor" : "none"}
                              />
                            </button>
                            <button
                              className="icon-button"
                              onClick={() => onAddExclusion(item)}
                              title="加入禁用词"
                            >
                              <Shield size={16} />
                            </button>
                          </div>
                        </td>
                      )}
                      {visibleColumns.has("history_rank") && (
                        <td className="history-rank-cell">
                          末月 {item.last_month ? item.last_month.slice(0, 7) : "-"} 记录：上月{" "}
                          {formatNumber(item.prev_month_rank)} / 4月前{" "}
                          {formatNumber(item.four_months_ago_rank)} / 12月前{" "}
                          {formatNumber(item.twelve_months_ago_rank)}
                        </td>
                      )}
                      {visibleColumns.has("monthly_volume") &&
                        compareMonths.map((month) => {
                          const row = monthlyMap.get(month);
                          return (
                            <td key={month} className="monthly-col">
                              {formatNumber(row?.search_volume)}
                            </td>
                          );
                        })}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={compareFilters.page}
          totalPages={comparePagination.total_pages}
          pageSize={compareFilters.page_size}
          pageJump={comparePageJump}
          onPageChange={(page) => updateCompareFilter("page", page)}
          onPageSizeChange={(size) => updateCompareFilter("page_size", size)}
          onPageJumpChange={setComparePageJump}
          onSubmitPageJump={submitComparePageJump}
          pageJumpInputId="compare-page-jump-input"
        />
      </section>
    </section>
  );
}
