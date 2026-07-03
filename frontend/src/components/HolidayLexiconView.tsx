import { CalendarDays, Plus, RefreshCw, Save, Tag, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { HolidayEvent, HolidayTerm } from "../types";

type DraftEvent = {
  code: string;
  name_cn: string;
  name_en: string;
  marketplace: string;
  trend_start_month: string;
  trend_end_month: string;
  min_growth_rate: string;
  termsText: string;
};

type EventConditionDraft = {
  name_cn: string;
  name_en: string;
  marketplace: string;
  trend_start_month: string;
  trend_end_month: string;
  min_growth_rate: string;
};

interface HolidayLexiconViewProps {
  events: HolidayEvent[];
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onCreateEvent: (payload: {
    code: string;
    name_cn: string;
    name_en: string;
    marketplace: string;
    trend_start_month: number;
    trend_end_month: number;
    min_growth_rate: number;
    terms: string[];
  }) => Promise<void>;
  onUpdateEvent: (event: HolidayEvent, payload: {
    name_cn: string;
    name_en: string;
    marketplace: string;
    trend_start_month: number;
    trend_end_month: number;
    min_growth_rate: number;
  }) => Promise<void>;
  onAddTerms: (event: HolidayEvent, terms: string[]) => Promise<void>;
  onDeleteTerm: (term: HolidayTerm) => Promise<boolean>;
  onToggleEvent: (event: HolidayEvent) => Promise<void>;
  onRefreshTags: (marketplace: string) => Promise<{ ok: boolean; count: number }>;
}

const initialDraft: DraftEvent = {
  code: "",
  name_cn: "",
  name_en: "",
  marketplace: "UK",
  trend_start_month: "8",
  trend_end_month: "10",
  min_growth_rate: "20",
  termsText: "",
};

function parseTerms(value: string): string[] {
  return value
    .split(/[\n,，;；]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function growthLabel(value: number): string {
  return `${Math.round(Number(value) * 100)}%`;
}

function eventToConditionDraft(event: HolidayEvent | null): EventConditionDraft {
  if (!event) {
    return {
      name_cn: "",
      name_en: "",
      marketplace: "UK",
      trend_start_month: "8",
      trend_end_month: "10",
      min_growth_rate: "20",
    };
  }
  return {
    name_cn: event.name_cn,
    name_en: event.name_en || "",
    marketplace: event.marketplace,
    trend_start_month: String(event.trend_start_month),
    trend_end_month: String(event.trend_end_month),
    min_growth_rate: String(Math.round(Number(event.min_growth_rate) * 100)),
  };
}

export function HolidayLexiconView({
  events,
  loading,
  error,
  onRefresh,
  onCreateEvent,
  onUpdateEvent,
  onAddTerms,
  onDeleteTerm,
  onToggleEvent,
  onRefreshTags,
}: HolidayLexiconViewProps) {
  const [draft, setDraft] = useState<DraftEvent>(initialDraft);
  const [activeEventId, setActiveEventId] = useState<number | null>(null);
  const [termDrafts, setTermDrafts] = useState<Record<number, string>>({});
  const [termSearch, setTermSearch] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [conditionDraft, setConditionDraft] = useState<EventConditionDraft>(() => eventToConditionDraft(null));
  const [tagRefreshing, setTagRefreshing] = useState(false);
  const [tagResult, setTagResult] = useState<string | null>(null);
  const [staleCacheWarning, setStaleCacheWarning] = useState(false);
  const [togglingEventId, setTogglingEventId] = useState<number | null>(null);
  const [deletingTermId, setDeletingTermId] = useState<number | null>(null);
  const [savingConditionId, setSavingConditionId] = useState<number | null>(null);

  const activeEvent = useMemo(
    () => events.find((event) => event.id === activeEventId) ?? events[0] ?? null,
    [events, activeEventId],
  );
  const visibleTerms = useMemo(() => {
    if (!activeEvent) return [];
    const keyword = termSearch.trim().toLowerCase();
    if (!keyword) return activeEvent.terms;
    return activeEvent.terms.filter((term) => term.term_normalized.includes(keyword));
  }, [activeEvent, termSearch]);

  useEffect(() => {
    setConditionDraft(eventToConditionDraft(activeEvent));
  }, [activeEvent]);

  async function submitEvent(event: React.FormEvent) {
    event.preventDefault();
    const terms = parseTerms(draft.termsText);
    setSubmitting(true);
    try {
      await onCreateEvent({
        code: draft.code,
        name_cn: draft.name_cn,
        name_en: draft.name_en,
        marketplace: draft.marketplace,
        trend_start_month: Number(draft.trend_start_month),
        trend_end_month: Number(draft.trend_end_month),
        min_growth_rate: Number(draft.min_growth_rate) / 100,
        terms,
      });
      setDraft(initialDraft);
      setStaleCacheWarning(true);
    } finally {
      setSubmitting(false);
    }
  }

  async function submitTerms(event: HolidayEvent) {
    const terms = parseTerms(termDrafts[event.id] ?? "");
    if (!terms.length) return;
    setSubmitting(true);
    try {
      await onAddTerms(event, terms);
      setTermDrafts((prev) => ({ ...prev, [event.id]: "" }));
      setStaleCacheWarning(true);
    } finally {
      setSubmitting(false);
    }
  }

  async function submitCondition(event: React.FormEvent) {
    event.preventDefault();
    if (!activeEvent) return;
    setSavingConditionId(activeEvent.id);
    try {
      await onUpdateEvent(activeEvent, {
        name_cn: conditionDraft.name_cn.trim(),
        name_en: conditionDraft.name_en.trim(),
        marketplace: conditionDraft.marketplace.trim() || "UK",
        trend_start_month: Number(conditionDraft.trend_start_month),
        trend_end_month: Number(conditionDraft.trend_end_month),
        min_growth_rate: Number(conditionDraft.min_growth_rate) / 100,
      });
      setStaleCacheWarning(true);
    } finally {
      setSavingConditionId(null);
    }
  }

  async function handleRefreshTags() {
    setTagRefreshing(true);
    setTagResult(null);
    try {
      const marketplace = activeEvent?.marketplace || "UK";
      const result = await onRefreshTags(marketplace);
      setTagResult(`已重新计算 ${result.count.toLocaleString()} 条节日标签`);
      setStaleCacheWarning(false);
    } catch {
      setTagResult("计算失败，请重试");
    } finally {
      setTagRefreshing(false);
    }
  }

  return (
    <section className="holiday-layout">
      <div className="apple-panel holiday-create-panel">
        <div className="filter-title">
          <div>
            <h2>
              <CalendarDays size={17} />
              节日词库
            </h2>
            <p>把一组关键词设定为某个节日，并配置对应的趋势验证窗口。</p>
          </div>
          <button className="button secondary" disabled={loading} onClick={onRefresh}>
            <RefreshCw size={15} />
            刷新词库
          </button>
          <button className="button primary" disabled={tagRefreshing} onClick={handleRefreshTags}>
            <Tag size={15} />
            {tagRefreshing ? "计算中..." : "重新计算标签"}
          </button>
        </div>
        {error && <div className="alert">{error}</div>}
        {staleCacheWarning && (
          <div className="alert warning">
            词库已变更，请点击「重新计算标签」更新横向对比清单中的节日标签。
          </div>
        )}
        {tagResult && (
          <div className="alert" style={{ color: "var(--success)", background: "#effaf2", borderColor: "#ccebd5" }}>
            {tagResult}
          </div>
        )}
        <form className="holiday-form-grid" onSubmit={submitEvent}>
          <label>
            节日编码
            <input
              value={draft.code}
              placeholder="halloween"
              onChange={(event) => setDraft((prev) => ({ ...prev, code: event.target.value }))}
              required
            />
          </label>
          <label>
            中文名称
            <input
              value={draft.name_cn}
              placeholder="万圣节"
              onChange={(event) => setDraft((prev) => ({ ...prev, name_cn: event.target.value }))}
              required
            />
          </label>
          <label>
            英文名称
            <input
              value={draft.name_en}
              placeholder="Halloween"
              onChange={(event) => setDraft((prev) => ({ ...prev, name_en: event.target.value }))}
            />
          </label>
          <label>
            市场
            <input
              value={draft.marketplace}
              onChange={(event) => setDraft((prev) => ({ ...prev, marketplace: event.target.value }))}
            />
          </label>
          <label>
            起始月份
            <input
              type="number"
              min={1}
              max={12}
              value={draft.trend_start_month}
              onChange={(event) => setDraft((prev) => ({ ...prev, trend_start_month: event.target.value }))}
            />
          </label>
          <label>
            结束月份
            <input
              type="number"
              min={1}
              max={12}
              value={draft.trend_end_month}
              onChange={(event) => setDraft((prev) => ({ ...prev, trend_end_month: event.target.value }))}
            />
          </label>
          <label>
            最小增长率 %
            <input
              type="number"
              min={0}
              value={draft.min_growth_rate}
              onChange={(event) => setDraft((prev) => ({ ...prev, min_growth_rate: event.target.value }))}
            />
          </label>
          <label className="holiday-terms-input">
            初始词库
            <textarea
              value={draft.termsText}
              placeholder="一行一个词，也可以用逗号分隔"
              onChange={(event) => setDraft((prev) => ({ ...prev, termsText: event.target.value }))}
            />
          </label>
          <button className="button primary" disabled={submitting || loading}>
            <Plus size={16} />
            新增节日
          </button>
        </form>
      </div>

      <div className="holiday-content">
        <div className="apple-panel holiday-list">
          {events.map((event) => (
            <button
              type="button"
              key={event.id}
              className={activeEvent?.id === event.id ? "holiday-list-item active" : "holiday-list-item"}
              onClick={() => setActiveEventId(event.id)}
            >
              <strong>{event.name_cn}</strong>
              <span>
                {event.marketplace} · {event.trend_start_month}-{event.trend_end_month}月 · {event.active_term_count}词
              </span>
            </button>
          ))}
          {!events.length && <div className="empty-cell">暂无节日词库</div>}
        </div>

        {activeEvent && (
          <div className="apple-panel holiday-detail">
            <div className="holiday-detail-head">
              <div>
                <h2>{activeEvent.name_cn}</h2>
                <p>
                  {activeEvent.code} · {activeEvent.name_en || "-"} · 增长阈值 {growthLabel(activeEvent.min_growth_rate)}
                </p>
              </div>
              <button
                className="button secondary"
                disabled={togglingEventId === activeEvent.id}
                onClick={() => {
                  setTogglingEventId(activeEvent.id);
                  void onToggleEvent(activeEvent).then(() => {
                    setStaleCacheWarning(true);
                    setTogglingEventId(null);
                  }).catch(() => setTogglingEventId(null));
                }}
              >
                {activeEvent.is_active ? "停用" : "启用"}
              </button>
            </div>

            <div className="holiday-rule-summary">
              <div>
                <span>趋势窗口</span>
                <strong>
                  {activeEvent.trend_start_month}月 - {activeEvent.trend_end_month}月
                </strong>
              </div>
              <div>
                <span>市场</span>
                <strong>{activeEvent.marketplace}</strong>
              </div>
              <div>
                <span>状态</span>
                <strong>{activeEvent.is_active ? "启用" : "停用"}</strong>
              </div>
            </div>

            <form className="holiday-condition-form" onSubmit={submitCondition}>
              <label>
                中文名称
                <input
                  value={conditionDraft.name_cn}
                  onChange={(event) => setConditionDraft((prev) => ({ ...prev, name_cn: event.target.value }))}
                  required
                />
              </label>
              <label>
                英文名称
                <input
                  value={conditionDraft.name_en}
                  onChange={(event) => setConditionDraft((prev) => ({ ...prev, name_en: event.target.value }))}
                />
              </label>
              <label>
                市场
                <input
                  value={conditionDraft.marketplace}
                  onChange={(event) => setConditionDraft((prev) => ({ ...prev, marketplace: event.target.value }))}
                />
              </label>
              <label>
                起始月份
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={conditionDraft.trend_start_month}
                  onChange={(event) => setConditionDraft((prev) => ({ ...prev, trend_start_month: event.target.value }))}
                />
              </label>
              <label>
                结束月份
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={conditionDraft.trend_end_month}
                  onChange={(event) => setConditionDraft((prev) => ({ ...prev, trend_end_month: event.target.value }))}
                />
              </label>
              <label>
                增长阈值 %
                <input
                  type="number"
                  min={0}
                  value={conditionDraft.min_growth_rate}
                  onChange={(event) => setConditionDraft((prev) => ({ ...prev, min_growth_rate: event.target.value }))}
                />
              </label>
              <button className="button secondary" disabled={savingConditionId === activeEvent.id}>
                <Save size={15} />
                {savingConditionId === activeEvent.id ? "保存中..." : "保存条件"}
              </button>
            </form>

            <div className="holiday-add-terms">
              <textarea
                value={termDrafts[activeEvent.id] ?? ""}
                placeholder="补充词库，一行一个词"
                onChange={(event) => setTermDrafts((prev) => ({ ...prev, [activeEvent.id]: event.target.value }))}
              />
              <button className="button primary" disabled={submitting} onClick={() => void submitTerms(activeEvent)}>
                <Plus size={16} />
                添加词条
              </button>
            </div>

            <div className="holiday-existing-terms">
              <div className="holiday-existing-head">
                <div>
                  <h3>当前已有词条</h3>
                  <span>
                    共 {activeEvent.terms.length} 个词，当前显示 {visibleTerms.length} 个
                  </span>
                </div>
                <input
                  value={termSearch}
                  placeholder="搜索已有词条"
                  onChange={(event) => setTermSearch(event.target.value)}
                />
              </div>
              <div className="holiday-term-list">
                {visibleTerms.map((term) => (
                  <span className={term.is_active ? "holiday-term" : "holiday-term inactive"} key={term.id}>
                    {term.term}
                    <small>{term.match_type === "phrase" ? "短语" : "单词"}</small>
                    <button
                      title="删除词条"
                      disabled={deletingTermId === term.id}
                      onClick={() => {
                        setDeletingTermId(term.id);
                        void onDeleteTerm(term).then((changed) => {
                          if (changed) setStaleCacheWarning(true);
                          setDeletingTermId(null);
                        }).catch(() => setDeletingTermId(null));
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </span>
                ))}
                {!visibleTerms.length && <div className="empty-cell">没有匹配的词条</div>}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
