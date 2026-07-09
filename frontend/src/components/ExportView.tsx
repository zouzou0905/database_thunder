import { Download, Search, X } from "lucide-react";
import type { CategoryItem, HolidayEvent, MonthItem } from "../types";
import { formatNumber } from "../utils";
import { AppleSelect } from "./AppleSelect";
import type { SelectOption } from "./AppleSelect";
import { Field } from "./Field";
import { Metric } from "./Metric";

export const EXPORT_BATCH_SIZE = 20000;
const DEFAULT_EXPORT_MAX_ROWS = 20000;

export interface ExportFilters {
  offset?: number;
  analysis_month: string;
  marketplace: string;
  keyword: string;
  category: string;
  trend_label: string;
  candidate_level: string;
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
  start_month: string;
  end_month: string;
  trend_type: string;
  holiday_code: string;
  growth_rate_min: string;
  growth_rate_max: string;
  month_count_min: string;
  month_count_max: string;
  sort_by: string;
}

interface ExportViewProps {
  exportSource: "candidates" | "compare";
  setExportSource: (value: "candidates" | "compare") => void;
  exportFilters: ExportFilters;
  setExportFilters: React.Dispatch<React.SetStateAction<ExportFilters>>;
  months: MonthItem[];
  categories: CategoryItem[];
  holidayEvents: HolidayEvent[];
  trendOptions: SelectOption[];
  candidateLevelOptions: SelectOption[];
  compareTrendOptions: SelectOption[];
  compareSortOptions: SelectOption[];
  exportCount: number | null;
  exportCountEstimated: boolean;
  exportCountLabel: string;
  exportLoading: boolean;
  exportError: string;
  setExportError: (value: string) => void;
  exportFilename: string;
  setExportFilename: (value: string) => void;
  exportFormat: "xlsx" | "csv";
  setExportFormat: (value: "xlsx" | "csv") => void;
  exportMaxRows: string;
  setExportMaxRows: (value: string) => void;
  effectiveExportMaxRows: number;
  exportRowsThisRun: number;
  exportWouldTruncate: boolean;
  exportBatchCount: number;
  exportBatchSize: number;
  onPreviewCount: () => Promise<void>;
  onDownload: () => Promise<void>;
  onClearPreview: () => void;
}

export function ExportView({
  exportSource,
  setExportSource,
  exportFilters,
  setExportFilters,
  months,
  categories,
  holidayEvents,
  trendOptions,
  candidateLevelOptions,
  compareTrendOptions,
  compareSortOptions,
  exportCount,
  exportCountEstimated,
  exportLoading,
  exportError,
  setExportError,
  exportFilename,
  setExportFilename,
  exportFormat,
  setExportFormat,
  exportMaxRows,
  setExportMaxRows,
  effectiveExportMaxRows,
  exportRowsThisRun,
  exportWouldTruncate,
  exportBatchCount,
  exportBatchSize,
  onPreviewCount,
  onDownload,
  onClearPreview,
}: ExportViewProps) {
  const resetCount = () => {}; // count is reset via onClearPreview
  const holidayOptions: SelectOption[] = [
    { value: "", label: "全部节日" },
    { value: "__any__", label: "任一节日标签" },
    ...holidayEvents
      .filter((event) => event.is_active && (!exportFilters.marketplace || event.marketplace === exportFilters.marketplace))
      .sort((a, b) => a.trend_start_month - b.trend_start_month || a.name_cn.localeCompare(b.name_cn))
      .map((event) => ({
        value: event.code,
        label: `${event.name_cn || event.name_en || event.code} (${event.trend_start_month}-${event.trend_end_month}月)`,
      })),
  ];

  return (
    <section className="admin-grid">
      <section className="filter-panel apple-panel">
        <div className="filter-title">
          <Download size={16} />
          导出条件
        </div>
        <div className="filter-grid">
          <Field label="数据来源">
            <AppleSelect
              value={exportSource}
              options={[
                { value: "candidates", label: "选品机会池" },
                { value: "compare", label: "关键词横向对比" },
              ]}
              ariaLabel="数据来源"
              onChange={(value) => {
                setExportSource(value as "candidates" | "compare");
                setExportFilename(value === "compare" ? "关键词横向对比" : "选品候选词");
                onClearPreview();
              }}
            />
          </Field>
          {exportSource === "candidates" ? (
            <>
              <Field label="分析月份">
                <AppleSelect
                  value={exportFilters.analysis_month}
                  options={months.map((item) => ({
                    value: item.data_month.slice(0, 10),
                    label: `${item.data_month.slice(0, 7)} / ${item.marketplace}`,
                  }))}
                  ariaLabel="分析月份"
                  onChange={(value) => {
                    setExportFilters((prev) => ({ ...prev, analysis_month: value }));
                    onClearPreview();
                  }}
                />
              </Field>
              <Field label="趋势">
                <AppleSelect
                  value={exportFilters.trend_label}
                  options={[{ value: "", label: "全部趋势" }, ...trendOptions]}
                  ariaLabel="趋势"
                  onChange={(value) => {
                    setExportFilters((prev) => ({ ...prev, trend_label: value }));
                    onClearPreview();
                  }}
                />
              </Field>
              <Field label="候选等级">
                <AppleSelect
                  value={exportFilters.candidate_level}
                  options={candidateLevelOptions}
                  ariaLabel="候选等级"
                  onChange={(value) => {
                    setExportFilters((prev) => ({ ...prev, candidate_level: value }));
                    onClearPreview();
                  }}
                />
              </Field>
              <Field label="选品分">
                <div className="range-row">
                  <input
                    value={exportFilters.score_min}
                    onChange={(e) => {
                      setExportFilters((prev) => ({ ...prev, score_min: e.target.value }));
                      onClearPreview();
                    }}
                  />
                  <span>-</span>
                  <input
                    value={exportFilters.score_max}
                    onChange={(e) => {
                      setExportFilters((prev) => ({ ...prev, score_max: e.target.value }));
                      onClearPreview();
                    }}
                  />
                </div>
              </Field>
              <Field label="收藏">
                <AppleSelect
                  value={exportFilters.favorite_only}
                  options={[
                    { value: "", label: "全部" },
                    { value: "true", label: "仅收藏" },
                  ]}
                  ariaLabel="收藏过滤"
                  onChange={(value) => {
                    setExportFilters((prev) => ({ ...prev, favorite_only: value }));
                    onClearPreview();
                  }}
                />
              </Field>
            </>
          ) : (
            <>
              <Field label="起始月份">
                <AppleSelect
                  value={exportFilters.start_month}
                  options={months.map((item) => ({
                    value: item.data_month.slice(0, 10),
                    label: `${item.data_month.slice(0, 7)} / ${item.marketplace}`,
                  }))}
                  ariaLabel="起始月份"
                  onChange={(value) => {
                    setExportFilters((prev) => ({ ...prev, start_month: value }));
                    onClearPreview();
                  }}
                />
              </Field>
              <Field label="结束月份">
                <AppleSelect
                  value={exportFilters.end_month}
                  options={months.map((item) => ({
                    value: item.data_month.slice(0, 10),
                    label: `${item.data_month.slice(0, 7)} / ${item.marketplace}`,
                  }))}
                  ariaLabel="结束月份"
                  onChange={(value) => {
                    setExportFilters((prev) => ({ ...prev, end_month: value }));
                    onClearPreview();
                  }}
                />
              </Field>
              <Field label="对比类型">
                <AppleSelect
                  value={exportFilters.trend_type}
                  options={compareTrendOptions}
                  ariaLabel="对比类型"
                  onChange={(value) => {
                    setExportFilters((prev) => ({ ...prev, trend_type: value }));
                    onClearPreview();
                  }}
                />
              </Field>
              <Field label="节日标签">
                <AppleSelect
                  value={exportFilters.holiday_code}
                  options={holidayOptions}
                  ariaLabel="节日标签"
                  onChange={(value) => {
                    setExportFilters((prev) => ({ ...prev, holiday_code: value }));
                    onClearPreview();
                  }}
                />
              </Field>
              <Field label="出现月数">
                <div className="range-row">
                  <input
                    value={exportFilters.month_count_min}
                    onChange={(e) => {
                      setExportFilters((prev) => ({ ...prev, month_count_min: e.target.value }));
                      onClearPreview();
                    }}
                    placeholder="最少"
                  />
                  <span>-</span>
                  <input
                    value={exportFilters.month_count_max}
                    onChange={(e) => {
                      setExportFilters((prev) => ({ ...prev, month_count_max: e.target.value }));
                      onClearPreview();
                    }}
                    placeholder="最多"
                  />
                </div>
              </Field>
              <Field label="增长率%">
                <div className="range-row">
                  <input
                    value={exportFilters.growth_rate_min}
                    onChange={(e) => {
                      setExportFilters((prev) => ({ ...prev, growth_rate_min: e.target.value }));
                      onClearPreview();
                    }}
                  />
                  <span>-</span>
                  <input
                    value={exportFilters.growth_rate_max}
                    onChange={(e) => {
                      setExportFilters((prev) => ({ ...prev, growth_rate_max: e.target.value }));
                      onClearPreview();
                    }}
                  />
                </div>
              </Field>
            </>
          )}
          <Field label="站点">
            <AppleSelect
              value={exportFilters.marketplace}
              options={[
                { value: "UK", label: "UK" },
                { value: "US", label: "US" },
              ]}
              ariaLabel="站点"
              onChange={(value) => {
                setExportFilters((prev) => ({ ...prev, marketplace: value }));
                onClearPreview();
              }}
            />
          </Field>
          <Field label="关键词">
            <div className="input-icon">
              <Search size={15} />
              <input
                value={exportFilters.keyword}
                onChange={(e) => {
                  setExportFilters((prev) => ({ ...prev, keyword: e.target.value }));
                  onClearPreview();
                }}
                placeholder="输入英文或中文"
              />
            </div>
          </Field>
          <Field label="类目">
            <AppleSelect
              value={exportFilters.category}
              options={[
                { value: "", label: "全部类目" },
                ...categories.slice(0, 160).map((item) => ({
                  value: item.category,
                  label: `${item.category} (${formatNumber(item.candidate_count)})`,
                })),
              ]}
              ariaLabel="类目"
              onChange={(value) => {
                setExportFilters((prev) => ({ ...prev, category: value }));
                onClearPreview();
              }}
            />
          </Field>
          <Field label="搜索量">
            <div className="range-row">
              <input
                value={exportFilters.search_volume_min}
                onChange={(e) => {
                  setExportFilters((prev) => ({ ...prev, search_volume_min: e.target.value }));
                  onClearPreview();
                }}
              />
              <span>-</span>
              <input
                value={exportFilters.search_volume_max}
                onChange={(e) => {
                  setExportFilters((prev) => ({ ...prev, search_volume_max: e.target.value }));
                  onClearPreview();
                }}
              />
            </div>
          </Field>
          <Field label="PPC区间">
            <div className="range-row">
              <input
                value={exportFilters.ppc_min}
                onChange={(e) => {
                  setExportFilters((prev) => ({ ...prev, ppc_min: e.target.value }));
                  onClearPreview();
                }}
                placeholder="最低"
              />
              <span>-</span>
              <input
                value={exportFilters.ppc_max}
                onChange={(e) => {
                  setExportFilters((prev) => ({ ...prev, ppc_max: e.target.value }));
                  onClearPreview();
                }}
                placeholder="最高"
              />
            </div>
          </Field>
          <Field label="SPR区间">
            <div className="range-row">
              <input
                value={exportFilters.spr_min}
                onChange={(e) => {
                  setExportFilters((prev) => ({ ...prev, spr_min: e.target.value }));
                  onClearPreview();
                }}
                placeholder="最低"
              />
              <span>-</span>
              <input
                value={exportFilters.spr_max}
                onChange={(e) => {
                  setExportFilters((prev) => ({ ...prev, spr_max: e.target.value }));
                  onClearPreview();
                }}
                placeholder="最高"
              />
            </div>
          </Field>
          <Field label="排序">
            <AppleSelect
              value={exportFilters.sort_by}
              options={
                exportSource === "compare"
                  ? compareSortOptions
                  : [
                      { value: "product_selection_score", label: "按选品分" },
                      { value: "search_volume", label: "按搜索量" },
                    ]
              }
              ariaLabel="排序"
              onChange={(value) => {
                setExportFilters((prev) => ({ ...prev, sort_by: value }));
                onClearPreview();
              }}
            />
          </Field>
        </div>
        <div className="filter-actions">
          <button
            className="button secondary"
            onClick={() => {
              onClearPreview();
              setExportError("");
            }}
          >
            <X size={16} />
            清除预览
          </button>
          <button className="button primary" onClick={onPreviewCount}>
            <Search size={16} />
            预览条数
          </button>
        </div>
        {exportError && <div className="alert">{exportError}</div>}
      </section>

      <section className="export-options-panel apple-panel">
        <div className="filter-title">
          <Download size={16} />
          导出选项
        </div>
        <div className="export-options-grid">
          <Field label="文件名称">
            <input
              value={exportFilename}
              onChange={(e) => setExportFilename(e.target.value)}
              placeholder="输入文件名"
            />
          </Field>
          <Field label="文件格式">
            <AppleSelect
              value={exportFormat}
              options={[
                { value: "xlsx", label: "Excel (.xlsx)" },
                { value: "csv", label: "CSV (.csv)" },
              ]}
              ariaLabel="文件格式"
              onChange={(value) => setExportFormat(value as "xlsx" | "csv")}
            />
          </Field>
          <Field label="导出条数">
            <div className="export-row-limit">
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                value={exportMaxRows}
                onChange={(e) => {
                  setExportMaxRows(e.target.value.replace(/\D/g, ""));
                }}
                onBlur={() => {
                  if (!exportMaxRows) {
                    setExportMaxRows(String(DEFAULT_EXPORT_MAX_ROWS));
                  }
                }}
              />
              <div className="limit-presets" aria-label="导出条数快捷选择">
                {[5000, 20000, 50000].map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={
                      Number(exportMaxRows) === value ? "limit-preset active" : "limit-preset"
                    }
                    onClick={() => setExportMaxRows(String(value))}
                  >
                    {formatNumber(value)}
                  </button>
                ))}
              </div>
            </div>
          </Field>
        </div>
      </section>

      {exportCount !== null && (
        <section className="export-result apple-panel">
          <div className="filter-title">
            <Download size={16} />
            导出结果
          </div>
          <div className="metric-grid" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
            <Metric
              label="总条数"
              value={`${exportCountEstimated ? "约 " : ""}${formatNumber(exportCount)}`}
              compact
            />
            <Metric
              label="数据来源"
              value={exportSource === "candidates" ? "选品机会池" : "关键词横向对比"}
              compact
            />
            <Metric label="预计导出条数" value={formatNumber(exportRowsThisRun)} compact />
            {exportBatchCount > 1 && (
              <Metric label="自动分批" value={`${exportBatchCount} 个文件，每批 ${formatNumber(exportBatchSize)} 条`} compact />
            )}
          </div>
          {exportWouldTruncate && !exportBatchCount && (
            <div className="alert warning">
              总条数 {formatNumber(exportCount)} 条，本次将导出当前排序下的前{" "}
              {formatNumber(exportRowsThisRun)} 条。可调高最大导出条数以导出更多。
            </div>
          )}
          {exportBatchCount > 1 && (
            <div className="alert" style={{ background: "var(--info-bg)", borderColor: "var(--info-border)" }}>
              数据将自动拆分为 {exportBatchCount} 个文件，每文件最多 {formatNumber(exportBatchSize)} 条。
              文件将按排序顺序依次下载，请允许浏览器多次下载。
            </div>
          )}
          {exportLoading && (
            <div className="alert warning">
              正在生成导出文件，请保持当前页面打开。文件准备好后会自动开始下载。
            </div>
          )}
          <div className="filter-actions">
            <button className="button primary" disabled={exportLoading} onClick={onDownload}>
              <Download size={16} />
              {exportLoading
                ? "正在导出..."
                : exportWouldTruncate
                  ? `下载前 ${formatNumber(exportRowsThisRun)} 条`
                  : "下载文件"}
            </button>
          </div>
        </section>
      )}
    </section>
  );
}
