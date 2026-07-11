"use client";

import { useCallback, useEffect, useState } from "react";

export function useFormDraft<T extends Record<string, unknown>>(storageKey: string, initialValue: T) {
  const [draft, setDraft] = useState<T>(initialValue);
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(storageKey);
      if (saved) setDraft({ ...initialValue, ...JSON.parse(saved) } as T);
    } catch {
      window.localStorage.removeItem(storageKey);
    } finally {
      setRestored(true);
    }
  }, [storageKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!restored) return;
    window.localStorage.setItem(storageKey, JSON.stringify(draft));
  }, [draft, restored, storageKey]);

  const clearDraft = useCallback(() => {
    window.localStorage.removeItem(storageKey);
    setDraft(initialValue);
  }, [initialValue, storageKey]);

  return { draft, setDraft, clearDraft, restored };
}
