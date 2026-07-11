"use client";

import { useEffect } from "react";

export function useUnsavedChanges(isDirty: boolean, message = "You have unsaved changes. Leave this page anyway?") {
  useEffect(() => {
    if (!isDirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [isDirty, message]);
}
