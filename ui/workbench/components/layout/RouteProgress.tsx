"use client";

/**
 * 路由切换顶部进度条（workbench 全站壳层挂载，链路 §7）。
 *
 * 触发：内部链接点击、`history.pushState/replaceState`、浏览器前进/后退（popstate）。
 * 收尾：`usePathname()` 变化（新页面已提交）后走到 100% 并淡出。
 * 仅当目标 `pathname` 不同才触发，避免筛选等仅改 query 的操作闪进度条。
 *
 * 体验约束：
 * - 120ms 内完成的导航不显示，避免快切闪烁；
 * - 一旦显示，至少停留 `MIN_VISIBLE`，避免一闪而过；
 * - `MAX_PROGRESS` 后缓慢蠕动，等待真正完成。
 */

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

const SHOW_DELAY = 120;
const MIN_VISIBLE = 300;
const TRICKLE_INTERVAL = 400;
const MAX_PROGRESS = 92;
const FADE_OUT = 220;
const FAILSAFE = 6_000;

/** 去掉尾斜杠后比较，兼容 `trailingSlash: true` */
function normalizePath(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith("/")) return pathname.slice(0, -1);
  return pathname;
}

type BarState = { shown: boolean; progress: number };

const INITIAL_STATE: BarState = { shown: false, progress: 0 };

export function RouteProgress() {
  const pathname = usePathname();
  const [state, setState] = useState<BarState>(INITIAL_STATE);

  const phaseRef = useRef<"idle" | "loading">("idle");
  const shownRef = useRef(false);
  const progressRef = useRef(0);
  const shownAtRef = useRef(0);
  const lastPathRef = useRef<string | null>(null);

  const showTimerRef = useRef<number | null>(null);
  const trickleTimerRef = useRef<number | null>(null);
  const hideTimerRef = useRef<number | null>(null);
  const resetTimerRef = useRef<number | null>(null);
  const failSafeTimerRef = useRef<number | null>(null);

  const setBar = useCallback((shown: boolean, progress: number) => {
    shownRef.current = shown;
    progressRef.current = progress;
    setState({ shown, progress });
  }, []);

  const clearTimer = useCallback((ref: { current: number | null }, interval = false) => {
    if (ref.current === null) return;
    if (interval) window.clearInterval(ref.current);
    else window.clearTimeout(ref.current);
    ref.current = null;
  }, []);

  const finish = useCallback(() => {
    if (phaseRef.current === "idle") return;
    phaseRef.current = "idle";
    clearTimer(showTimerRef);
    clearTimer(trickleTimerRef, true);
    clearTimer(failSafeTimerRef);

    if (!shownRef.current) {
      // 未真正显示（快速切换），无需收尾动画
      setBar(false, 0);
      return;
    }

    setBar(true, 100);
    const elapsed = Date.now() - shownAtRef.current;
    // 至少留 200ms 让宽度动画走到 100%，再整体淡出
    const hold = Math.max(200, MIN_VISIBLE - elapsed);
    hideTimerRef.current = window.setTimeout(() => {
      hideTimerRef.current = null;
      setBar(false, 100);
      resetTimerRef.current = window.setTimeout(() => {
        resetTimerRef.current = null;
        setBar(false, 0);
      }, FADE_OUT);
    }, hold);
  }, [clearTimer, setBar]);

  const start = useCallback(() => {
    if (phaseRef.current === "loading") return;
    phaseRef.current = "loading";

    // 上一次收尾动画尚未结束时，取消它，直接复用当前可见的条
    clearTimer(hideTimerRef);
    clearTimer(resetTimerRef);

    clearTimer(failSafeTimerRef);
    failSafeTimerRef.current = window.setTimeout(finish, FAILSAFE);

    showTimerRef.current = window.setTimeout(() => {
      showTimerRef.current = null;
      if (phaseRef.current !== "loading") return;
      shownAtRef.current = Date.now();
      setBar(true, 8);
      window.requestAnimationFrame(() => {
        if (phaseRef.current === "loading") setBar(true, 28);
      });
      trickleTimerRef.current = window.setInterval(() => {
        if (phaseRef.current !== "loading") return;
        const next = progressRef.current + (MAX_PROGRESS - progressRef.current) * 0.12;
        setBar(true, Math.min(next, MAX_PROGRESS));
      }, TRICKLE_INTERVAL);
    }, SHOW_DELAY);
  }, [clearTimer, finish, setBar]);

  // 导航开始：内部链接点击 / history 变更 / 前进后退
  useEffect(() => {
    const maybeStart = (rawUrl: string | URL | null | undefined) => {
      if (!rawUrl) return;
      let url: URL;
      try {
        url = rawUrl instanceof URL ? rawUrl : new URL(String(rawUrl), window.location.href);
      } catch {
        return;
      }
      if (url.origin !== window.location.origin) return;
      if (normalizePath(url.pathname) === normalizePath(window.location.pathname)) return;
      start();
    };

    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      if (anchor.target && anchor.target !== "_self") return;
      if (anchor.hasAttribute("download")) return;
      const href = anchor.getAttribute("href");
      if (!href || /^(mailto:|tel:|javascript:|#)/i.test(href)) return;
      maybeStart(anchor.href);
    };

    const onPopState = () => {
      const last = lastPathRef.current;
      if (last === null) return;
      if (normalizePath(window.location.pathname) !== normalizePath(last)) start();
    };

    const originalPush = window.history.pushState;
    const originalReplace = window.history.replaceState;

    window.history.pushState = function pushState(this: History, data: unknown, unused: string, url?: string | URL | null) {
      maybeStart(url);
      return originalPush.call(this, data, unused, url);
    };
    window.history.replaceState = function replaceState(this: History, data: unknown, unused: string, url?: string | URL | null) {
      maybeStart(url);
      return originalReplace.call(this, data, unused, url);
    };

    document.addEventListener("click", onClick, true);
    window.addEventListener("popstate", onPopState);
    return () => {
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("popstate", onPopState);
      window.history.pushState = originalPush;
      window.history.replaceState = originalReplace;
    };
  }, [start]);

  // 导航完成：pathname 提交后收尾
  useEffect(() => {
    lastPathRef.current = pathname;
    finish();
  }, [pathname, finish]);

  // 卸载兜底清理
  useEffect(() => {
    const timers = [showTimerRef, trickleTimerRef, hideTimerRef, resetTimerRef, failSafeTimerRef];
    return () => {
      timers.forEach((ref, index) => clearTimer(ref, index === 1));
    };
  }, [clearTimer]);

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-x-0 top-0"
      style={{
        zIndex: 9999,
        height: 2,
        opacity: state.shown ? 1 : 0,
        transition: `opacity ${FADE_OUT}ms ease`,
      }}
    >
      <div
        className="h-full bg-brand"
        style={{
          width: `${state.progress}%`,
          boxShadow: "0 0 8px var(--brand)",
          transition: "width 200ms ease-out",
        }}
      />
    </div>
  );
}
