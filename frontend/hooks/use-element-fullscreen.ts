"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** 将 ref 指向的 DOM 置于浏览器全屏（Fullscreen API）。 */
export function useElementFullscreen<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const sync = () => {
      setActive(document.fullscreenElement === ref.current);
    };
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);

  const enter = useCallback(async () => {
    const el = ref.current;
    if (!el?.requestFullscreen) return;
    try {
      await el.requestFullscreen();
    } catch {
      /* 用户取消或浏览器策略拒绝 */
    }
  }, []);

  const exit = useCallback(async () => {
    if (!document.fullscreenElement) return;
    try {
      await document.exitFullscreen();
    } catch {
      /* ignore */
    }
  }, []);

  const toggle = useCallback(async () => {
    if (document.fullscreenElement === ref.current) {
      await exit();
    } else {
      await enter();
    }
  }, [enter, exit]);

  return { ref, active, enter, exit, toggle };
}
