import {
  BarChart3,
  Bookmark,
  CalendarDays,
  ClipboardList,
  Download,
  Filter,
  GitCompareArrows,
  LogOut,
  Shield,
} from "lucide-react";
import type { User } from "../types";

export type ActiveView =
  | "opportunities"
  | "favorites"
  | "compare"
  | "exclusions"
  | "export"
  | "clipboard"
  | "holidayLexicon";

interface SidebarProps {
  user: User;
  activeView: ActiveView;
  onNavigate: (view: ActiveView) => void;
  onLogout: () => void;
}

export function Sidebar({ user, activeView, onNavigate, onLogout }: SidebarProps) {
  const userInitial = (user.account || user.display_name || "?").trim().slice(0, 1).toUpperCase();
  const roleLabel = user.role === "admin" ? "Admin" : user.role;

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">
          <BarChart3 size={20} />
        </div>
        <div>
          <strong>选品工作台</strong>
          <span>Product Selection</span>
        </div>
      </div>
      <nav className="nav-list">
        <button
          className={activeView === "opportunities" ? "nav-item active" : "nav-item"}
          onClick={() => onNavigate("opportunities")}
        >
          <Filter size={17} />
          机会池
        </button>
        <button
          className={activeView === "favorites" ? "nav-item active" : "nav-item"}
          onClick={() => onNavigate("favorites")}
        >
          <Bookmark size={17} />
          我的收藏
        </button>
        <button
          className={activeView === "compare" ? "nav-item active" : "nav-item"}
          onClick={() => onNavigate("compare")}
        >
          <GitCompareArrows size={17} />
          横向对比
        </button>
        <button
          className={activeView === "exclusions" ? "nav-item active" : "nav-item"}
          onClick={() => onNavigate("exclusions")}
        >
          <Shield size={17} />
          禁用词
        </button>
        <button
          className={activeView === "export" ? "nav-item active" : "nav-item"}
          onClick={() => onNavigate("export")}
        >
          <Download size={17} />
          数据导出
        </button>
        <button
          className={activeView === "clipboard" ? "nav-item active" : "nav-item"}
          onClick={() => onNavigate("clipboard")}
        >
          <ClipboardList size={17} />
          共享粘贴板
        </button>
        <button
          className={activeView === "holidayLexicon" ? "nav-item active" : "nav-item"}
          onClick={() => onNavigate("holidayLexicon")}
        >
          <CalendarDays size={17} />
          节日词库
        </button>
      </nav>
      <div className="user-card">
        <div className="user-avatar" aria-hidden="true">
          {userInitial}
        </div>
        <div className="user-meta">
          <span className="user-name">{user.account}</span>
          <small>{roleLabel}</small>
        </div>
        <button className="logout-button" onClick={onLogout} title="退出登录" aria-label="退出登录">
          <LogOut size={15} />
        </button>
      </div>
    </aside>
  );
}
