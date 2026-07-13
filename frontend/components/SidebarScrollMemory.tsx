"use client";

import { usePathname } from "next/navigation";
import { useEffect, useLayoutEffect } from "react";

let sidebarScrollTop = 0;

function restoreSidebarScroll() {
  const sidebar = document.querySelector<HTMLElement>(".sidebar");
  if (sidebar && sidebar.scrollTop !== sidebarScrollTop) sidebar.scrollTop = sidebarScrollTop;
}

export function SidebarScrollMemory() {
  const pathname = usePathname();

  useEffect(() => {
    const rememberScroll = (event: Event) => {
      const target = event.target;
      if (target instanceof HTMLElement && target.classList.contains("sidebar")) {
        sidebarScrollTop = target.scrollTop;
      }
    };

    let currentSidebar = document.querySelector<HTMLElement>(".sidebar");
    const observer = new MutationObserver(() => {
      const sidebar = document.querySelector<HTMLElement>(".sidebar");
      if (sidebar && sidebar !== currentSidebar) {
        currentSidebar = sidebar;
        sidebar.scrollTop = sidebarScrollTop;
      }
    });

    window.addEventListener("scroll", rememberScroll, true);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      window.removeEventListener("scroll", rememberScroll, true);
      observer.disconnect();
    };
  }, []);

  useLayoutEffect(() => {
    restoreSidebarScroll();
    const frame = window.requestAnimationFrame(restoreSidebarScroll);
    return () => window.cancelAnimationFrame(frame);
  }, [pathname]);

  return null;
}
