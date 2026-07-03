export function Metric({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: string;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "metric compact" : "metric apple-panel"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
