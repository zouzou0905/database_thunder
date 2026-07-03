import { Check, ClipboardPaste, Copy, RefreshCw, Send, Trash2 } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import type { ClipboardItem, User } from "../types";

interface ClipboardViewProps {
  user: User;
  items: ClipboardItem[];
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onCreate: (payload: { title: string; content: string }) => Promise<void>;
  onDelete: (item: ClipboardItem) => Promise<void>;
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

export function ClipboardView({
  user,
  items,
  loading,
  error,
  onRefresh,
  onCreate,
  onDelete,
}: ClipboardViewProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [notice, setNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!content.trim()) {
      setNotice("请先粘贴或输入内容");
      return;
    }
    setSubmitting(true);
    setNotice("");
    try {
      await onCreate({ title, content });
      setTitle("");
      setContent("");
      setNotice("已放入共享粘贴板");
    } catch {
      // error is surfaced via parent's error prop
    } finally {
      setSubmitting(false);
    }
  }

  async function readLocalClipboard() {
    setNotice("");
    if (!navigator.clipboard?.readText) {
      setNotice("当前浏览器不支持读取剪贴板，请手动粘贴");
      return;
    }
    try {
      const text = await navigator.clipboard.readText();
      setContent(text);
      setNotice(text ? "已读取本机剪贴板" : "本机剪贴板为空");
    } catch {
      setNotice("浏览器拒绝读取剪贴板，请手动粘贴");
    }
  }

  async function handleCopy(item: ClipboardItem) {
    await copyText(item.content);
    setNotice("已复制到本机剪贴板");
  }

  return (
    <section className="clipboard-layout">
      <form className="apple-panel clipboard-compose" onSubmit={submit}>
        <div className="filter-title">
          <ClipboardPaste size={16} />
          共享粘贴板
        </div>
        <div className="clipboard-form-grid">
          <label>
            <span>标题</span>
            <input
              value={title}
              maxLength={200}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="例如：供应商回复、脚本片段、文件内容"
            />
          </label>
          <label>
            <span>内容</span>
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="在电脑或手机上粘贴文本内容，另一台设备刷新后即可复制"
              rows={12}
            />
          </label>
        </div>
        <div className="filter-actions">
          <button className="button secondary" type="button" onClick={readLocalClipboard}>
            <ClipboardPaste size={16} />
            读取本机剪贴板
          </button>
          <button className="button secondary" type="button" onClick={onRefresh}>
            <RefreshCw size={16} />
            刷新
          </button>
          <button className="button primary" type="submit" disabled={submitting}>
            {submitting ? <RefreshCw size={16} /> : <Send size={16} />}
            {submitting ? "正在发送" : "发送到共享板"}
          </button>
        </div>
        {(notice || error) && <div className={error ? "alert" : "success-alert"}>{error || notice}</div>}
      </form>

      <section className="table-shell clipboard-list">
        <div className="table-toolbar">
          <div>
            <strong>最近内容</strong>
            <span>共 {items.length} 条，手机和电脑登录后都可以复制</span>
          </div>
        </div>
        <div className="clipboard-items">
          {loading ? (
            Array.from({ length: 4 }).map((_, index) => (
              <div className="clipboard-item" key={index}>
                <div className="skeleton" />
              </div>
            ))
          ) : items.length === 0 ? (
            <div className="empty-cell">暂无共享内容</div>
          ) : (
            items.map((item) => {
              const canDelete = item.created_by === user.id || user.role === "admin";
              return (
                <article className="clipboard-item" key={item.id}>
                  <div className="clipboard-item-head">
                    <div>
                      <strong>{item.title || "未命名内容"}</strong>
                      <span>
                        {item.created_by_name} · {new Date(item.created_at).toLocaleString("zh-CN")} · {formatBytes(item.content_size)}
                      </span>
                    </div>
                    <div className="row-actions">
                      <button className="icon-button" title="复制" onClick={() => void handleCopy(item)}>
                        <Copy size={16} />
                      </button>
                      {canDelete && (
                        <button className="icon-button" title="删除" onClick={() => void onDelete(item)}>
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  </div>
                  <pre>{item.content}</pre>
                  <button className="button secondary clipboard-copy-button" onClick={() => void handleCopy(item)}>
                    <Check size={16} />
                    复制内容
                  </button>
                </article>
              );
            })
          )}
        </div>
      </section>
    </section>
  );
}
