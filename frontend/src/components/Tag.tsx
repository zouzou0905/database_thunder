import type { ReactNode } from "react";

export function Tag({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "success" | "neutral" | "danger" | "warning" | "info";
}) {
  return <span className={`tag ${tone}`}>{children}</span>;
}
