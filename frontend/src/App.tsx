import {
  ArrowDownAZ,
  BarChart3,
  Bookmark,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  Filter,
  GitCompareArrows,
  LogOut,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Star,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  authHeaders,
  buildExportUrl,
  clearCandidateCache,
  clearSession,
  createExclusion,
  createCandidateNote,
  getCandidateDetail,
  getCandidates,
  getCategories,
  getExclusions,
  getKeywordCompare,
  getMe,
  getMonths,
  login,
  readUser,
  saveSession,
  updateExclusion,
  updateCandidateState,
} from "./api";
import type {
  Candidate,
  CandidateDetail,
  CandidateFilters,
  CategoryItem,
  ExclusionRule,
  KeywordCompareFilters,
  KeywordCompareItem,
  MonthItem,
  Pagination,
  User,
} from "./types";

type DataScope =
  | "all"
  | "candidate"
  | "priority"
  | "rising"
  | "stable"
  | "new"
  | "lowCompetition"
  | "highDemand"
  | "review";
type ActiveView = "opportunities" | "favorites" | "compare" | "exclusions";
type ListView = Exclude<ActiveView, "compare" | "exclusions">;
type ListViewState = { filters: CandidateFilters; dataScope: DataScope };
type SelectOption = { value: string; label: string };

const DEFAULT_SCOPE: DataScope = "priority";

const DEFAULT_FILTERS: CandidateFilters = {
  page: 1,
  page_size: 50,
  analysis_month: "",
  marketplace: "UK",
  keyword: "",
  category: "",
  trend_label: "",
  candidate_level: "",
  selection_segment: "",
  is_candidate: "true",
  favorite_only: "",
  search_volume_min: "",
  search_volume_max: "",
  score_min: "85",
  score_max: "",
  ppc_max: "",
  spr_max: "",
  sort_by: "product_selection_score",
  sort_order: "desc",
};

const DEFAULT_FAVORITE_FILTERS: CandidateFilters = {
  ...DEFAULT_FILTERS,
  ...getScopePatch("all"),
  favorite_only: "true",
  sort_by: "search_volume",
  sort_order: "desc",
};

const DEFAULT_COMPARE_FILTERS: KeywordCompareFilters = {
  page: 1,
  page_size: 50,
  start_month: "",
  end_month: "",
  marketplace: "UK",
  keyword: "",
  category: "",
  trend_type: "",
  search_volume_min: "1000",
  search_volume_max: "",
  growth_rate_min: "",
  growth_rate_max: "",
  month_count_min: "3",
  ppc_max: "",
  spr_max: "",
  sort_by: "end_search_volume",
  sort_order: "desc",
};

const compareTrendOptions: SelectOption[] = [
  { value: "", label: "全部类型" },
  { value: "rising", label: "上升型" },
  { value: "falling", label: "下降型" },
  { value: "stable", label: "常年稳定型" },
  { value: "seasonal", label: "季节型" },
  { value: "volatile", label: "波动型" },
];

const compareSortOptions: SelectOption[] = [
  { value: "end_search_volume", label: "按末月搜索量" },
  { value: "growth_rate", label: "按增长率" },
  { value: "volume_change", label: "按搜索量增量" },
  { value: "rank_change", label: "按排名改善" },
  { value: "month_count", label: "按出现月数" },
];

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

const statusOptions = [
  { value: "new", label: "新候选" },
  { value: "watching", label: "观察中" },
  { value: "researching", label: "调研中" },
  { value: "rejected", label: "已放弃" },
  { value: "approved", label: "进入开发" },
  { value: "launched", label: "已上架" },
];

const trendOptions = [
  { value: "rising", label: "上升机会" },
  { value: "new", label: "新出现词" },
  { value: "stable", label: "稳定词" },
  { value: "volume_up_rank_down", label: "需求升但排名降" },
  { value: "rank_up_volume_down", label: "排名升但需求降" },
  { value: "falling", label: "下降风险" },
];

const matchTypeOptions: SelectOption[] = [
  { value: "contains", label: "包含匹配" },
  { value: "exact", label: "完全匹配" },
];

const exclusionTypeOptions: SelectOption[] = [
  { value: "brand", label: "品牌词" },
  { value: "irrelevant", label: "无关词" },
  { value: "risk", label: "风险词" },
  { value: "competitor", label: "竞品词" },
];

const activeStateOptions: SelectOption[] = [
  { value: "active", label: "启用" },
  { value: "inactive", label: "停用" },
];

const candidateLevelOptions: SelectOption[] = [
  { value: "", label: "全部等级" },
  { value: "A级", label: "A级" },
  { value: "B级", label: "B级" },
  { value: "C级", label: "C级" },
];

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat("zh-CN").format(Math.round(value));
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function formatGrowthPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function formatMonth(value: string | null | undefined): string {
  if (!value) return "-";
  return value.slice(0, 7);
}

function statusLabel(value: string | null | undefined): string {
  return statusOptions.find((item) => item.value === value)?.label ?? "新候选";
}

function exclusionTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    brand: "品牌词",
    irrelevant: "无关词",
    risk: "风险词",
    competitor: "竞品词",
  };
  return labels[value] ?? value;
}

function minutesAgo(timestamp: number): string {
  const elapsed = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  if (elapsed < 1) return "不到1";
  return String(elapsed);
}

function getScopePatch(scope: DataScope): Partial<CandidateFilters> {
  const base: Partial<CandidateFilters> = {
    category: "",
    trend_label: "",
    candidate_level: "",
    selection_segment: "",
    search_volume_min: "",
    search_volume_max: "",
    score_min: "",
    score_max: "",
    ppc_max: "",
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

function AppleSelect({
  value,
  options,
  onChange,
  ariaLabel,
  compact = false,
}: {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  ariaLabel: string;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selected = options.find((option) => option.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;

    function closeOnOutside(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div className={compact ? "apple-select compact" : "apple-select"} ref={rootRef}>
      <button
        type="button"
        className={open ? "apple-select-trigger open" : "apple-select-trigger"}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{selected?.label ?? "请选择"}</span>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className="apple-select-menu" role="listbox">
          {options.map((option) => (
            <button
              type="button"
              key={option.value}
              className={option.value === value ? "apple-select-option selected" : "apple-select-option"}
              role="option"
              aria-selected={option.value === value}
              onClick={() => {
                onChange(option.value);
                setOpen(false);
              }}
            >
              <span>{option.label}</span>
              {option.value === value && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function App() {
  const [user, setUser] = useState<User | null>(() => readUser());
  const [loginAccount, setLoginAccount] = useState("admin");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [filters, setFilters] = useState<CandidateFilters>(DEFAULT_FILTERS);
  const [compareFilters, setCompareFilters] = useState<KeywordCompareFilters>(DEFAULT_COMPARE_FILTERS);
  const [dataScope, setDataScope] = useState<DataScope>(DEFAULT_SCOPE);
  const [activeView, setActiveView] = useState<ActiveView>("opportunities");
  const [months, setMonths] = useState<MonthItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [items, setItems] = useState<Candidate[]>([]);
  const [compareItems, setCompareItems] = useState<KeywordCompareItem[]>([]);
  const [compareMonths, setCompareMonths] = useState<string[]>([]);
  const [comparePagination, setComparePagination] = useState<Pagination>({
    page: 1,
    page_size: DEFAULT_COMPARE_FILTERS.page_size,
    total: 0,
    total_pages: 1,
  });
  const [comparePageJump, setComparePageJump] = useState("1");
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState("");
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [totalIsEstimated, setTotalIsEstimated] = useState(false);
  const [totalLabel, setTotalLabel] = useState<"estimated" | "lower_bound" | "exact">("exact");
  const [pageJump, setPageJump] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dataAge, setDataAge] = useState<number | null>(null);  // timestamp of last successful fetch
  const [isCached, setIsCached] = useState(true);
  const [dbOperationCount, setDbOperationCount] = useState(0);
  const [dbOperationMessage, setDbOperationMessage] = useState("");
  const [selected, setSelected] = useState<Candidate | null>(null);
  const [detail, setDetail] = useState<CandidateDetail | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [exclusions, setExclusions] = useState<ExclusionRule[]>([]);
  const [exclusionLoading, setExclusionLoading] = useState(false);
  const [exclusionError, setExclusionError] = useState("");
  const [newExclusion, setNewExclusion] = useState({
    term: "",
    match_type: "contains" as "contains" | "exact",
    exclusion_type: "brand",
    reason: "",
    is_active: true,
  });
  const listViewSnapshots = useRef<Record<ListView, ListViewState>>({
    opportunities: { filters: { ...DEFAULT_FILTERS }, dataScope: DEFAULT_SCOPE },
    favorites: { filters: { ...DEFAULT_FAVORITE_FILTERS }, dataScope: "all" },
  });

  useEffect(() => {
    if (!user) return;
    getMe().catch(() => {
      clearSession();
      setUser(null);
    });
  }, [user]);

  useEffect(() => {
    if (!user) return;
    const finishDbOperation = beginDbOperation("正在查询月份数据");
    getMonths()
      .then((data) => {
        setMonths(data.items);
        if (!filters.analysis_month && data.items.length) {
          const first = data.items[0];
          const last = data.items[data.items.length - 1];
          setFilters((prev) => ({
            ...prev,
            analysis_month: first.data_month.slice(0, 10),
            marketplace: first.marketplace,
          }));
          setCompareFilters((prev) => ({
            ...prev,
            start_month: last.data_month.slice(0, 10),
            end_month: first.data_month.slice(0, 10),
            marketplace: first.marketplace,
          }));
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(finishDbOperation);
  }, [user, filters.analysis_month]);

  useEffect(() => {
    if (!user || !filters.analysis_month) return;
    const finishDbOperation = beginDbOperation("正在查询类目数据");
    getCategories(filters.analysis_month, filters.marketplace)
      .then((data) => setCategories(data.items))
      .catch((err: Error) => setError(err.message))
      .finally(finishDbOperation);
  }, [user, filters.analysis_month, filters.marketplace]);

  useEffect(() => {
    if (!user || !filters.analysis_month || (activeView !== "opportunities" && activeView !== "favorites")) return;
    void loadCandidates();
  }, [
    user,
    activeView,
    filters.page,
    filters.page_size,
    filters.analysis_month,
    filters.marketplace,
    filters.category,
    filters.trend_label,
    filters.candidate_level,
    filters.selection_segment,
    filters.is_candidate,
    filters.favorite_only,
    filters.search_volume_min,
    filters.search_volume_max,
    filters.score_min,
    filters.score_max,
    filters.ppc_max,
    filters.spr_max,
    filters.sort_by,
    filters.sort_order,
  ]);

  useEffect(() => {
    if (!user || activeView !== "exclusions") return;
    void loadExclusions();
  }, [user, activeView]);

  useEffect(() => {
    if (!user || activeView !== "compare" || !compareFilters.start_month || !compareFilters.end_month) return;
    void loadKeywordCompare();
  }, [
    user,
    activeView,
    compareFilters.page,
    compareFilters.page_size,
    compareFilters.start_month,
    compareFilters.end_month,
    compareFilters.marketplace,
    compareFilters.category,
    compareFilters.trend_type,
    compareFilters.keyword,
    compareFilters.search_volume_min,
    compareFilters.search_volume_max,
    compareFilters.growth_rate_min,
    compareFilters.growth_rate_max,
    compareFilters.month_count_min,
    compareFilters.ppc_max,
    compareFilters.spr_max,
    compareFilters.sort_by,
    compareFilters.sort_order,
  ]);

  useEffect(() => {
    setPageJump(String(filters.page));
  }, [filters.page]);

  useEffect(() => {
    setComparePageJump(String(compareFilters.page));
  }, [compareFilters.page]);

  const summary = useMemo(() => {
    const levelA = items.filter((item) => item.candidate_level_cn === "A级").length;
    const favorites = items.filter((item) => item.user_is_favorite).length;
    const avgScore =
      items.length === 0
        ? 0
        : items.reduce((sum, item) => sum + (item.product_selection_score ?? 0), 0) / items.length;
    return { levelA, favorites, avgScore };
  }, [items]);

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

  const currentScope = scopeOptions.find((item) => item.value === dataScope) ?? scopeOptions[0];
  const totalPrefix = totalLabel === "lower_bound" ? "至少 " : totalIsEstimated ? "约 " : "";
  const currentMonth = months.find(
    (item) => item.data_month.slice(0, 10) === filters.analysis_month && item.marketplace === filters.marketplace,
  );
  const pageTitle =
    activeView === "favorites"
      ? "我的收藏"
      : activeView === "compare"
        ? "关键词横向对比"
        : activeView === "exclusions"
          ? "禁用词管理"
          : "选品机会池";
  const pageSubtitle =
    activeView === "favorites"
      ? "集中查看已收藏关键词，继续调研、标记状态或导出清单。"
      : activeView === "compare"
        ? "按相同关键词跨月份对比搜索量、排名、出现连续性和历史排名参考。"
      : activeView === "exclusions"
        ? "维护品牌词、无关词和风险词，启用后会从候选池中排除。"
        : "在全量词库、候选词库和高优先级机会之间切换，明确区分数据总量和当前筛选结果。";

  function beginDbOperation(message: string) {
    setDbOperationMessage(message);
    setDbOperationCount((count) => count + 1);
    let finished = false;
    return () => {
      if (finished) return;
      finished = true;
      setDbOperationCount((count) => {
        const nextCount = Math.max(0, count - 1);
        if (nextCount === 0) setDbOperationMessage("");
        return nextCount;
      });
    };
  }

  async function handleLogin(event: React.FormEvent) {
    event.preventDefault();
    setLoginError("");
    const finishDbOperation = beginDbOperation("正在验证账号");
    try {
      const data = await login(loginAccount, loginPassword);
      saveSession(data.access_token, data.user);
      setUser(data.user);
    } catch {
      setLoginError("账号或密码不正确");
    } finally {
      finishDbOperation();
    }
  }

  async function loadCandidates(forceRefresh = false) {
    if (forceRefresh) clearCandidateCache();
    const finishDbOperation = beginDbOperation("正在查询数据库");
    setLoading(true);
    setError("");
    try {
      const data = await getCandidates(filters);
      setItems(data.items);
      setTotal(data.pagination.total);
      setTotalPages(data.pagination.total_pages || 1);
      setTotalIsEstimated(Boolean(data.pagination.total_is_estimated));
      setTotalLabel(data.pagination.total_label ?? (data.pagination.total_is_estimated ? "estimated" : "exact"));
      setIsCached(data.cached !== false);
      setDataAge(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
      finishDbOperation();
    }
  }

  async function loadKeywordCompare() {
    const finishDbOperation = beginDbOperation("正在查询横向对比数据");
    setCompareLoading(true);
    setCompareError("");
    try {
      const data = await getKeywordCompare(compareFilters);
      setCompareItems(data.items);
      setCompareMonths(data.months.map((item) => item.data_month.slice(0, 10)));
      setComparePagination(data.pagination);
    } catch (err) {
      setCompareError(err instanceof Error ? err.message : "横向对比加载失败");
    } finally {
      setCompareLoading(false);
      finishDbOperation();
    }
  }

  async function loadExclusions() {
    const finishDbOperation = beginDbOperation("正在查询禁用词规则");
    setExclusionLoading(true);
    setExclusionError("");
    try {
      const data = await getExclusions(false);
      setExclusions(data.items);
    } catch (err) {
      setExclusionError(err instanceof Error ? err.message : "禁用词加载失败");
    } finally {
      setExclusionLoading(false);
      finishDbOperation();
    }
  }

  function updateFilter<K extends keyof CandidateFilters>(key: K, value: CandidateFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value, page: key === "page" ? (value as number) : 1 }));
  }

  function updateCompareFilter<K extends keyof KeywordCompareFilters>(key: K, value: KeywordCompareFilters[K]) {
    setCompareFilters((prev) => ({ ...prev, [key]: value, page: key === "page" ? (value as number) : 1 }));
  }

  function rememberCurrentListView() {
    if (activeView !== "opportunities" && activeView !== "favorites") return;
    listViewSnapshots.current[activeView] = {
      filters: { ...filters },
      dataScope,
    };
  }

  function restoreListView(view: ListView) {
    if (activeView === view) return;
    rememberCurrentListView();
    const snapshot = listViewSnapshots.current[view];
    setDataScope(snapshot.dataScope);
    setFilters({
      ...snapshot.filters,
      favorite_only: view === "favorites" ? "true" : "",
    });
    setActiveView(view);
  }

  function showOpportunities() {
    restoreListView("opportunities");
  }

  function showFavorites() {
    restoreListView("favorites");
  }

  function showCompare() {
    rememberCurrentListView();
    setActiveView("compare");
  }

  function showExclusions() {
    rememberCurrentListView();
    setActiveView("exclusions");
  }

  function submitPageJump(event: React.FormEvent) {
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

  function submitComparePageJump(event: React.FormEvent) {
    event.preventDefault();
    const parsed = Number.parseInt(comparePageJump, 10);
    if (Number.isNaN(parsed)) {
      setComparePageJump(String(compareFilters.page));
      return;
    }
    const targetPage = Math.max(parsed, 1);
    updateCompareFilter("page", targetPage);
    setComparePageJump(String(targetPage));
  }

  function changeScope(scope: DataScope) {
    setDataScope(scope);
    setFilters((prev) => ({
      ...prev,
      ...getScopePatch(scope),
      page: 1,
    }));
  }

  async function submitExclusion(event: React.FormEvent) {
    event.preventDefault();
    const term = newExclusion.term.trim();
    if (!term) return;
    const finishDbOperation = beginDbOperation("正在保存禁用词规则");
    setExclusionError("");
    try {
      await createExclusion({
        term,
        match_type: newExclusion.match_type,
        exclusion_type: newExclusion.exclusion_type,
        reason: newExclusion.reason.trim() || undefined,
        is_active: newExclusion.is_active,
      });
      setNewExclusion({
        term: "",
        match_type: "contains",
        exclusion_type: "brand",
        reason: "",
        is_active: true,
      });
      await loadExclusions();
      if (activeView !== "exclusions") setActiveView("exclusions");
    } catch (err) {
      setExclusionError(err instanceof Error ? err.message : "新增禁用词失败");
    } finally {
      finishDbOperation();
    }
  }

  async function toggleExclusion(rule: ExclusionRule) {
    const finishDbOperation = beginDbOperation("正在更新禁用词规则");
    setExclusionError("");
    try {
      await updateExclusion(rule.id, { is_active: !rule.is_active });
      await loadExclusions();
    } catch (err) {
      setExclusionError(err instanceof Error ? err.message : "更新禁用词失败");
    } finally {
      finishDbOperation();
    }
  }

  async function addKeywordToExclusion(candidate: Candidate) {
    const finishDbOperation = beginDbOperation("正在加入禁用词");
    const reason = `运营从关键词清单加入：${candidate.keyword_translation || candidate.category || ""}`.trim();
    setNewExclusion((prev) => ({
      ...prev,
      term: candidate.keyword,
      match_type: "exact",
      exclusion_type: "irrelevant",
      reason,
      is_active: true,
    }));
    showExclusions();
    try {
      await createExclusion({
        term: candidate.keyword,
        match_type: "exact",
        exclusion_type: "irrelevant",
        reason,
        is_active: true,
      });
      await loadExclusions();
    } catch (err) {
      setExclusionError(err instanceof Error ? err.message : "加入禁用词失败");
    } finally {
      finishDbOperation();
    }
  }

  async function openDetail(candidate: Candidate) {
    const finishDbOperation = beginDbOperation("正在查询关键词详情");
    setSelected(candidate);
    setNoteDraft(candidate.user_notes ?? "");
    try {
      const data = await getCandidateDetail(candidate.keyword_id, candidate.analysis_month, candidate.marketplace);
      setDetail(data);
    } finally {
      finishDbOperation();
    }
  }

  async function changeState(candidate: Candidate, status: string) {
    const finishDbOperation = beginDbOperation("正在保存运营状态");
    try {
      await updateCandidateState(candidate.keyword_id, {
        analysis_month: candidate.analysis_month,
        marketplace: candidate.marketplace,
        status,
      });
      await loadCandidates();
      if (selected?.keyword_id === candidate.keyword_id) await openDetail(candidate);
    } finally {
      finishDbOperation();
    }
  }

  async function toggleFavorite(candidate: Candidate) {
    const finishDbOperation = beginDbOperation(candidate.user_is_favorite ? "正在取消收藏" : "正在收藏关键词");
    try {
      const nextFavorite = !candidate.user_is_favorite;
      await updateCandidateState(candidate.keyword_id, {
        analysis_month: candidate.analysis_month,
        marketplace: candidate.marketplace,
        is_favorite: nextFavorite,
      });
      if (selected?.keyword_id === candidate.keyword_id) {
        setSelected({ ...selected, user_is_favorite: nextFavorite });
      }
      await loadCandidates();
    } finally {
      finishDbOperation();
    }
  }

  async function changeCompareState(item: KeywordCompareItem, status: string) {
    const finishDbOperation = beginDbOperation("正在保存横向对比关键词状态");
    try {
      await updateCandidateState(item.keyword_id, {
        analysis_month: item.last_month,
        marketplace: item.marketplace,
        status,
      });
      await loadKeywordCompare();
    } finally {
      finishDbOperation();
    }
  }

  async function toggleCompareFavorite(item: KeywordCompareItem) {
    const finishDbOperation = beginDbOperation(item.user_is_favorite ? "正在取消收藏关键词" : "正在收藏关键词");
    try {
      await updateCandidateState(item.keyword_id, {
        analysis_month: item.last_month,
        marketplace: item.marketplace,
        is_favorite: !item.user_is_favorite,
      });
      await loadKeywordCompare();
    } finally {
      finishDbOperation();
    }
  }

  async function addCompareKeywordToExclusion(item: KeywordCompareItem) {
    const finishDbOperation = beginDbOperation("正在加入禁用词");
    const reason = `运营从横向对比加入，${item.keyword_translation || item.category || ""}`.trim();
    try {
      await createExclusion({
        term: item.keyword,
        match_type: "exact",
        exclusion_type: "irrelevant",
        reason,
        is_active: true,
      });
      await loadKeywordCompare();
    } catch (err) {
      setCompareError(err instanceof Error ? err.message : "加入禁用词失败");
    } finally {
      finishDbOperation();
    }
  }

  async function saveNote() {
    if (!selected || !noteDraft.trim()) return;
    const finishDbOperation = beginDbOperation("正在保存备注");
    try {
      await createCandidateNote(selected.keyword_id, {
        analysis_month: selected.analysis_month,
        marketplace: selected.marketplace,
        note: noteDraft.trim(),
      });
      await openDetail(selected);
    } finally {
      finishDbOperation();
    }
  }

  async function exportExcel() {
    const finishDbOperation = beginDbOperation("正在导出 Excel");
    const url = buildExportUrl(filters, 5000);
    try {
      const response = await fetch(url, { headers: authHeaders() });
      if (!response.ok) throw new Error("导出失败");
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "选品候选词.xlsx";
      link.click();
      URL.revokeObjectURL(link.href);
    } finally {
      finishDbOperation();
    }
  }

  if (!user) {
    return (
      <main className="login-shell">
        <section className="login-panel apple-panel animate-in">
          <div className="login-mark">
            <BarChart3 size={24} />
          </div>
          <h1>关键词选品工作台</h1>
          <p>登录后进入选品机会池，筛选、标记并推进关键词机会。</p>
          <form onSubmit={handleLogin} className="login-form">
            <label>
              <span>账号</span>
              <input value={loginAccount} onChange={(event) => setLoginAccount(event.target.value)} />
            </label>
            <label>
              <span>密码</span>
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
              />
            </label>
            {loginError && <div className="form-error">{loginError}</div>}
            <button className="button primary" type="submit">
              <Check size={16} />
              登录
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <BarChart3 size={20} />
          </div>
          <div>
            <strong>选品工作台</strong>
            <span>Product Selection</span>
          </div>
        </div>
        <nav className="nav-list">
          <button className={activeView === "opportunities" ? "nav-item active" : "nav-item"} onClick={showOpportunities}>
            <Filter size={17} />
            机会池
          </button>
          <button className={activeView === "favorites" ? "nav-item active" : "nav-item"} onClick={showFavorites}>
            <Bookmark size={17} />
            我的收藏
          </button>
          <button className={activeView === "compare" ? "nav-item active" : "nav-item"} onClick={showCompare}>
            <GitCompareArrows size={17} />
            横向对比
          </button>
          <button className={activeView === "exclusions" ? "nav-item active" : "nav-item"} onClick={showExclusions}>
            <Shield size={17} />
            禁用词
          </button>
        </nav>
        <div className="user-card">
          <span>{user.display_name}</span>
          <small>
            {user.account} / {user.role}
          </small>
          <button
            className="icon-text"
            onClick={() => {
              clearSession();
              setUser(null);
            }}
          >
            <LogOut size={15} />
            退出
          </button>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{pageTitle}</h1>
            <p>{pageSubtitle}</p>
          </div>
          <div className="topbar-actions">
            {dataAge && (activeView !== "exclusions" && activeView !== "compare") && (
              <span className="data-age" title="数据来自缓存，点击刷新获取最新数据">
                数据更新于 {minutesAgo(dataAge)} 分钟前
              </span>
            )}
            <button
              className="button secondary"
              onClick={() =>
                activeView === "exclusions"
                  ? void loadExclusions()
                  : activeView === "compare"
                    ? void loadKeywordCompare()
                    : void loadCandidates(true)
              }
            >
              <RefreshCw size={16} />
              刷新
            </button>
            {(activeView === "opportunities" || activeView === "favorites") && (
              <button className="button primary" onClick={() => void exportExcel()}>
                <Download size={16} />
                导出 Excel
              </button>
            )}
          </div>
        </header>

        {activeView === "exclusions" ? (
          <section className="admin-grid">
            <form className="exclusion-form apple-panel" onSubmit={submitExclusion}>
              <div className="filter-title">
                <Plus size={16} />
                新增禁用词
              </div>
              <div className="filter-grid compact">
                <Field label="禁用词">
                  <input
                    value={newExclusion.term}
                    onChange={(event) => setNewExclusion((prev) => ({ ...prev, term: event.target.value }))}
                    placeholder="输入品牌词、无关词或风险词"
                  />
                </Field>
                <Field label="匹配方式">
                  <AppleSelect
                    value={newExclusion.match_type}
                    options={matchTypeOptions}
                    ariaLabel="匹配方式"
                    onChange={(value) =>
                      setNewExclusion((prev) => ({ ...prev, match_type: value as "contains" | "exact" }))
                    }
                  />
                </Field>
                <Field label="规则类型">
                  <AppleSelect
                    value={newExclusion.exclusion_type}
                    options={exclusionTypeOptions}
                    ariaLabel="规则类型"
                    onChange={(value) => setNewExclusion((prev) => ({ ...prev, exclusion_type: value }))}
                  />
                </Field>
                <Field label="状态">
                  <AppleSelect
                    value={newExclusion.is_active ? "active" : "inactive"}
                    options={activeStateOptions}
                    ariaLabel="状态"
                    onChange={(value) => setNewExclusion((prev) => ({ ...prev, is_active: value === "active" }))}
                  />
                </Field>
                <Field label="原因">
                  <input
                    value={newExclusion.reason}
                    onChange={(event) => setNewExclusion((prev) => ({ ...prev, reason: event.target.value }))}
                    placeholder="例如：品牌限制、意图不相关"
                  />
                </Field>
              </div>
              <div className="filter-actions">
                <button className="button secondary" type="button" onClick={() => void loadExclusions()}>
                  <RefreshCw size={16} />
                  刷新
                </button>
                <button className="button primary" type="submit">
                  <Check size={16} />
                  保存规则
                </button>
              </div>
              {exclusionError && <div className="alert">{exclusionError}</div>}
            </form>

            <section className="table-shell">
              <div className="table-toolbar">
                <div>
                  <strong>禁用词规则</strong>
                  <span>共 {formatNumber(exclusions.length)} 条，命中后会从候选池中排除</span>
                </div>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>禁用词</th>
                      <th>类型</th>
                      <th>匹配方式</th>
                      <th>原因</th>
                      <th>状态</th>
                      <th>更新时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exclusionLoading ? (
                      Array.from({ length: 5 }).map((_, index) => (
                        <tr key={index}>
                          <td colSpan={7}>
                            <div className="skeleton" />
                          </td>
                        </tr>
                      ))
                    ) : exclusions.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="empty-cell">
                          暂无禁用词规则
                        </td>
                      </tr>
                    ) : (
                      exclusions.map((rule) => (
                        <tr key={rule.id}>
                          <td className="keyword-cell">
                            <strong>{rule.term}</strong>
                          </td>
                          <td>{exclusionTypeLabel(rule.exclusion_type)}</td>
                          <td>{rule.match_type === "contains" ? "包含匹配" : "完全匹配"}</td>
                          <td className="muted-cell">{rule.reason || "-"}</td>
                          <td>
                            <Tag tone={rule.is_active ? "success" : "neutral"}>{rule.is_active ? "启用" : "停用"}</Tag>
                          </td>
                          <td className="muted-cell">{new Date(rule.updated_at).toLocaleString("zh-CN")}</td>
                          <td>
                            <button className="button secondary" onClick={() => void toggleExclusion(rule)}>
                              {rule.is_active ? "停用" : "启用"}
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </section>
        ) : activeView === "compare" ? (
          <section className="admin-grid">
            <section className="metric-grid">
              <Metric label="对比月份数" value={formatNumber(compareMonths.length)} />
              <Metric label="当前页关键词" value={formatNumber(compareItems.length)} />
              <Metric label="平均末月搜索量" value={compareItems.length ? formatNumber(compareSummary.avgEndSearchVolume) : "-"} />
              <Metric label="平均增长率" value={compareItems.length ? formatGrowthPercent(compareSummary.avgGrowthRate) : "-"} />
              <Metric
                label="连续出现占比"
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
                      onChange={(event) => setCompareFilters((prev) => ({ ...prev, keyword: event.target.value }))}
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
                <Field label="至少出现月数">
                  <input
                    value={compareFilters.month_count_min}
                    onChange={(event) => updateCompareFilter("month_count_min", event.target.value)}
                  />
                </Field>
                <Field label="PPC上限">
                  <input
                    value={compareFilters.ppc_max}
                    onChange={(event) => updateCompareFilter("ppc_max", event.target.value)}
                  />
                </Field>
                <Field label="SPR上限">
                  <input
                    value={compareFilters.spr_max}
                    onChange={(event) => updateCompareFilter("spr_max", event.target.value)}
                  />
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
                      ...DEFAULT_COMPARE_FILTERS,
                      start_month: compareFilters.start_month,
                      end_month: compareFilters.end_month,
                      marketplace: compareFilters.marketplace,
                    })
                  }
                >
                  <X size={16} />
                  重置
                </button>
                <button className="button primary" onClick={() => void loadKeywordCompare()}>
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
                  <span>当前页 {compareItems.length} 条</span>
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
              <div className="table-scroll">
                <table className="compare-table">
                  <thead>
                    <tr>
                      <th>关键词</th>
                      <th>类目</th>
                      <th className="sparkline-th">趋势图</th>
                      <th>PPC</th>
                      <th>SPR</th>
                      <th>增长率</th>
                      <th>排名变化</th>
                      <th>出现月数</th>
                      <th>类型</th>
                      <th>历史排名参考</th>
                      <th>状态</th>
                      <th>操作</th>
                      {compareMonths.map((month) => (
                        <th key={month} className="monthly-col">{formatMonth(month)}搜索量</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {compareLoading ? (
                      Array.from({ length: 8 }).map((_, index) => (
                        <tr key={index}>
                          <td colSpan={13 + compareMonths.length}>
                            <div className="skeleton" />
                          </td>
                        </tr>
                      ))
                    ) : compareItems.length === 0 ? (
                      <tr>
                        <td colSpan={13 + compareMonths.length} className="empty-cell">
                          没有符合条件的横向对比关键词
                        </td>
                      </tr>
                    ) : (
                      compareItems.map((item) => {
                        const monthlyMap = new Map(item.monthly.map((month) => [month.data_month.slice(0, 10), month]));
                        const volumes = compareMonths.map((m) => monthlyMap.get(m)?.search_volume ?? null);
                        return (
                          <tr key={`${item.keyword_id}-${item.marketplace}`}>
                            <td className="keyword-cell">
                              <button className="keyword-button" type="button">
                                {item.keyword}
                              </button>
                              <span>{item.keyword_translation || "-"}</span>
                            </td>
                            <td className="muted-cell">{item.category || "-"}</td>
                            <td className="sparkline-cell">
                              <Sparkline volumes={volumes} width={120} height={32} />
                            </td>
                            <td>{item.ppc_bid_mid ?? "-"}</td>
                            <td>{item.spr ?? "-"}</td>
                            <td>
                              <strong className={(item.search_volume_growth_rate ?? 0) >= 0 ? "positive" : "negative"}>
                                {formatGrowthPercent(item.search_volume_growth_rate)}
                              </strong>
                              <small className="level">
                                {formatNumber(item.start_search_volume)} → {formatNumber(item.end_search_volume)}
                              </small>
                            </td>
                            <td>
                              {item.rank_change === null || item.rank_change === undefined
                                ? "-"
                                : item.rank_change > 0
                                  ? `提升 ${formatNumber(item.rank_change)}`
                                  : item.rank_change < 0
                                    ? `下降 ${formatNumber(Math.abs(item.rank_change))}`
                                    : "持平"}
                              <small className="level">
                                {formatNumber(item.start_rank)} → {formatNumber(item.end_rank)}
                              </small>
                            </td>
                            <td>
                              {item.month_count} / {item.total_months}
                            </td>
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
                            <td className="history-rank-cell">
                              上月 {formatNumber(item.prev_month_rank)} / 4月前{" "}
                              {formatNumber(item.four_months_ago_rank)} / 12月前{" "}
                              {formatNumber(item.twelve_months_ago_rank)}
                            </td>
                            <td>
                              <AppleSelect
                                compact
                                value={item.user_status || "new"}
                                options={statusOptions}
                                ariaLabel={`${item.keyword} 当前状态 ${statusLabel(item.user_status)}`}
                                onChange={(value) => void changeCompareState(item, value)}
                              />
                            </td>
                            <td>
                              <div className="row-actions">
                                <button className="icon-button" onClick={() => void toggleCompareFavorite(item)} title="收藏">
                                  <Star size={16} fill={item.user_is_favorite ? "currentColor" : "none"} />
                                </button>
                                <button
                                  className="icon-button"
                                  onClick={() => void addCompareKeywordToExclusion(item)}
                                  title="加入禁用词"
                                >
                                  <Shield size={16} />
                                </button>
                              </div>
                            </td>
                            {compareMonths.map((month) => {
                              const row = monthlyMap.get(month);
                              return <td key={month} className="monthly-col">{formatNumber(row?.search_volume)}</td>;
                            })}
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
              <div className="pagination">
                <button
                  className="button secondary"
                  disabled={compareFilters.page <= 1}
                  onClick={() => updateCompareFilter("page", compareFilters.page - 1)}
                >
                  <ChevronLeft size={16} />
                  上一页
                </button>
                <span>第 {compareFilters.page} 页</span>
                <form className="page-jump" onSubmit={submitComparePageJump}>
                  <label htmlFor="compare-page-jump-input">跳至</label>
                  <input
                    id="compare-page-jump-input"
                    type="number"
                    min={1}
                    value={comparePageJump}
                    onChange={(event) => setComparePageJump(event.target.value)}
                  />
                  <button className="button secondary" type="submit">
                    跳转
                  </button>
                </form>
                <button
                  className="button secondary"
                  disabled={!comparePagination.has_more}
                  onClick={() => updateCompareFilter("page", compareFilters.page + 1)}
                >
                  下一页
                  <ChevronRight size={16} />
                </button>
              </div>
            </section>
          </section>
        ) : (
          <>
        <section className="scope-bar apple-panel" aria-label="运营模式">
          {scopeOptions.map((option) => (
            <button
              key={option.value}
              className={option.value === dataScope ? "scope-option active" : "scope-option"}
              onClick={() => changeScope(option.value)}
            >
              <strong>{option.label}</strong>
              <span>{option.description}</span>
            </button>
          ))}
        </section>

        <section className="metric-grid">
          <Metric label="月份全量" value={formatNumber(currentMonth?.keyword_count)} />
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
                  value={filters.keyword}
                  onChange={(event) => setFilters((prev) => ({ ...prev, keyword: event.target.value }))}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") updateFilter("page", 1);
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
                <input value={filters.score_min} onChange={(event) => updateFilter("score_min", event.target.value)} />
                <span>-</span>
                <input value={filters.score_max} onChange={(event) => updateFilter("score_max", event.target.value)} />
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
            <Field label="PPC上限">
              <input value={filters.ppc_max} onChange={(event) => updateFilter("ppc_max", event.target.value)} />
            </Field>
            <Field label="SPR上限">
              <input value={filters.spr_max} onChange={(event) => updateFilter("spr_max", event.target.value)} />
            </Field>
          </div>
          <div className="filter-actions">
            <button
              className="button secondary"
              onClick={() =>
                setFilters({
                  ...DEFAULT_FILTERS,
                  ...getScopePatch(dataScope),
                  analysis_month: filters.analysis_month,
                  marketplace: filters.marketplace,
                  favorite_only: activeView === "favorites" ? "true" : "",
                })
              }
            >
              <X size={16} />
              重置
            </button>
            <button className="button primary" onClick={() => void loadCandidates()}>
              <Search size={16} />
              查询
            </button>
          </div>
        </section>

        {error && <div className="alert">{error}</div>}

        {!isCached && (activeView === "opportunities" || activeView === "favorites") && (
          <div className="alert warning">
            当前月份使用实时计算，查询较慢。建议运行 <code>calculate_trends.py</code> 生成缓存以提升速度。
          </div>
        )}

        <section className="table-shell">
          <div className="table-toolbar">
            <div>
              <strong>{activeView === "favorites" ? `${currentScope.label}收藏清单` : `${currentScope.label}清单`}</strong>
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
                  sort_by: prev.sort_by === "search_volume" ? "product_selection_score" : "search_volume",
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
                {loading
                  ? Array.from({ length: 8 }).map((_, index) => (
                      <tr key={index}>
                        <td colSpan={10}>
                          <div className="skeleton" />
                        </td>
                      </tr>
                    ))
                  : items.length === 0 ? (
                      <tr>
                        <td colSpan={10} className="empty-cell">
                          {activeView === "favorites" ? "还没有收藏关键词" : "没有符合条件的关键词"}
                        </td>
                      </tr>
                    )
                  : items.map((item) => (
                      <tr key={`${item.keyword_id}-${item.analysis_month}-${item.marketplace}`}>
                        <td className="keyword-cell">
                          <button className="keyword-button" onClick={() => void openDetail(item)}>
                            {item.keyword}
                          </button>
                          <span>{item.keyword_translation || "-"}</span>
                        </td>
                        <td className="muted-cell">{item.category}</td>
                        <td>{formatNumber(item.search_volume)}</td>
                        <td>
                          <Tag tone={item.trend_label === "rising" ? "success" : "neutral"}>{item.trend_label_cn || "-"}</Tag>
                        </td>
                        <td>
                          <strong>{item.product_selection_score ?? "-"}</strong>
                          <small className="level">{item.candidate_level_cn || "-"}</small>
                        </td>
                        <td className="reason-cell">{item.exclusion_reason_cn || item.selection_segment_cn || "-"}</td>
                        <td>{item.ppc_bid_mid ?? "-"}</td>
                        <td>{item.spr ?? "-"}</td>
                        <td>
                          <AppleSelect
                            compact
                            value={item.user_status || "new"}
                            options={statusOptions}
                            ariaLabel={`${item.keyword} 当前状态 ${statusLabel(item.user_status)}`}
                            onChange={(value) => void changeState(item, value)}
                          />
                        </td>
                        <td>
                          <div className="row-actions">
                            <button className="icon-button" onClick={() => void toggleFavorite(item)} title="收藏">
                              <Star size={16} fill={item.user_is_favorite ? "currentColor" : "none"} />
                            </button>
                            <button className="icon-button" onClick={() => void openDetail(item)} title="详情">
                              <Eye size={16} />
                            </button>
                            <button className="icon-button" onClick={() => void addKeywordToExclusion(item)} title="加入禁用词">
                              <Shield size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <button className="button secondary" disabled={filters.page <= 1} onClick={() => updateFilter("page", filters.page - 1)}>
              <ChevronLeft size={16} />
              上一页
            </button>
            <span>
              {filters.page} / {totalPages}
            </span>
            <form className="page-jump" onSubmit={submitPageJump}>
              <label htmlFor="page-jump-input">跳至</label>
              <input
                id="page-jump-input"
                type="number"
                min={1}
                max={totalPages}
                value={pageJump}
                onChange={(event) => setPageJump(event.target.value)}
              />
              <button className="button secondary" type="submit">
                跳转
              </button>
            </form>
            <button
              className="button secondary"
              disabled={filters.page >= totalPages}
              onClick={() => updateFilter("page", filters.page + 1)}
            >
              下一页
              <ChevronRight size={16} />
            </button>
          </div>
        </section>
          </>
        )}
      </main>

      {selected && (
        <aside className="drawer">
          <div className="drawer-header">
            <div>
              <h2>{selected.keyword}</h2>
              <p>{selected.keyword_translation || "暂无中文释义"}</p>
            </div>
            <button className="icon-button" onClick={() => setSelected(null)}>
              <X size={18} />
            </button>
          </div>
          <div className="detail-grid">
            <Metric label="搜索量" value={formatNumber(selected.search_volume)} compact />
            <Metric label="选品分" value={String(selected.product_selection_score ?? "-")} compact />
            <Metric label="点击份额" value={formatPercent(selected.click_share)} compact />
            <Metric label="转化份额" value={formatPercent(selected.conversion_share)} compact />
          </div>
          <div className="drawer-actions">
            <button className="button secondary" onClick={() => void toggleFavorite(selected)}>
              <Star size={16} fill={selected.user_is_favorite ? "currentColor" : "none"} />
              {selected.user_is_favorite ? "取消收藏" : "收藏关键词"}
            </button>
            <button className="button secondary" onClick={() => void addKeywordToExclusion(selected)}>
              <Shield size={16} />
              加入禁用词
            </button>
          </div>
          <section className="drawer-section">
            <h3>多月变化</h3>
            <div className="mini-table">
              {detail?.monthly.map((row) => (
                <div key={row.data_month}>
                  <span>{row.data_month.slice(0, 7)}</span>
                  <strong>{formatNumber(row.search_volume)}</strong>
                  <small>{row.trend_label_cn || "-"}</small>
                </div>
              ))}
            </div>
          </section>
          <section className="drawer-section">
            <h3>
              <MessageSquare size={16} />
              备注
            </h3>
            <textarea value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="写下调研判断、风险或动作" />
            <button className="button primary" onClick={() => void saveNote()}>
              保存备注
            </button>
            <div className="note-list">
              {detail?.notes.map((note) => (
                <article key={note.id}>
                  <strong>{note.display_name}</strong>
                  <p>{note.note}</p>
                  <span>{new Date(note.created_at).toLocaleString("zh-CN")}</span>
                </article>
              ))}
            </div>
          </section>
        </aside>
      )}
      {dbOperationCount > 0 && (
        <div className="query-toast" role="status" aria-live="polite">
          <span className="query-spinner" />
          <div>
            <strong>{dbOperationMessage || "正在查询数据库"}</strong>
            <small>请稍候，数据正在处理中</small>
          </div>
        </div>
      )}
    </div>
  );
}

function Sparkline({ volumes, width, height }: { volumes: (number | null)[]; width: number; height: number }) {
  const valid = volumes.filter((v): v is number => v !== null && v > 0);
  if (valid.length < 2) {
    return <span className="sparkline-empty">-</span>;
  }
  const min = Math.min(...valid);
  const max = Math.max(...valid);
  const range = max - min || 1; // avoid division by zero
  const pad = 3; // top/bottom padding in px
  const h = height - pad * 2;
  const stepX = valid.length > 1 ? (width - 4) / (valid.length - 1) : 0;
  const points = valid
    .map((v, i) => {
      const x = 2 + i * stepX;
      const y = pad + h - ((v - min) / range) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} width={width} height={height}>
      <polyline
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
      {valid.map((v, i) => {
        const x = 2 + i * stepX;
        const y = pad + h - ((v - min) / range) * h;
        return <circle key={i} cx={x} cy={y} r="2" fill="var(--accent)" />;
      })}
    </svg>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function Metric({ label, value, compact = false }: { label: string; value: string; compact?: boolean }) {
  return (
    <div className={compact ? "metric compact" : "metric apple-panel"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Tag({ children, tone }: { children: React.ReactNode; tone: "success" | "neutral" | "danger" | "warning" | "info" }) {
  return <span className={`tag ${tone}`}>{children}</span>;
}
