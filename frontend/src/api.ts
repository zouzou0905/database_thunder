import type {
  CandidateDetail,
  CandidateFilters,
  CandidateListResponse,
  CategoryItem,
  ClipboardItem,
  ExclusionRule,
  HolidayEvent,
  KeywordCompareFilters,
  KeywordCompareResponse,
  LoginResponse,
  MonthItem,
  User,
} from "./types";

const defaultApiHost = window.location.hostname || "127.0.0.1";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? `${window.location.protocol}//${defaultApiHost}:8001/api`;
const CANDIDATE_CACHE_TTL_MS = 5 * 60 * 1000;
const COMPARE_CACHE_TTL_MS = 2 * 60 * 1000;
const CATEGORY_CACHE_TTL_MS = 10 * 60 * 1000;

interface CacheEntry<T> {
  expiresAt: number;
  data: T;
}

const candidateCache = new Map<string, CacheEntry<CandidateListResponse>>();
const compareCache = new Map<string, CacheEntry<KeywordCompareResponse>>();
const categoryCache = new Map<string, CacheEntry<{ items: CategoryItem[] }>>();

/** Build a cache key from filters. Page is included so each page caches independently. */
function filtersCacheKey(params: URLSearchParams): string {
  return params.toString();
}

export function clearCandidateCache(): void {
  candidateCache.clear();
}

/** Invalidate only entries that match a predicate (used for targeted cache eviction). */
function invalidateCandidateCacheByKeyword(keywordId: number): void {
  // Simple approach: clear the whole cache on keyword mutation.
  // The cache TTL is short enough (5 min) that this is acceptable for 10 users.
  candidateCache.clear();
}

function getToken(): string | null {
  return localStorage.getItem("keyword_api_token");
}

export function saveSession(token: string, user: User): void {
  clearCandidateCache();
  localStorage.setItem("keyword_api_token", token);
  localStorage.setItem("keyword_user", JSON.stringify(user));
}

export function readUser(): User | null {
  const raw = localStorage.getItem("keyword_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  clearCandidateCache();
  compareCache.clear();
  categoryCache.clear();
  localStorage.removeItem("keyword_api_token");
  localStorage.removeItem("keyword_user");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

function appendParam(params: URLSearchParams, key: string, value: string | number | boolean | null | undefined): void {
  if (value === "" || value === null || value === undefined) return;
  params.set(key, String(value));
}

export async function login(account: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ account, password }),
  });
}

export async function getMe(): Promise<{ user: User }> {
  return request<{ user: User }>("/auth/me");
}

export async function getMonths(): Promise<{ items: MonthItem[] }> {
  return request<{ items: MonthItem[] }>("/meta/months");
}

export async function getCategories(analysisMonth: string, marketplace: string): Promise<{ items: CategoryItem[] }> {
  const params = new URLSearchParams();
  appendParam(params, "analysis_month", analysisMonth);
  appendParam(params, "marketplace", marketplace);
  const cacheKey = params.toString();
  const cached = categoryCache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.data;
  }
  const data = await request<{ items: CategoryItem[] }>(`/meta/categories?${cacheKey}`);
  categoryCache.set(cacheKey, {
    expiresAt: Date.now() + CATEGORY_CACHE_TTL_MS,
    data,
  });
  return data;
}

export async function getCandidates(filters: CandidateFilters): Promise<CandidateListResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => appendParam(params, key, value));
  const cacheKey = filtersCacheKey(params);
  const cached = candidateCache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.data;
  }
  const data = await request<CandidateListResponse>(`/product-selection/candidates?${params.toString()}`);
  candidateCache.set(cacheKey, {
    expiresAt: Date.now() + CANDIDATE_CACHE_TTL_MS,
    data,
  });
  return data;
}

export async function getCandidateDetail(keywordId: number, analysisMonth: string, marketplace: string): Promise<CandidateDetail> {
  const params = new URLSearchParams();
  appendParam(params, "analysis_month", analysisMonth);
  appendParam(params, "marketplace", marketplace);
  return request<CandidateDetail>(`/product-selection/candidates/${keywordId}?${params.toString()}`);
}

export async function getKeywordCompare(filters: KeywordCompareFilters): Promise<KeywordCompareResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => appendParam(params, key, value));
  const cacheKey = filtersCacheKey(params);
  const cached = compareCache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.data;
  }
  const data = await request<KeywordCompareResponse>(`/keyword-compare/keywords?${params.toString()}`);
  compareCache.set(cacheKey, {
    expiresAt: Date.now() + COMPARE_CACHE_TTL_MS,
    data,
  });
  return data;
}

export async function updateCandidateState(
  keywordId: number,
  payload: {
    analysis_month: string;
    marketplace: string;
    status?: string;
    priority?: string;
    is_favorite?: boolean;
    notes?: string;
  },
): Promise<unknown> {
  const result = await request(`/product-selection/candidates/${keywordId}/state`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  invalidateCandidateCacheByKeyword(keywordId);
  compareCache.clear();
  return result;
}

export async function createCandidateNote(
  keywordId: number,
  payload: { analysis_month: string; marketplace: string; note: string },
): Promise<unknown> {
  const result = await request(`/product-selection/candidates/${keywordId}/notes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  invalidateCandidateCacheByKeyword(keywordId);
  return result;
}

export function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getExclusions(activeOnly = false): Promise<{ items: ExclusionRule[] }> {
  const params = new URLSearchParams();
  appendParam(params, "active_only", activeOnly);
  return request<{ items: ExclusionRule[] }>(`/exclusions?${params.toString()}`);
}

export async function createExclusion(payload: {
  term: string;
  match_type: "contains" | "exact";
  exclusion_type: string;
  reason?: string;
  is_active: boolean;
}): Promise<{ exclusion: ExclusionRule }> {
  const result = await request<{ exclusion: ExclusionRule }>("/exclusions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  clearCandidateCache();
  return result;
}

export async function updateExclusion(
  id: number,
  payload: { reason?: string; is_active?: boolean },
): Promise<{ exclusion: ExclusionRule }> {
  const result = await request<{ exclusion: ExclusionRule }>(`/exclusions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  clearCandidateCache();
  return result;
}

export async function getClipboardItems(): Promise<{ items: ClipboardItem[] }> {
  return request<{ items: ClipboardItem[] }>("/clipboard");
}

export async function createClipboardItem(payload: {
  title: string;
  content: string;
}): Promise<{ item: ClipboardItem }> {
  return request<{ item: ClipboardItem }>("/clipboard", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteClipboardItem(id: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/clipboard/${id}`, {
    method: "DELETE",
  });
}

export async function getHolidayEvents(): Promise<{ items: HolidayEvent[] }> {
  return request<{ items: HolidayEvent[] }>("/holiday-lexicon");
}

export async function createHolidayEvent(payload: {
  code: string;
  name_cn: string;
  name_en: string;
  marketplace: string;
  trend_start_month: number;
  trend_end_month: number;
  min_growth_rate: number;
  terms: string[];
}): Promise<{ items: HolidayEvent[] }> {
  return request<{ items: HolidayEvent[] }>("/holiday-lexicon", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateHolidayEvent(
  id: number,
  payload: Partial<{
    name_cn: string;
    name_en: string;
    marketplace: string;
    trend_start_month: number;
    trend_end_month: number;
    min_growth_rate: number;
    is_active: boolean;
  }>,
): Promise<{ items: HolidayEvent[] }> {
  return request<{ items: HolidayEvent[] }>(`/holiday-lexicon/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function addHolidayTerms(
  eventId: number,
  terms: string[],
): Promise<{ items: HolidayEvent[] }> {
  return request<{ items: HolidayEvent[] }>(`/holiday-lexicon/${eventId}/terms`, {
    method: "POST",
    body: JSON.stringify({ terms, match_type: "auto" }),
  });
}

export async function deleteHolidayTerm(termId: number): Promise<{ items: HolidayEvent[] }> {
  return request<{ items: HolidayEvent[] }>(`/holiday-lexicon/terms/${termId}`, {
    method: "DELETE",
  });
}

// ── Holiday tags ──

export async function refreshHolidayTags(marketplace: string = "UK"): Promise<{ ok: boolean; count: number }> {
  return request<{ ok: boolean; count: number }>(`/holiday-tags/refresh?marketplace=${marketplace}`, {
    method: "POST",
  });
}

// ── Export module ──

export interface ExportFilters {
  source: "candidates" | "compare";
  analysis_month?: string;
  marketplace?: string;
  keyword?: string;
  category?: string;
  trend_label?: string;
  candidate_level?: string;
  is_candidate?: string;
  favorite_only?: string;
  search_volume_min?: string;
  search_volume_max?: string;
  score_min?: string;
  score_max?: string;
  ppc_min?: string;
  ppc_max?: string;
  spr_min?: string;
  spr_max?: string;
  start_month?: string;
  end_month?: string;
  trend_type?: string;
  growth_rate_min?: string;
  growth_rate_max?: string;
  month_count_min?: string;
  month_count_max?: string;
  sort_by?: string;
}

export async function getExportCount(filters: ExportFilters): Promise<{ count: number; total_is_estimated?: boolean; total_label?: string }> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, String(value)); });
  return request<{ count: number }>(`/exports/count?${params.toString()}`);
}

export function buildExportDownloadUrl(filters: ExportFilters, format: "xlsx" | "csv", filename: string, maxRows: number): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, String(value)); });
  params.set("format", format);
  params.set("filename", filename);
  params.set("max_rows", String(maxRows));
  return `${API_BASE_URL}/exports/download?${params.toString()}`;
}

async function downloadBlob(url: string): Promise<Blob> {
  const response = await fetch(url, { headers: authHeaders() });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `导出失败：${response.status}`);
  }
  return response.blob();
}

export async function downloadCandidateExport(
  filters: CandidateFilters,
  filename = "选品候选词",
  maxRows = 5000,
): Promise<Blob> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (key !== "page" && key !== "page_size") appendParam(params, key, value);
  });
  params.set("source", "candidates");
  params.set("format", "xlsx");
  params.set("filename", filename);
  params.set("max_rows", String(maxRows));
  return downloadBlob(`${API_BASE_URL}/exports/download?${params.toString()}`);
}

export async function downloadExportFile(
  filters: ExportFilters,
  format: "xlsx" | "csv",
  filename: string,
  maxRows: number,
): Promise<Blob> {
  return downloadBlob(buildExportDownloadUrl(filters, format, filename, maxRows));
}
