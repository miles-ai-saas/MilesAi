"use client";

/** 登录入口（鉴权链路 §1）：`api.login` 写 token/user → 跳转工作台。 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { CompanyLogo } from "@/components/brand/company-logo";
import { LoginHero } from "@/components/layout/LoginHero";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.login(username, password);
      router.push("/workbench/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-surface-muted">
      <LoginHero />

      <div className="flex flex-1 flex-col justify-center px-6 py-10 sm:px-12 lg:px-16">
        <div className="mx-auto w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <CompanyLogo variant="full" size="md" className="mb-3" />
            <h1 className="mt-1 text-2xl font-bold text-ink">登录工作台</h1>
          </div>

          <form onSubmit={onSubmit} className="card p-8">
            <h2 className="text-xl font-semibold text-ink">欢迎回来</h2>
            <p className="mt-1 text-sm text-ink-muted">使用租户账号登录 AI 工作台</p>

            <label className="mb-1 mt-6 block text-sm font-medium text-ink">用户名</label>
            <input className="input-field mb-4" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />

            <label className="mb-1 block text-sm font-medium text-ink">密码</label>
            <input
              type="password"
              className="input-field mb-4"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />

            {error && <p className="mb-3 rounded-lg bg-brand-light px-3 py-2 text-sm text-brand-dark">{error}</p>}

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? "登录中…" : "进入工作台"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
