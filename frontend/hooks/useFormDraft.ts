"use client";

import { useCallback, useEffect, useState } from "react";
import {trainingDraftKey} from "../lib/training-form-draft";

export function useFormDraft<T extends Record<string, unknown>>(storageKey: string, initialValue: T) {
  const scopedStorageKey = process.env.NEXT_PUBLIC_INVENTORY_TRAINING === "1" && typeof window !== "undefined"
    ? trainingDraftKey(storageKey)
    : storageKey;
  const [draft, setDraft] = useState<T>(initialValue);
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(scopedStorageKey);
      if (saved) setDraft({ ...initialValue, ...JSON.parse(saved) } as T);
    } catch {
      window.localStorage.removeItem(scopedStorageKey);
    } finally {
      setRestored(true);
    }
  }, [scopedStorageKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!restored) return;
    window.localStorage.setItem(scopedStorageKey, JSON.stringify(draft));
  }, [draft, restored, scopedStorageKey]);

  const clearDraft = useCallback(() => {
    window.localStorage.removeItem(scopedStorageKey);
    setDraft(initialValue);
  }, [initialValue, scopedStorageKey]);

  return { draft, setDraft, clearDraft, restored };
}
