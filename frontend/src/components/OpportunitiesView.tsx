import {
  ArrowDownAZ,
  Eye,
  Filter,
  Search,
  Shield,
  Star,
  X,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import type { Candidate, CandidateFilters, CategoryItem, MonthItem } from "../types";
import { formatNumber, statusLabel } from "../utils";
import { AppleSelect } from "./AppleSelect";
import type { SelectOption } from "./AppleSelect";
import { Field } from "./Field";
import { Metric } from "./Metric";
import { Pagination } from "./Pagination";
import { Tag } from "./Tag";

export type DataScope =
  | "all"
  | "candidate"
  | "priority"
  | "rising"
  | "stable"
  | "new"
  | "lowCompetition"
  | "highDemand"
  | "review";

const scopeOptions: Array<{ value: DataScope; label: string; description: string }> = [
  { value: "all", label: "全量词库", description: "当月导入的全部关键词" },
  { value: "candidate", label: "候选词库", description: "符合基础选品规则" },
  { value: "priority", label: "核心选品机会", description: "A级候选，值得优先调研" },
  { value: "rising", label: "上升趋势机会", description: "增长词，适合提前布局" },
  { value: "stable", label: "稳定需求机会", description: "长期稳定，适合常规开发" },
  { value: "new", label: "新词观察", description: "新出现词，先观察再判断" },
  { value: "lowCompetition", label: "低竞争机会", description: "低PPC低SPR，适合切入" },
  { value: "highDemand", label: "高需求谨慎池", description: "高搜索量，需单独判断" },
  { value: "review", label: "待人工判断", description: "低分或异常词，适合清洗" },
];

export const DEFAULT_SCOPE: DataScope = "priority";

export function getScopePatch(scope: DataScope): Partial<CandidateFilters> {
  const base: Partial<CandidateFilters> = {
    category: "",
    trend_label: "",
    candidate_level: "",
    selection_segment: "",
    search_volume_min: "",
    search_volume_max: "",
    score_min: "",
    score_max: "",
    ppc_min: "",
    ppc_max: "",
    spr_min: "",
    spr_max: "",
    sort_order: "desc",
  };
  if (scope === "all") {
    return { ...base, is_candidate: "", sort_by: "search_volume" };
  }
  if (scope === "candidate") {
    return { ...base, is_candidate: "true", sort_by: "product_selection_score" };
  }
  if (scope === "priority") {
    return { ...base, is_candidate: "true", score_min: "85", sort_by: "product_selection_score" };
  }
  if (scope === "rising") {
    return {
      ...base,
      is_candidate: "true",
      trend_label: "rising",
      search_volume_min: "1000",
      search_volume_max: "30000",
      ppc_max: "1.8",
      spr_max: "25",
      sort_by: "product_selection_score",
    };
  }
  if (scope === "stable") {
    return {
      ...base,
      is_candidate: "true",
      trend_label: "stable",
      search_volume_min: "2000",
      search_volume_max: "20000",
      ppc_max: "1.5",
      spr_max: "20",
      sort_by: "product_selection_score",
    };
  }
  if (scope === "new") {
    return {
      ...base,
      is_candidate: "",
      trend_label: "new",
      search_volume_min: "1000",
      search_volume_max: "15000",
      ppc_max: "1.5",
      spr_max: "20",
      sort_by: "search_volume",
    };
  }
  if (scope === "lowCompetition") {
    return {
      ...base,
      is_candidate: "true",
      search_volume_min: "500",
      search_volume_max: "10000",
      ppc_max: "1.0",
      spr_max: "10",
      sort_by: "product_selection_score",
    };
  }
  if (scope === "highDemand") {
    return {
      ...base,
      is_candidate: "",
      search_volume_min: "20000",
      search_volume_max: "80000",
      ppc_max: "2.5",
      spr_max: "50",
      sort_by: "search_volume",
    };
  }
  return {
    ...base,
    is_candidate: "",
    score_min: "",
    score_max: "64",
    sort_by: "product_selection_score",
    sort_order: "asc",
  };
}

const trendOptions: SelectOption[] = [
  { value: "rising", label: "上升机会" },
  { value: "new", label: "新出现词" },
  { value: "stable", label: "稳定词" },
  { value: "volume_up_rank_down", label: "需求升但排名降" },
  { value: "rank_up_volume_down", label: "排名升但需求降" },
  { value: "falling", label: "下降风险" },
];

const candidateLevelOptions: SelectOption[] = [
  { value: "", label: "全部等级" },
  { value: "A级", label: "A级" },
  { value: "B级", label: "B级" },
  { value: "C级", label: "C级" },
];

const statusOptions: SelectOption[] = [
  { value: "new", label: "新候选" },
  { value: "watching", label: "观察中" },
  { value: "researching", label: "调研中" },
  { value: "rejected", label: "已放弃" },
  { value: "approved", label: "进入开发" },
  { value: "launched", label: "已上架" },
];

interface OpportunitiesViewProps {
  dataScope: DataScope;
  onChangeScope: (scope: DataScope) => void;
  activeView: "opportunities" | "favorites";
  currentMonthKeywordCount: number | null;
  totalLabel: "estimated" | "lower_bound" | "exact";
  totalIsEstimated: boolean;
  total: number;
  totalPages: number;
  summary: { levelA: number; favorites: number; avgScore: number };
  filters: CandidateFilters;
  setFilters: React.Dispatch<React.SetStateAction<CandidateFilters>>;
  updateFilter: <K extends keyof CandidateFilters>(key: K, value: CandidateFilters[K]) => void;
  months: MonthItem[];
  categories: CategoryItem[];
  items: Candidate[];
  loading: boolean;
  error: string;
  isCached: boolean;
  pageJump: string;
  setPageJump: (value: string) => void;
  onLoadCandidates: (forceRefresh?: boolean) => void;
  onOpenDetail: (candidate: Candidate) => void;
  onChangeState: (candidate: Candidate, status: string) => void;
  onToggleFavorite: (candidate: Candidate) => void;
  onAddExclusion: (candidate: Candidate) => void;
}

export function OpportunitiesView({
  dataScope,
  onChangeScope,
  activeView,
  currentMonthKeywordCount,
  totalLabel,
  totalIsEstimated,
  total,
  totalPages,
  summary,
  filters,
  setFilters,
  updateFilter,
  months,
  categories,
  items,
  loading,
  error,
  isCached,
  pageJump,
  setPageJump,
  onLoadCandidates,
  onOpenDetail,
  onChangeState,
  onToggleFavorite,
  onAddExclusion,
}: OpportunitiesViewProps) {
  const [keywordDraft, setKeywordDraft] = useState(filters.keyword);
  const currentScope = scopeOptions.find((item) => item.value === dataScope) ?? scopeOptions[0];
  const totalPrefix =
    totalLabel === "lower_bound" ? "至少 " : totalIsEstimated ? "约 " : "";

  useEffect(() => {
    setKeywordDraft(filters.keyword);
  }, [filters.keyword]);

  useEffect(() => {
    if (keywordDraft === filters.keyword) return;
    const timeoutId = window.setTimeout(() => {
      updateFilter("keyword", keywordDraft);
    }, 300);
    return () => window.clearTimeout(timeoutId);
  }, [keywordDraft, filters.keyword, updateFilter]);

  function submitPageJump(event: FormEvent) {
    event.preventDefault();
    const parsed = Number.parseInt(pageJump, 10);
    if (Number.isNaN(parsed)) {
      setPageJump(String(filters.page));
      return;
    }
    const targetPage = Math.min(Math.max(parsed, 1), Math.max(totalPages, 1));
    updateFilter("page", targetPage);
    setPageJump(String(targetPage));
  }

  return (
    <>
      <section className="scope-bar apple-panel" aria-label="运营模式">
        {scopeOptions.map((option) => (
          <button
            key={option.value}
            className={option.value === dataScope ? "scope-option active" : "scope-option"}
            onClick={() => onChangeScope(option.value)}
          >
            <strong>{option.label}</strong>
            <span>{option.description}</span>
          </button>
        ))}
      </section>

      <section className="metric-grid">
        <Metric label="月份全量" value={formatNumber(currentMonthKeywordCount)} />
        <Metric
          label={
            activeView === "favorites"
              ? "当前收藏结果"
              : totalLabel === "lower_bound"
                ? "当前筛选至少"
                : totalIsEstimated
                  ? "当前筛选约"
                  : "当前筛选结果"
          }
          value={formatNumber(total)}
        />
        <Metric label="本页A级" value={formatNumber(summary.levelA)} />
        <Metric label="本页收藏" value={formatNumber(summary.favorites)} />
        <Metric label="平均选品分" value={summary.avgScore.toFixed(1)} />
      </section>

      <section className="filter-panel apple-panel">
        <div className="filter-title">
          <Filter size={16} />
          筛选条件
        </div>
        <div className="filter-grid">
          <Field label="月份">
            <AppleSelect
              value={filters.analysis_month}
              options={months.map((item) => ({
                value: item.data_month.slice(0, 10),
                label: `${item.data_month.slice(0, 7)} / ${item.marketplace}`,
              }))}
              ariaLabel="月份"
              onChange={(value) => updateFilter("analysis_month", value)}
            />
          </Field>
          <Field label="关键词">
            <div className="input-icon">
              <Search size={15} />
              <input
                value={keywordDraft}
                onChange={(event) => setKeywordDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") updateFilter("keyword", keywordDraft);
                }}
                placeholder="输入英文或中文"
              />
            </div>
          </Field>
          <Field label="类目">
            <AppleSelect
              value={filters.category}
              options={[
                { value: "", label: "全部类目" },
                ...categories.slice(0, 160).map((item) => ({
                  value: item.category,
                  label: `${item.category} (${formatNumber(item.candidate_count)})`,
                })),
              ]}
              ariaLabel="类目"
              onChange={(value) => updateFilter("category", value)}
            />
          </Field>
          <Field label="趋势">
            <AppleSelect
              value={filters.trend_label}
              options={[{ value: "", label: "全部趋势" }, ...trendOptions]}
              ariaLabel="趋势"
              onChange={(value) => updateFilter("trend_label", value)}
            />
          </Field>
          <Field label="候选等级">
            <AppleSelect
              value={filters.candidate_level}
              options={candidateLevelOptions}
              ariaLabel="候选等级"
              onChange={(value) => updateFilter("candidate_level", value)}
            />
          </Field>
          <Field label="选品分">
            <div className="range-row">
              <input
                value={filters.score_min}
                onChange={(event) => updateFilter("score_min", event.target.value)}
              />
              <span>-</span>
              <input
                value={filters.score_max}
                onChange={(event) => updateFilter("score_max", event.target.value)}
              />
            </div>
          </Field>
          <Field label="搜索量">
            <div className="range-row">
              <input
                value={filters.search_volume_min}
                onChange={(event) => updateFilter("search_volume_min", event.target.value)}
              />
              <span>-</span>
              <input
                value={filters.search_volume_max}
                onChange={(event) => updateFilter("search_volume_max", event.target.value)}
              />
            </div>
          </Field>
          <Field label="PPC区间">
            <div className="range-row">
              <input
                value={filters.ppc_min}
                onChange={(event) => updateFilter("ppc_min", event.target.value)}
                placeholder="最低"
              />
              <span>-</span>
              <input
                value={filters.ppc_max}
                onChange={(event) => updateFilter("ppc_max", event.target.value)}
                placeholder="最高"
              />
            </div>
          </Field>
          <Field label="SPR区间">
            <div className="range-row">
              <input
                value={filters.spr_min}
                onChange={(event) => updateFilter("spr_min", event.target.value)}
                placeholder="最低"
              />
              <span>-</span>
              <input
                value={filters.spr_max}
                onChange={(event) => updateFilter("spr_max", event.target.value)}
                placeholder="最高"
              />
            </div>
          </Field>
        </div>
        <div className="filter-actions">
          <button
            className="button secondary"
            onClick={() =>
              setFilters({
                ...filters,
                keyword: "",
                category: "",
                trend_label: "",
                candidate_level: "",
                search_volume_min: "",
                search_volume_max: "",
                score_min: "",
                score_max: "",
                ppc_min: "",
                ppc_max: "",
                spr_min: "",
                spr_max: "",
                ...getScopePatch(dataScope),
                favorite_only: activeView === "favorites" ? "true" : "",
                page: 1,
              })
            }
          >
            <X size={16} />
            重置
          </button>
          <button className="button primary" onClick={() => onLoadCandidates()}>
            <Search size={16} />
            查询
          </button>
        </div>
      </section>

      {error && <div className="alert">{error}</div>}

      {!isCached && (
        <div className="alert warning">
          当前月份使用实时计算，查询较慢。建议运行 <code>calculate_trends.py</code>{" "}
          生成缓存以提升速度。
        </div>
      )}

      <section className="table-shell">
        <div className="table-toolbar">
          <div>
            <strong>
              {activeView === "favorites"
                ? `${currentScope.label}收藏清单`
                : `${currentScope.label}清单`}
            </strong>
            <span>
              当前筛选后{totalPrefix || "共 "}
              {formatNumber(total)} 条，当前第 {filters.page} 页
            </span>
          </div>
          <button
            className="button ghost"
            onClick={() =>
              setFilters((prev) => ({
                ...prev,
                sort_by:
                  prev.sort_by === "search_volume"
                    ? "product_selection_score"
                    : "search_volume",
                page: 1,
              }))
            }
          >
            <ArrowDownAZ size={16} />
            {filters.sort_by === "search_volume" ? "按选品分" : "按搜索量"}
          </button>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>关键词</th>
                <th>类目</th>
                <th>搜索量</th>
                <th>趋势</th>
                <th>选品分</th>
                <th>原因</th>
                <th>PPC</th>
                <th>SPR</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 8 }).map((_, index) => (
                  <tr key={index}>
                    <td colSpan={10}>
                      <div className="skeleton" />
                    </td>
                  </tr>
                ))
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={10} className="empty-cell">
                    {activeView === "favorites"
                      ? "还没有收藏关键词"
                      : "没有符合条件的关键词"}
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={`${item.keyword_id}-${item.analysis_month}-${item.marketplace}`}>
                    <td className="keyword-cell">
                      <button
                        className="keyword-button"
                        onClick={() => onOpenDetail(item)}
                      >
                        {item.keyword}
                      </button>
                      <span>{item.keyword_translation || "-"}</span>
                    </td>
                    <td className="muted-cell">{item.category}</td>
                    <td>{formatNumber(item.search_volume)}</td>
                    <td>
                      <Tag
                        tone={item.trend_label === "rising" ? "success" : "neutral"}
                      >
                        {item.trend_label_cn || "-"}
                      </Tag>
                    </td>
                    <td>
                      <strong>{item.product_selection_score ?? "-"}</strong>
                      <small className="level">{item.candidate_level_cn || "-"}</small>
                    </td>
                    <td className="reason-cell">
                      {item.exclusion_reason_cn || item.selection_segment_cn || "-"}
                    </td>
                    <td>{item.ppc_bid_mid ?? "-"}</td>
                    <td>{item.spr ?? "-"}</td>
                    <td>
                      <AppleSelect
                        compact
                        value={item.user_status || "new"}
                        options={statusOptions}
                        ariaLabel={`${item.keyword} 当前状态 ${statusLabel(item.user_status)}`}
                        onChange={(value) => onChangeState(item, value)}
                      />
                    </td>
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
                          onClick={() => onOpenDetail(item)}
                          title="详情"
                        >
                          <Eye size={16} />
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
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={filters.page}
          totalPages={totalPages}
          pageSize={filters.page_size}
          pageJump={pageJump}
          onPageChange={(page) => updateFilter("page", page)}
          onPageSizeChange={(size) => updateFilter("page_size", size)}
          onPageJumpChange={setPageJump}
          onSubmitPageJump={submitPageJump}
        />
      </section>
    </>
  );
}
