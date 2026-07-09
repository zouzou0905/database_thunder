export type UserRole = "admin" | "manager" | "operator" | "viewer";

export interface User {
  id: number;
  account: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface Candidate {
  keyword_id: number;
  keyword: string;
  keyword_translation: string | null;
  analysis_month: string;
  marketplace: string;
  category: string;
  search_rank: number | null;
  search_volume: number | null;
  months_seen_to_date: number;
  trend_label: string | null;
  trend_label_cn: string | null;
  selection_segment_cn: string | null;
  demand_band_cn: string | null;
  candidate_level_cn: string | null;
  product_selection_score: number | null;
  ppc_bid_mid: number | null;
  spr: number | null;
  click_share: number | null;
  conversion_share: number | null;
  is_product_selection_candidate: boolean;
  exclusion_reason_cn: string | null;
  user_status: string | null;
  user_priority: string | null;
  user_is_favorite: boolean;
  user_notes: string | null;
}

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  total_is_estimated?: boolean;
  total_label?: "estimated" | "lower_bound" | "exact";
  has_more?: boolean;
}

export interface CandidateListResponse {
  items: Candidate[];
  pagination: Pagination;
  cached?: boolean;
}

export interface MonthItem {
  data_month: string;
  marketplace: string;
  keyword_count: number;
}

export interface CategoryItem {
  category: string;
  candidate_count: number;
  level_a_count: number;
  growth_candidate_count: number;
  stable_candidate_count: number;
  avg_candidate_score: number | null;
}

export interface CandidateDetail {
  candidate: Candidate;
  monthly: Array<{
    data_month: string;
    marketplace: string;
    category: string | null;
    search_rank: number | null;
    search_volume: number | null;
    ppc_bid_mid: number | null;
    spr: number | null;
    click_share: number | null;
    conversion_share: number | null;
    trend_label_cn: string | null;
    opportunity_score: number | null;
    conversion_score: number | null;
  }>;
  notes: Array<{
    id: number;
    note: string;
    created_at: string;
    user_id: number;
    display_name: string;
    account: string;
  }>;
}

export interface CandidateFilters {
  page: number;
  page_size: number;
  analysis_month: string;
  marketplace: string;
  keyword: string;
  category: string;
  trend_label: string;
  candidate_level: string;
  selection_segment: string;
  is_candidate: string;
  favorite_only: string;
  search_volume_min: string;
  search_volume_max: string;
  score_min: string;
  score_max: string;
  ppc_min: string;
  ppc_max: string;
  spr_min: string;
  spr_max: string;
  sort_by: string;
  sort_order: "asc" | "desc";
}

export interface KeywordCompareMonthlyItem {
  data_month: string;
  search_rank: number | null;
  search_volume: number | null;
  ppc_bid_mid: number | null;
  spr: number | null;
}

export interface KeywordCompareItem {
  keyword_id: number;
  keyword: string;
  keyword_translation: string | null;
  category: string | null;
  marketplace: string;
  first_month: string;
  last_month: string;
  start_search_volume: number | null;
  end_search_volume: number | null;
  search_volume_change: number | null;
  search_volume_growth_rate: number | null;
  start_rank: number | null;
  end_rank: number | null;
  rank_change: number | null;
  month_count: number;
  total_months: number;
  avg_search_volume: number | null;
  ppc_bid_mid: number | null;
  spr: number | null;
  prev_month_rank: number | null;
  four_months_ago_rank: number | null;
  twelve_months_ago_rank: number | null;
  trend_type: string;
  trend_type_cn: string;
  user_status: string | null;
  user_priority: string | null;
  user_is_favorite: boolean;
  user_notes: string | null;
  monthly: KeywordCompareMonthlyItem[];
  holiday_tags: HolidayTag[] | null;
  holiday_label: string | null;
  mom_change: number | null;
  mom_rate: number | null;
  yoy_change: number | null;
  yoy_rate: number | null;
}

export interface KeywordCompareFilters {
  page: number;
  page_size: number;
  start_month: string;
  end_month: string;
  marketplace: string;
  keyword: string;
  category: string;
  trend_type: string;
  holiday_code: string;
  search_volume_min: string;
  search_volume_max: string;
  growth_rate_min: string;
  growth_rate_max: string;
  month_count_min: string;
  month_count_max: string;
  ppc_min: string;
  ppc_max: string;
  spr_min: string;
  spr_max: string;
  sort_by: string;
  sort_order: "asc" | "desc";
}

export interface KeywordCompareResponse {
  items: KeywordCompareItem[];
  months: Array<{ data_month: string }>;
  pagination: Pagination;
}

export interface ExclusionRule {
  id: number;
  term: string;
  match_type: "contains" | "exact";
  exclusion_type: string;
  reason: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClipboardItem {
  id: number;
  title: string;
  content: string;
  content_size: number;
  created_by: number;
  created_by_name: string;
  created_by_account: string;
  created_at: string;
  updated_at: string;
}

export interface HolidayTag {
  code: string;
  name_cn: string;
  confidence: "confirmed" | "suspected";
  matched_terms: string[];
  match_sources: string[];
  trend_year: number;
  trend_start_month: number;
  trend_end_month: number;
  start_volume: number | null;
  end_volume: number | null;
  growth_rate: number | null;
  is_trend_confirmed: boolean;
}

export interface HolidayTerm {
  id: number;
  event_id: number;
  term: string;
  term_normalized: string;
  match_type: "word" | "phrase";
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface HolidayEvent {
  id: number;
  code: string;
  name_cn: string;
  name_en: string;
  marketplace: string;
  trend_start_month: number;
  trend_end_month: number;
  min_growth_rate: number;
  is_active: boolean;
  active_term_count: number;
  term_count: number;
  terms: HolidayTerm[];
  created_at: string;
  updated_at: string;
}
