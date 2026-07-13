"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

function labelScrollableTables() {
  document.querySelectorAll<HTMLElement>(".table-wrap").forEach((region, index) => {
    region.tabIndex = 0;
    if (!region.hasAttribute("role")) region.setAttribute("role", "region");
    if (!region.hasAttribute("aria-label")) {
      const heading = region.closest("section")?.querySelector("h2, h3")?.textContent?.trim();
      region.setAttribute("aria-label", heading ? `${heading} table` : `Scrollable data table ${index + 1}`);
    }
  });
}

export function ScrollableRegionA11y() {
  const pathname = usePathname();

  useEffect(() => {
    labelScrollableTables();
    const observer = new MutationObserver(labelScrollableTables);
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("resize", labelScrollableTables);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", labelScrollableTables);
    };
  }, [pathname]);

  return null;
}
