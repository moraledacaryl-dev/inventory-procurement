"use client";

import { usePathname } from "next/navigation";
import { useEffect, useLayoutEffect } from "react";

let sidebarScrollTop = 0;

export function SidebarScrollMemory() {
  const pathname = usePathname();

  useEffect(() => {
    const rememberScroll = (event: Event) => {
      const target = event.target;
      if (target instanceof HTMLElement && target.classList.contains("sidebar")) {
        sidebarScrollTop = target.scrollTop;
      }
    };

    window.addEventListener("scroll", rememberScroll, true);
    return () => window.removeEventListener("scroll", rememberScroll, true);
  }, []);

  useLayoutEffect(() => {
    const sidebar = document.querySelector<HTMLElement>(".sidebar");
    if (sidebar) sidebar.scrollTop = sidebarScrollTop;
  }, [pathname]);

  return null;
}
