import { BarChart3, Check } from "lucide-react";
import type { FormEvent } from "react";

interface LoginViewProps {
  loginAccount: string;
  setLoginAccount: (value: string) => void;
  loginPassword: string;
  setLoginPassword: (value: string) => void;
  loginError: string;
  onLogin: (event: FormEvent) => void;
}

export function LoginView({
  loginAccount,
  setLoginAccount,
  loginPassword,
  setLoginPassword,
  loginError,
  onLogin,
}: LoginViewProps) {
  return (
    <main className="login-shell">
      <section className="login-panel apple-panel animate-in">
        <div className="login-mark">
          <BarChart3 size={24} />
        </div>
        <h1>关键词选品工作台</h1>
        <p>登录后进入选品机会池，筛选、标记并推进关键词机会。</p>
        <form onSubmit={onLogin} className="login-form">
          <label>
            <span>账号</span>
            <input value={loginAccount} onChange={(event) => setLoginAccount(event.target.value)} />
          </label>
          <label>
            <span>密码</span>
            <input
              type="password"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
            />
          </label>
          {loginError && <div className="form-error">{loginError}</div>}
          <button className="button primary" type="submit">
            <Check size={16} />
            登录
          </button>
        </form>
      </section>
    </main>
  );
}
