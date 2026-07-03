import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { formatNumber } from "../utils";

export interface SparklineMonth {
  data_month: string;
  search_volume: number | null;
  ppc_bid_mid: number | null;
}

export function Sparkline({
  monthly,
  width,
  height,
}: {
  monthly: SparklineMonth[];
  width: number;
  height: number;
}) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number; below: boolean } | null>(null);
  const wrapperRef = useRef<HTMLSpanElement | null>(null);
  const valid = monthly.filter(
    (m): m is SparklineMonth & { search_volume: number } =>
      m.search_volume !== null && m.search_volume > 0,
  );
  if (valid.length < 2) {
    return <span className="sparkline-empty">-</span>;
  }
  const volumes = valid.map((m) => m.search_volume);
  const min = Math.min(...volumes);
  const max = Math.max(...volumes);
  const range = max - min || 1;
  const pad = 3;
  const h = height - pad * 2;
  const stepX = valid.length > 1 ? (width - 4) / (valid.length - 1) : 0;
  const points = valid
    .map((_m, i) => {
      const x = 2 + i * stepX;
      const y = pad + h - ((volumes[i] - min) / range) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  function handleEnter(i: number, event: React.MouseEvent) {
    setHoverIdx(i);
    const target = event.currentTarget as SVGCircleElement;
    const rect = target.getBoundingClientRect();
    const below = rect.top < 80;
    setTooltipPos({
      x: rect.left + rect.width / 2,
      y: below ? rect.bottom + 4 : window.innerHeight - rect.top + 4,
      below,
    });
  }

  return (
    <span ref={wrapperRef} style={{ display: "inline-block" }}>
      <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} width={width} height={height}>
        <polyline
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
        {valid.map((m, i) => {
          const svgX = 2 + i * stepX;
          const svgY = pad + h - ((volumes[i] - min) / range) * h;
          return (
            <circle
              key={i}
              cx={svgX}
              cy={svgY}
              r={hoverIdx === i ? 4 : 2}
              fill="var(--accent)"
              style={{ cursor: "pointer", transition: "r 120ms" }}
              onMouseEnter={(e) => handleEnter(i, e)}
              onMouseLeave={() => {
                setHoverIdx(null);
                setTooltipPos(null);
              }}
            />
          );
        })}
      </svg>
      {hoverIdx !== null && valid[hoverIdx] && tooltipPos &&
        createPortal(
          <div
            className="sparkline-tooltip"
            style={{
              position: "fixed",
              left: tooltipPos.x,
              [tooltipPos.below ? "top" : "bottom"]: tooltipPos.y,
              transform: "translateX(-50%)",
            }}
          >
            <strong>{valid[hoverIdx].data_month.slice(0, 7)}</strong>
            <span>搜索量 {formatNumber(valid[hoverIdx].search_volume)}</span>
            <span>PPC {valid[hoverIdx].ppc_bid_mid ?? "-"}</span>
          </div>,
          document.body,
        )}
    </span>
  );
}
