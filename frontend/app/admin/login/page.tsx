"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { adminApi } from "@/lib/admin-api";

export default function AdminLoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("platform");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await adminApi.login(username, password);
      router.push("/admin/tenants");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900">
      <form onSubmit={onSubmit} className="w-full max-w-sm rounded-xl bg-white p-8 shadow-lg">
        <h1 className="text-center text-2xl font-bold text-slate-800">运营后台</h1>
        <p className="mt-1 text-center text-xs text-slate-500">平台管理员登录</p>
        <label className="mt-6 block text-sm text-slate-600">用户名</label>
        <input
          className="mb-4 w-full rounded border px-3 py-2"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <label className="block text-sm text-slate-600">密码</label>
        <input
          type="password"
          className="mb-4 w-full rounded border px-3 py-2"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-brand py-2 text-white disabled:opacity-50"
        >
          {loading ? "登录中…" : "登录"}
        </button>
        <p className="mt-4 text-center text-xs text-slate-400">默认 platform / admin123</p>
      </form>
    </div>
  );
}
