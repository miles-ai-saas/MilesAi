"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAdminAuthStore, useAdminHydrated } from "@/lib/admin-auth-store";

const NAV = [
  { href: "/admin/tenants", label: "租户管理" },
  { href: "/admin/billing", label: "计费管理" },
  { href: "/admin/risk", label: "风控管理" },
  { href: "/admin/profile", label: "账号安全" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const hydrated = useAdminHydrated();
  const token = useAdminAuthStore((s) => s.accessToken);

  useEffect(() => {
    if (!hydrated) return;
    if (pathname === "/admin/login") return;
    if (!token) router.replace("/admin/login");
  }, [hydrated, token, pathname, router]);

  if (pathname === "/admin/login") return <>{children}</>;

  if (!hydrated || !token) {
    return <p className="flex min-h-screen items-center justify-center text-slate-500">加载中…</p>;
  }

  return (
    <div className="flex min-h-screen bg-slate-100">
      <aside className="relative flex w-56 flex-col border-r border-slate-200 bg-slate-900 text-white">
        <div className="border-b border-slate-700 px-4 py-5">
          <p className="text-lg font-bold">AiEngine</p>
          <p className="text-xs text-slate-400">运营后台</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded px-3 py-2 text-sm ${
                pathname.startsWith(item.href)
                  ? "bg-brand text-white"
                  : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="border-t border-slate-700 p-4">
          <Link href="/flows" className="text-xs text-slate-400 hover:text-white">
            ← 租户前台
          </Link>
        </div>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <h1 className="text-sm font-semibold text-slate-700">平台运营中心</h1>
          <button
            type="button"
            className="text-sm text-slate-500 hover:text-red-600"
            onClick={() => {
              useAdminAuthStore.getState().logout();
              router.push("/admin/login");
            }}
          >
            退出
          </button>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
