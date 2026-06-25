import type {
  CandidateDetail,
  CandidateFilters,
  CandidateListResponse,
  CategoryItem,
  ExclusionRule,
  KeywordCompareFilters,
  KeywordCompareResponse,
  LoginResponse,
  MonthItem,
  User,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8001/api";
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

/** Build a cache key from filters, ignoring pagination so page changes don't miss. */
function filtersCacheKey(params: URLSearchParams): string {
  const stable = new URLSearchParams(params);
  stable.delete("page");
  stable.delete("page_size");
  return stable.toString();
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

export function buildExportUrl(filters: CandidateFilters, maxRows = 5000): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (key !== "page" && key !== "page_size") appendParam(params, key, value);
  });
  params.set("max_rows", String(maxRows));
  return `${API_BASE_URL}/exports/product-selection?${params.toString()}`;
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
