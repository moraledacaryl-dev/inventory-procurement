"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "../lib/api";

type Workspace = { id: string; code: string; name: string; behavior_key?: string | null; is_active: boolean };

const STORAGE_KEY = "hidden-oasis:inventory-workspace";
const BEHAVIOR_KEY = "hidden-oasis:inventory-workspace-behavior";
export const ALL_OPERATIONS = "all";

let cachedScope: string | null = null;
let cachedBehavior: string | null = null;
let cachedWorkspaces: Workspace[] | null = null;
let workspaceRequest: Promise<Workspace[]> | null = null;

export function readWorkspaceScope() {
  if (cachedScope !== null) return cachedScope;
  if (typeof window === "undefined") return ALL_OPERATIONS;
  cachedScope = window.localStorage.getItem(STORAGE_KEY) || ALL_OPERATIONS;
  return cachedScope;
}

export function readWorkspaceBehavior() {
  if (cachedBehavior !== null) return cachedBehavior;
  if (typeof window === "undefined") return ALL_OPERATIONS;
  cachedBehavior = window.localStorage.getItem(BEHAVIOR_KEY) || ALL_OPERATIONS;
  return cachedBehavior;
}

export function cachedWorkspaceBehavior() {
  return cachedBehavior || ALL_OPERATIONS;
}

function rememberWorkspace(id: string, behavior: string) {
  cachedScope = id;
  cachedBehavior = behavior;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, id);
    window.localStorage.setItem(BEHAVIOR_KEY, behavior);
  }
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
  const [workspaces, setWorkspaces] = useState<Workspace[]>(() => cachedWorkspaces || []);
  const [value, setValue] = useState(() => cachedScope || ALL_OPERATIONS);
  const [loading, setLoading] = useState(cachedWorkspaces === null);
  const [navigating, startNavigation] = useTransition();

  const load = useCallback(async () => {
    if (cachedWorkspaces) {
      setWorkspaces(cachedWorkspaces);
      const stored = readWorkspaceScope();
      setValue(stored === ALL_OPERATIONS || cachedWorkspaces.some(row => row.id === stored) ? stored : ALL_OPERATIONS);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      workspaceRequest ||= api<Workspace[]>("/classification/dimensions?dimension_type=workspace&active=true");
      const rows = await workspaceRequest;
      cachedWorkspaces = rows;
      setWorkspaces(rows);
      const stored = readWorkspaceScope();
      const next = stored === ALL_OPERATIONS || rows.some(row => row.id === stored) ? stored : ALL_OPERATIONS;
      cachedScope = next;
      setValue(next);
    } catch {
      workspaceRequest = null;
      cachedWorkspaces = [];
      rememberWorkspace(ALL_OPERATIONS, ALL_OPERATIONS);
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
    rememberWorkspace(next, behavior);
    setValue(next);
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
