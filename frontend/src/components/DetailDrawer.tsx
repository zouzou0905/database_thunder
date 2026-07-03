import { MessageSquare, Shield, Star, X } from "lucide-react";
import type { Candidate, CandidateDetail } from "../types";
import { formatNumber, formatPercent } from "../utils";
import { Metric } from "./Metric";

interface DetailDrawerProps {
  selected: Candidate;
  detail: CandidateDetail | null;
  noteDraft: string;
  onNoteChange: (value: string) => void;
  onToggleFavorite: (candidate: Candidate) => void;
  onAddExclusion: (candidate: Candidate) => void;
  onSaveNote: () => void;
  onClose: () => void;
}

export function DetailDrawer({
  selected,
  detail,
  noteDraft,
  onNoteChange,
  onToggleFavorite,
  onAddExclusion,
  onSaveNote,
  onClose,
}: DetailDrawerProps) {
  return (
    <aside className="drawer">
      <div className="drawer-header">
        <div>
          <h2>{selected.keyword}</h2>
          <p>{selected.keyword_translation || "暂无中文释义"}</p>
        </div>
        <button className="icon-button" onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      <div className="detail-grid">
        <Metric label="搜索量" value={formatNumber(selected.search_volume)} compact />
        <Metric label="选品分" value={String(selected.product_selection_score ?? "-")} compact />
        <Metric label="点击份额" value={formatPercent(selected.click_share)} compact />
        <Metric label="转化份额" value={formatPercent(selected.conversion_share)} compact />
      </div>
      <div className="drawer-actions">
        <button className="button secondary" onClick={() => onToggleFavorite(selected)}>
          <Star size={16} fill={selected.user_is_favorite ? "currentColor" : "none"} />
          {selected.user_is_favorite ? "取消收藏" : "收藏关键词"}
        </button>
        <button className="button secondary" onClick={() => onAddExclusion(selected)}>
          <Shield size={16} />
          加入禁用词
        </button>
      </div>
      <section className="drawer-section">
        <h3>多月变化</h3>
        <div className="mini-table">
          {detail?.monthly.map((row) => (
            <div key={row.data_month}>
              <span>{row.data_month.slice(0, 7)}</span>
              <strong>{formatNumber(row.search_volume)}</strong>
              <small>{row.trend_label_cn || "-"}</small>
            </div>
          ))}
        </div>
      </section>
      <section className="drawer-section">
        <h3>
          <MessageSquare size={16} />
          备注
        </h3>
        <textarea
          value={noteDraft}
          onChange={(event) => onNoteChange(event.target.value)}
          placeholder="写下调研判断、风险或动作"
        />
        <button className="button primary" onClick={onSaveNote}>
          保存备注
        </button>
        <div className="note-list">
          {detail?.notes.map((note) => (
            <article key={note.id}>
              <strong>{note.display_name}</strong>
              <p>{note.note}</p>
              <span>{new Date(note.created_at).toLocaleString("zh-CN")}</span>
            </article>
          ))}
        </div>
      </section>
    </aside>
  );
}
