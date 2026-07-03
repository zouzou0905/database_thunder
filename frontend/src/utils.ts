export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat("zh-CN").format(Math.round(value));
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatGrowthPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function formatMonth(value: string | null | undefined): string {
  if (!value) return "-";
  return value.slice(0, 7);
}

const statusOptions = [
  { value: "new", label: "新候选" },
  { value: "watching", label: "观察中" },
  { value: "researching", label: "调研中" },
  { value: "rejected", label: "已放弃" },
  { value: "approved", label: "进入开发" },
  { value: "launched", label: "已上架" },
];

export function statusLabel(value: string | null | undefined): string {
  return statusOptions.find((item) => item.value === value)?.label ?? "新候选";
}

export function exclusionTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    brand: "品牌词",
    irrelevant: "无关词",
    risk: "风险词",
    competitor: "竞品词",
  };
  return labels[value] ?? value;
}

export function minutesAgo(timestamp: number): string {
  const elapsed = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  if (elapsed < 1) return "不到1";
  return String(elapsed);
}
