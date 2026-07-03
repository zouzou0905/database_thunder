import { Check, Plus, RefreshCw } from "lucide-react";
import type { FormEvent } from "react";
import type { ExclusionRule } from "../types";
import { exclusionTypeLabel, formatNumber } from "../utils";
import { AppleSelect } from "./AppleSelect";
import type { SelectOption } from "./AppleSelect";
import { Field } from "./Field";
import { Tag } from "./Tag";

export interface NewExclusion {
  term: string;
  match_type: "contains" | "exact";
  exclusion_type: string;
  reason: string;
  is_active: boolean;
}

interface ExclusionsViewProps {
  newExclusion: NewExclusion;
  setNewExclusion: React.Dispatch<React.SetStateAction<NewExclusion>>;
  matchTypeOptions: SelectOption[];
  exclusionTypeOptions: SelectOption[];
  activeStateOptions: SelectOption[];
  exclusionError: string;
  exclusions: ExclusionRule[];
  exclusionLoading: boolean;
  onSubmitExclusion: (event: FormEvent) => void;
  onRefresh: () => void;
  onToggleExclusion: (rule: ExclusionRule) => void;
}

export function ExclusionsView({
  newExclusion,
  setNewExclusion,
  matchTypeOptions,
  exclusionTypeOptions,
  activeStateOptions,
  exclusionError,
  exclusions,
  exclusionLoading,
  onSubmitExclusion,
  onRefresh,
  onToggleExclusion,
}: ExclusionsViewProps) {
  return (
    <section className="admin-grid">
      <form className="exclusion-form apple-panel" onSubmit={onSubmitExclusion}>
        <div className="filter-title">
          <Plus size={16} />
          新增禁用词
        </div>
        <div className="filter-grid compact">
          <Field label="禁用词">
            <input
              value={newExclusion.term}
              onChange={(event) =>
                setNewExclusion((prev) => ({ ...prev, term: event.target.value }))
              }
              placeholder="输入品牌词、无关词或风险词"
            />
          </Field>
          <Field label="匹配方式">
            <AppleSelect
              value={newExclusion.match_type}
              options={matchTypeOptions}
              ariaLabel="匹配方式"
              onChange={(value) =>
                setNewExclusion((prev) => ({
                  ...prev,
                  match_type: value as "contains" | "exact",
                }))
              }
            />
          </Field>
          <Field label="规则类型">
            <AppleSelect
              value={newExclusion.exclusion_type}
              options={exclusionTypeOptions}
              ariaLabel="规则类型"
              onChange={(value) =>
                setNewExclusion((prev) => ({ ...prev, exclusion_type: value }))
              }
            />
          </Field>
          <Field label="状态">
            <AppleSelect
              value={newExclusion.is_active ? "active" : "inactive"}
              options={activeStateOptions}
              ariaLabel="状态"
              onChange={(value) =>
                setNewExclusion((prev) => ({
                  ...prev,
                  is_active: value === "active",
                }))
              }
            />
          </Field>
          <Field label="原因">
            <input
              value={newExclusion.reason}
              onChange={(event) =>
                setNewExclusion((prev) => ({ ...prev, reason: event.target.value }))
              }
              placeholder="例如：品牌限制、意图不相关"
            />
          </Field>
        </div>
        <div className="filter-actions">
          <button className="button secondary" type="button" onClick={onRefresh}>
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
                    <td>
                      {rule.match_type === "contains" ? "包含匹配" : "完全匹配"}
                    </td>
                    <td className="muted-cell">{rule.reason || "-"}</td>
                    <td>
                      <Tag tone={rule.is_active ? "success" : "neutral"}>
                        {rule.is_active ? "启用" : "停用"}
                      </Tag>
                    </td>
                    <td className="muted-cell">
                      {new Date(rule.updated_at).toLocaleString("zh-CN")}
                    </td>
                    <td>
                      <button
                        className="button secondary"
                        onClick={() => onToggleExclusion(rule)}
                      >
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
  );
}
