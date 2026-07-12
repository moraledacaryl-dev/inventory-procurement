"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "../lib/api";

type Workspace = { id: string; code: string; name: string; behavior_key?: string | null; is_active: boolean };

const STORAGE_KEY = "hidden-oasis:inventory-workspace";
const BEHAVIOR_KEY = "hidden-oasis:inventory-workspace-behavior";
export const ALL_OPERATIONS = "all";

export function readWorkspaceScope() {
  if (typeof window === "undefined") return ALL_OPERATIONS;
  return window.localStorage.getItem(STORAGE_KEY) || ALL_OPERATIONS;
}

export function readWorkspaceBehavior() {
  if (typeof window === "undefined") return ALL_OPERATIONS;
  return window.localStorage.getItem(BEHAVIOR_KEY) || ALL_OPERATIONS;
}

function workspaceRoute(behavior: string) {
  if (behavior === "fnb") return "/fnb";
  if (behavior === "hotel") return "/hotel";
  if (behavior === "assets") return "/assets";
  return "/dashboard";
}

export function WorkspaceSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [value, setValue] = useState(ALL_OPERATIONS);
  const [loading, setLoading] = useState(true);
  const [navigating, startNavigation] = useTransition();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api<Workspace[]>("/classification/dimensions?dimension_type=workspace&active=true");
      setWorkspaces(rows);
      const stored = readWorkspaceScope();
      setValue(stored === ALL_OPERATIONS || rows.some(row => row.id === stored) ? stored : ALL_OPERATIONS);
    } catch {
      setWorkspaces([]);
      setValue(ALL_OPERATIONS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  function change(next: string) {
    const workspace = workspaces.find(row => row.id === next);
    const behavior = workspace?.behavior_key || ALL_OPERATIONS;
    const target = workspaceRoute(behavior);
    setValue(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    window.localStorage.setItem(BEHAVIOR_KEY, behavior);
    if (pathname === target) {
      window.dispatchEvent(new CustomEvent("hidden-oasis:workspace-change", { detail: { id: next, behavior, pending: false } }));
      return;
    }
    window.dispatchEvent(new CustomEvent("hidden-oasis:workspace-change", { detail: { id: next, behavior, pending: true } }));
    startNavigation(() => router.push(target));
  }

  return <label className={`workspace-switcher ${navigating ? "is-navigating" : ""}`}>
    <span>Workspace</span>
    <select aria-label="Current operating workspace" value={value} disabled={loading || navigating} onChange={event => change(event.target.value)}>
      <option value={ALL_OPERATIONS}>All Operations</option>
      {workspaces.map(workspace => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
    </select>
  </label>;
}
