import { Download, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  addHolidayTerms,
  createClipboardItem,
  createHolidayEvent,
  downloadCandidateExport,
  downloadExportFile,
  deleteClipboardItem,
  deleteHolidayTerm,
  getExportCount,
  clearCandidateCache,
  clearSession,
  createExclusion,
  createCandidateNote,
  getCandidateDetail,
  getCandidates,
  getCategories,
  getClipboardItems,
  getExclusions,
  getHolidayEvents,
  getKeywordCompare,
  refreshHolidayTags,
  getMe,
  getMonths,
  login,
  readUser,
  saveSession,
  updateExclusion,
  updateHolidayEvent,
  updateCandidateState,
} from "./api";
import { ClipboardView } from "./components/ClipboardView";
import { CompareView } from "./components/CompareView";
import { DetailDrawer } from "./components/DetailDrawer";
import { ExclusionsView } from "./components/ExclusionsView";
import type { NewExclusion } from "./components/ExclusionsView";
import { ExportView, EXPORT_SINGLE_FILE_LIMIT } from "./components/ExportView";
import type { ExportFilters } from "./components/ExportView";
import { HolidayLexiconView } from "./components/HolidayLexiconView";
import { LoginView } from "./components/LoginView";
import { OpportunitiesView } from "./components/OpportunitiesView";
import type { DataScope } from "./components/OpportunitiesView";
import { DEFAULT_SCOPE, getScopePatch } from "./components/OpportunitiesView";
import { Sidebar } from "./components/Sidebar";
import type { ActiveView } from "./components/Sidebar";
import type { SelectOption } from "./components/AppleSelect";
import { minutesAgo } from "./utils";
import type {
  Candidate,
  CandidateDetail,
  CandidateFilters,
  CategoryItem,
  ClipboardItem,
  ExclusionRule,
  HolidayEvent,
  HolidayTerm,
  KeywordCompareFilters,
  KeywordCompareItem,
  MonthItem,
  Pagination,
  User,
} from "./types";

// ── Local types ──────────────────────────────────────────────
type ListView = Exclude<ActiveView, "compare" | "exclusions" | "export" | "clipboard" | "holidayLexicon">;
type ListViewState = { filters: CandidateFilters; dataScope: DataScope };

// ── Shared constants ─────────────────────────────────────────
const DEFAULT_EXPORT_MAX_ROWS = EXPORT_SINGLE_FILE_LIMIT;

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
  ppc_min: "",
  ppc_max: "",
  spr_min: "",
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
  month_count_min: "",
  month_count_max: "",
  ppc_min: "",
  ppc_max: "",
  spr_min: "",
  spr_max: "",
  sort_by: "end_search_volume",
  sort_order: "desc",
};

// ── Shared option arrays ─────────────────────────────────────
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

// ── App component ────────────────────────────────────────────
export function App() {
  // Auth
  const [user, setUser] = useState<User | null>(() => readUser());
  const [loginAccount, setLoginAccount] = useState("admin");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  // Candidates
  const [filters, setFilters] = useState<CandidateFilters>(DEFAULT_FILTERS);
  const [dataScope, setDataScope] = useState<DataScope>(DEFAULT_SCOPE);
  const [items, setItems] = useState<Candidate[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [totalIsEstimated, setTotalIsEstimated] = useState(false);
  const [totalLabel, setTotalLabel] = useState<"estimated" | "lower_bound" | "exact">("exact");
  const [pageJump, setPageJump] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dataAge, setDataAge] = useState<number | null>(null);
  const [isCached, setIsCached] = useState(true);

  // Compare
  const [compareFilters, setCompareFilters] = useState<KeywordCompareFilters>(DEFAULT_COMPARE_FILTERS);
  const [compareItems, setCompareItems] = useState<KeywordCompareItem[]>([]);
  const [compareMonths, setCompareMonths] = useState<string[]>([]);
  const [comparePagination, setComparePagination] = useState<Pagination>({
    page: 1, page_size: DEFAULT_COMPARE_FILTERS.page_size, total: 0, total_pages: 1,
  });
  const [comparePageJump, setComparePageJump] = useState("1");
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState("");

  // Exclusions
  const [exclusions, setExclusions] = useState<ExclusionRule[]>([]);
  const [exclusionLoading, setExclusionLoading] = useState(false);
  const [exclusionError, setExclusionError] = useState("");
  const [newExclusion, setNewExclusion] = useState<NewExclusion>({
    term: "", match_type: "contains", exclusion_type: "brand", reason: "", is_active: true,
  });

  // Clipboard
  const [clipboardItems, setClipboardItems] = useState<ClipboardItem[]>([]);
  const [clipboardLoading, setClipboardLoading] = useState(false);
  const [clipboardError, setClipboardError] = useState("");

  // Holiday lexicon
  const [holidayEvents, setHolidayEvents] = useState<HolidayEvent[]>([]);
  const [holidayLoading, setHolidayLoading] = useState(false);
  const [holidayError, setHolidayError] = useState("");

  // Export
  const [exportSource, setExportSource] = useState<"candidates" | "compare">("candidates");
  const [exportFilename, setExportFilename] = useState("选品候选词");
  const [exportFormat, setExportFormat] = useState<"xlsx" | "csv">("xlsx");
  const [exportMaxRows, setExportMaxRows] = useState(DEFAULT_EXPORT_MAX_ROWS);
  const [exportCount, setExportCount] = useState<number | null>(null);
  const [exportCountEstimated, setExportCountEstimated] = useState(false);
  const [exportCountLabel, setExportCountLabel] = useState<string>("exact");
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState("");
  const [exportFilters, setExportFilters] = useState<ExportFilters>({
    analysis_month: "", marketplace: "UK", keyword: "", category: "",
    trend_label: "", candidate_level: "", is_candidate: "", favorite_only: "",
    search_volume_min: "", search_volume_max: "", score_min: "", score_max: "",
    ppc_min: "", ppc_max: "", spr_min: "", spr_max: "",
    start_month: "", end_month: "", trend_type: "", growth_rate_min: "", growth_rate_max: "",
    month_count_min: "", month_count_max: "", sort_by: "product_selection_score",
  });

  // Detail drawer
  const [selected, setSelected] = useState<Candidate | null>(null);
  const [detail, setDetail] = useState<CandidateDetail | null>(null);
  const [noteDraft, setNoteDraft] = useState("");

  // Global
  const [activeView, setActiveView] = useState<ActiveView>("opportunities");
  const [months, setMonths] = useState<MonthItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [dbOperationCount, setDbOperationCount] = useState(0);
  const [dbOperationMessage, setDbOperationMessage] = useState("");

  const listViewSnapshots = useRef<Record<ListView, ListViewState>>({
    opportunities: { filters: { ...DEFAULT_FILTERS }, dataScope: DEFAULT_SCOPE },
    favorites: { filters: { ...DEFAULT_FAVORITE_FILTERS }, dataScope: "all" },
  });

  // ── Effects ──────────────────────────────────────────────

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
    user, activeView,
    filters.page, filters.page_size, filters.analysis_month, filters.marketplace,
    filters.category, filters.trend_label, filters.candidate_level,
    filters.selection_segment, filters.is_candidate, filters.favorite_only,
    filters.search_volume_min, filters.search_volume_max,
    filters.score_min, filters.score_max,
    filters.ppc_min, filters.ppc_max, filters.spr_min, filters.spr_max,
    filters.sort_by, filters.sort_order,
  ]);

  useEffect(() => {
    if (!user || activeView !== "exclusions") return;
    void loadExclusions();
  }, [user, activeView]);

  useEffect(() => {
    if (!user || activeView !== "clipboard") return;
    void loadClipboardItems();
  }, [user, activeView]);

  useEffect(() => {
    if (!user || activeView !== "holidayLexicon") return;
    void loadHolidayEvents();
  }, [user, activeView]);

  useEffect(() => {
    if (!user || activeView !== "compare" || !compareFilters.start_month || !compareFilters.end_month) return;
    void loadKeywordCompare();
  }, [
    user, activeView,
    compareFilters.page, compareFilters.page_size,
    compareFilters.start_month, compareFilters.end_month, compareFilters.marketplace,
    compareFilters.category, compareFilters.trend_type, compareFilters.keyword,
    compareFilters.search_volume_min, compareFilters.search_volume_max,
    compareFilters.growth_rate_min, compareFilters.growth_rate_max,
    compareFilters.month_count_min, compareFilters.month_count_max,
    compareFilters.ppc_min, compareFilters.ppc_max,
    compareFilters.spr_min, compareFilters.spr_max,
    compareFilters.sort_by, compareFilters.sort_order,
  ]);

  useEffect(() => {
    setPageJump(String(filters.page));
  }, [filters.page]);

  useEffect(() => {
    setComparePageJump(String(compareFilters.page));
  }, [compareFilters.page]);

  // ── Computed values ─────────────────────────────────────

  const summary = useMemo(() => {
    const levelA = items.filter((item) => item.candidate_level_cn === "A级").length;
    const favorites = items.filter((item) => item.user_is_favorite).length;
    const avgScore =
      items.length === 0
        ? 0
        : items.reduce((sum, item) => sum + (item.product_selection_score ?? 0), 0) / items.length;
    return { levelA, favorites, avgScore };
  }, [items]);

  const currentMonth = months.find(
    (item) => item.data_month.slice(0, 10) === filters.analysis_month && item.marketplace === filters.marketplace,
  );

  const pageTitle =
    activeView === "favorites" ? "我的收藏"
    : activeView === "compare" ? "关键词横向对比"
    : activeView === "exclusions" ? "禁用词管理"
    : activeView === "export" ? "数据导出"
    : activeView === "clipboard" ? "共享粘贴板"
    : activeView === "holidayLexicon" ? "节日词库"
    : "选品机会池";

  const pageSubtitle =
    activeView === "favorites" ? "集中查看已收藏关键词，继续调研、标记状态或导出清单。"
    : activeView === "compare" ? "按所选月份区间实时对比相同关键词的搜索量、排名变化、出现连续性和趋势类型。"
    : activeView === "exclusions" ? "维护品牌词、无关词和风险词，启用后会从候选池中排除。"
    : activeView === "export" ? "选择数据来源和筛选条件，预览条数后导出为 Excel 或 CSV 文件。"
    : activeView === "clipboard" ? "在手机和电脑之间临时同步文本、文件内容和脚本片段。"
    : activeView === "holidayLexicon" ? "维护万圣节、圣诞节等节日词库，并定义对应的趋势验证窗口。"
    : "在全量词库、候选词库和高优先级机会之间切换，明确区分数据总量和当前筛选结果。";

  const effectiveExportMaxRows = Math.min(Math.max(exportMaxRows || 1, 1), EXPORT_SINGLE_FILE_LIMIT);
  const exportRowsThisRun = exportCount === null ? effectiveExportMaxRows : Math.min(exportCount, effectiveExportMaxRows);
  const exportWouldTruncate = exportCount !== null && exportCount > exportRowsThisRun;
  const exportExceedsSingleFileLimit = exportCount !== null && exportCount > EXPORT_SINGLE_FILE_LIMIT;

  // ── Helper ──────────────────────────────────────────────

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

  // ── Handlers: auth ──────────────────────────────────────

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

  function handleLogout() {
    clearSession();
    setUser(null);
  }

  // ── Handlers: navigation ────────────────────────────────

  function rememberCurrentListView() {
    if (activeView !== "opportunities" && activeView !== "favorites") return;
    listViewSnapshots.current[activeView] = { filters: { ...filters }, dataScope };
  }

  function restoreListView(view: ListView) {
    if (activeView === view) return;
    rememberCurrentListView();
    const snapshot = listViewSnapshots.current[view];
    setDataScope(snapshot.dataScope);
    setFilters({ ...snapshot.filters, favorite_only: view === "favorites" ? "true" : "" });
    setActiveView(view);
  }

  function handleNavigate(view: ActiveView) {
    if (view === "opportunities") restoreListView("opportunities");
    else if (view === "favorites") restoreListView("favorites");
    else {
      rememberCurrentListView();
      setActiveView(view);
    }
  }

  // ── Handlers: candidates ────────────────────────────────

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

  function updateFilter<K extends keyof CandidateFilters>(key: K, value: CandidateFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value, page: key === "page" ? (value as number) : 1 }));
  }

  function changeScope(scope: DataScope) {
    setDataScope(scope);
    setFilters((prev) => ({ ...prev, ...getScopePatch(scope), page: 1 }));
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

  async function addKeywordToExclusion(candidate: Candidate) {
    const finishDbOperation = beginDbOperation("正在加入禁用词");
    const reason = `运营从关键词清单加入：${candidate.keyword_translation || candidate.category || ""}`.trim();
    setNewExclusion((prev) => ({
      ...prev, term: candidate.keyword, match_type: "exact", exclusion_type: "irrelevant", reason, is_active: true,
    }));
    setActiveView("exclusions");
    try {
      await createExclusion({ term: candidate.keyword, match_type: "exact", exclusion_type: "irrelevant", reason, is_active: true });
      await loadExclusions();
    } catch (err) {
      setExclusionError(err instanceof Error ? err.message : "加入禁用词失败");
    } finally {
      finishDbOperation();
    }
  }

  // ── Handlers: compare ───────────────────────────────────

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

  function updateCompareFilter<K extends keyof KeywordCompareFilters>(key: K, value: KeywordCompareFilters[K]) {
    setCompareFilters((prev) => ({ ...prev, [key]: value, page: key === "page" ? (value as number) : 1 }));
  }

  async function changeCompareState(item: KeywordCompareItem, status: string) {
    const finishDbOperation = beginDbOperation("正在保存横向对比关键词状态");
    try {
      await updateCandidateState(item.keyword_id, {
        analysis_month: item.last_month, marketplace: item.marketplace, status,
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
        analysis_month: item.last_month, marketplace: item.marketplace,
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
      await createExclusion({ term: item.keyword, match_type: "exact", exclusion_type: "irrelevant", reason, is_active: true });
      await loadKeywordCompare();
    } catch (err) {
      setCompareError(err instanceof Error ? err.message : "加入禁用词失败");
    } finally {
      finishDbOperation();
    }
  }

  // ── Handlers: exclusions ────────────────────────────────

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
      setNewExclusion({ term: "", match_type: "contains", exclusion_type: "brand", reason: "", is_active: true });
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

  // ── Handlers: detail drawer ─────────────────────────────

  // ── Handlers: clipboard ───────────────────────────────────────────────

  async function loadClipboardItems() {
    const finishDbOperation = beginDbOperation("正在读取共享粘贴板");
    setClipboardLoading(true);
    setClipboardError("");
    try {
      const data = await getClipboardItems();
      setClipboardItems(data.items);
    } catch (err) {
      setClipboardError(err instanceof Error ? err.message : "共享粘贴板加载失败");
    } finally {
      setClipboardLoading(false);
      finishDbOperation();
    }
  }

  async function createSharedClipboardItem(payload: { title: string; content: string }) {
    const finishDbOperation = beginDbOperation("正在发送到共享粘贴板");
    setClipboardError("");
    try {
      await createClipboardItem(payload);
      await loadClipboardItems();
    } catch (err) {
      setClipboardError(err instanceof Error ? err.message : "发送失败");
      throw err;
    } finally {
      finishDbOperation();
    }
  }

  async function removeSharedClipboardItem(item: ClipboardItem) {
    if (!window.confirm(`删除「${item.title || "未命名内容"}」？`)) return;
    const finishDbOperation = beginDbOperation("正在删除共享粘贴内容");
    setClipboardError("");
    try {
      await deleteClipboardItem(item.id);
      await loadClipboardItems();
    } catch (err) {
      setClipboardError(err instanceof Error ? err.message : "删除失败");
    } finally {
      finishDbOperation();
    }
  }

  // ── Handlers: holiday lexicon ─────────────────────────────────────────

  async function loadHolidayEvents() {
    const finishDbOperation = beginDbOperation("正在读取节日词库");
    setHolidayLoading(true);
    setHolidayError("");
    try {
      const data = await getHolidayEvents();
      setHolidayEvents(data.items);
    } catch (err) {
      setHolidayError(err instanceof Error ? err.message : "节日词库加载失败");
    } finally {
      setHolidayLoading(false);
      finishDbOperation();
    }
  }

  async function submitHolidayEvent(payload: {
    code: string;
    name_cn: string;
    name_en: string;
    marketplace: string;
    trend_start_month: number;
    trend_end_month: number;
    min_growth_rate: number;
    terms: string[];
  }) {
    const finishDbOperation = beginDbOperation("正在保存节日词库");
    setHolidayError("");
    try {
      const data = await createHolidayEvent(payload);
      setHolidayEvents(data.items);
    } catch (err) {
      setHolidayError(err instanceof Error ? err.message : "新增节日失败");
      throw err;
    } finally {
      finishDbOperation();
    }
  }

  async function submitHolidayTerms(event: HolidayEvent, terms: string[]) {
    const finishDbOperation = beginDbOperation("正在添加节日词条");
    setHolidayError("");
    try {
      const data = await addHolidayTerms(event.id, terms);
      setHolidayEvents(data.items);
    } catch (err) {
      setHolidayError(err instanceof Error ? err.message : "添加词条失败");
      throw err;
    } finally {
      finishDbOperation();
    }
  }

  async function updateHolidayConditions(
    event: HolidayEvent,
    payload: {
      name_cn: string;
      name_en: string;
      marketplace: string;
      trend_start_month: number;
      trend_end_month: number;
      min_growth_rate: number;
    },
  ) {
    const finishDbOperation = beginDbOperation("正在保存节日条件");
    setHolidayError("");
    try {
      const data = await updateHolidayEvent(event.id, payload);
      setHolidayEvents(data.items);
    } catch (err) {
      setHolidayError(err instanceof Error ? err.message : "保存节日条件失败");
      throw err;
    } finally {
      finishDbOperation();
    }
  }

  async function removeHolidayTerm(term: HolidayTerm): Promise<boolean> {
    if (!window.confirm(`删除词条「${term.term}」？`)) return false;
    const finishDbOperation = beginDbOperation("正在删除节日词条");
    setHolidayError("");
    try {
      const data = await deleteHolidayTerm(term.id);
      setHolidayEvents(data.items);
      return true;
    } catch (err) {
      setHolidayError(err instanceof Error ? err.message : "删除词条失败");
      throw err;
    } finally {
      finishDbOperation();
    }
  }

  async function toggleHolidayEvent(event: HolidayEvent) {
    const finishDbOperation = beginDbOperation(event.is_active ? "正在停用节日词库" : "正在启用节日词库");
    setHolidayError("");
    try {
      const data = await updateHolidayEvent(event.id, { is_active: !event.is_active });
      setHolidayEvents(data.items);
    } catch (err) {
      setHolidayError(err instanceof Error ? err.message : "更新节日状态失败");
      throw err;
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

  // ── Handlers: export ────────────────────────────────────

  async function exportExcel() {
    const finishDbOperation = beginDbOperation("正在导出 Excel");
    setExportLoading(true);
    setExportError("");
    try {
      const blob = await downloadCandidateExport(filters, "选品候选词", 5000);
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "选品候选词.xlsx";
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "导出失败");
    } finally {
      setExportLoading(false);
      finishDbOperation();
    }
  }

  async function handleExportPreviewCount() {
    setExportLoading(true);
    setExportError("");
    try {
      const data = await getExportCount({ source: exportSource, ...exportFilters });
      setExportCount(data.count);
      setExportCountEstimated(Boolean(data.total_is_estimated));
      setExportCountLabel(data.total_label ?? "exact");
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "查询失败");
    } finally {
      setExportLoading(false);
    }
  }

  async function handleExportDownload() {
    const finishDbOperation = beginDbOperation("正在导出文件");
    setExportLoading(true);
    setExportError("");
    try {
      const blob = await downloadExportFile(
        { source: exportSource, ...exportFilters },
        exportFormat,
        exportFilename || "export",
        effectiveExportMaxRows,
      );
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${exportFilename || "export"}.${exportFormat}`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "下载失败");
    } finally {
      setExportLoading(false);
      finishDbOperation();
    }
  }

  function handleClearExportPreview() {
    setExportCount(null);
    setExportError("");
  }

  // ── Render ──────────────────────────────────────────────

  if (!user) {
    return (
      <LoginView
        loginAccount={loginAccount}
        setLoginAccount={setLoginAccount}
        loginPassword={loginPassword}
        setLoginPassword={setLoginPassword}
        loginError={loginError}
        onLogin={handleLogin}
      />
    );
  }

  return (
    <div className="app-shell">
      <Sidebar
        user={user}
        activeView={activeView}
        onNavigate={handleNavigate}
        onLogout={handleLogout}
      />

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{pageTitle}</h1>
            <p>{pageSubtitle}</p>
          </div>
          <div className="topbar-actions">
            {dataAge && activeView !== "exclusions" && activeView !== "compare" && activeView !== "clipboard" && activeView !== "holidayLexicon" && (
              <span className="data-age" title="数据来自缓存，点击刷新获取最新数据">
                数据更新于 {minutesAgo(dataAge)} 分钟前
              </span>
            )}
            <button
              className="button secondary"
              onClick={() => {
                if (activeView === "exclusions") void loadExclusions();
                else if (activeView === "compare") void loadKeywordCompare();
                else if (activeView === "clipboard") void loadClipboardItems();
                else if (activeView === "holidayLexicon") void loadHolidayEvents();
                else void loadCandidates(true);
              }}
            >
              <RefreshCw size={16} />
              刷新
            </button>
            {(activeView === "opportunities" || activeView === "favorites") && (
              <button className="button primary" disabled={exportLoading} onClick={() => void exportExcel()}>
                <Download size={16} />
                {exportLoading ? "正在导出..." : "导出 Excel"}
              </button>
            )}
          </div>
        </header>

        {activeView === "exclusions" ? (
          <ExclusionsView
            newExclusion={newExclusion}
            setNewExclusion={setNewExclusion}
            matchTypeOptions={matchTypeOptions}
            exclusionTypeOptions={exclusionTypeOptions}
            activeStateOptions={activeStateOptions}
            exclusionError={exclusionError}
            exclusions={exclusions}
            exclusionLoading={exclusionLoading}
            onSubmitExclusion={submitExclusion}
            onRefresh={() => void loadExclusions()}
            onToggleExclusion={toggleExclusion}
          />
        ) : activeView === "compare" ? (
          <CompareView
            compareFilters={compareFilters}
            updateCompareFilter={updateCompareFilter}
            setCompareFilters={setCompareFilters}
            months={months}
            categories={categories}
            compareItems={compareItems}
            compareMonths={compareMonths}
            comparePagination={comparePagination}
            compareLoading={compareLoading}
            compareError={compareError}
            comparePageJump={comparePageJump}
            setComparePageJump={setComparePageJump}
            compareTrendOptions={compareTrendOptions}
            compareSortOptions={compareSortOptions}
            onLoadData={() => void loadKeywordCompare()}
            onChangeState={changeCompareState}
            onToggleFavorite={toggleCompareFavorite}
            onAddExclusion={addCompareKeywordToExclusion}
          />
        ) : activeView === "export" ? (
          <ExportView
            exportSource={exportSource}
            setExportSource={setExportSource}
            exportFilters={exportFilters}
            setExportFilters={setExportFilters}
            months={months}
            categories={categories}
            trendOptions={trendOptions}
            candidateLevelOptions={candidateLevelOptions}
            compareTrendOptions={compareTrendOptions}
            compareSortOptions={compareSortOptions}
            exportCount={exportCount}
            exportCountEstimated={exportCountEstimated}
            exportCountLabel={exportCountLabel}
            exportLoading={exportLoading}
            exportError={exportError}
            setExportError={setExportError}
            exportFilename={exportFilename}
            setExportFilename={setExportFilename}
            exportFormat={exportFormat}
            setExportFormat={setExportFormat}
            exportMaxRows={exportMaxRows}
            setExportMaxRows={setExportMaxRows}
            effectiveExportMaxRows={effectiveExportMaxRows}
            exportRowsThisRun={exportRowsThisRun}
            exportWouldTruncate={exportWouldTruncate}
            exportExceedsSingleFileLimit={exportExceedsSingleFileLimit}
            onPreviewCount={handleExportPreviewCount}
            onDownload={handleExportDownload}
            onClearPreview={handleClearExportPreview}
          />
        ) : activeView === "clipboard" ? (
          <ClipboardView
            user={user}
            items={clipboardItems}
            loading={clipboardLoading}
            error={clipboardError}
            onRefresh={() => void loadClipboardItems()}
            onCreate={createSharedClipboardItem}
            onDelete={removeSharedClipboardItem}
          />
        ) : activeView === "holidayLexicon" ? (
          <HolidayLexiconView
            events={holidayEvents}
            loading={holidayLoading}
            error={holidayError}
            onRefresh={() => void loadHolidayEvents()}
            onCreateEvent={submitHolidayEvent}
            onUpdateEvent={updateHolidayConditions}
            onAddTerms={submitHolidayTerms}
            onDeleteTerm={removeHolidayTerm}
            onToggleEvent={toggleHolidayEvent}
            onRefreshTags={refreshHolidayTags}
          />
        ) : (
          <OpportunitiesView
            dataScope={dataScope}
            onChangeScope={changeScope}
            activeView={activeView as "opportunities" | "favorites"}
            currentMonthKeywordCount={currentMonth?.keyword_count ?? null}
            totalLabel={totalLabel}
            totalIsEstimated={totalIsEstimated}
            total={total}
            totalPages={totalPages}
            summary={summary}
            filters={filters}
            setFilters={setFilters}
            updateFilter={updateFilter}
            months={months}
            categories={categories}
            items={items}
            loading={loading}
            error={error}
            isCached={isCached}
            pageJump={pageJump}
            setPageJump={setPageJump}
            onLoadCandidates={loadCandidates}
            onOpenDetail={openDetail}
            onChangeState={changeState}
            onToggleFavorite={toggleFavorite}
            onAddExclusion={addKeywordToExclusion}
          />
        )}
      </main>

      {selected && (
        <DetailDrawer
          selected={selected}
          detail={detail}
          noteDraft={noteDraft}
          onNoteChange={setNoteDraft}
          onToggleFavorite={toggleFavorite}
          onAddExclusion={addKeywordToExclusion}
          onSaveNote={saveNote}
          onClose={() => setSelected(null)}
        />
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
