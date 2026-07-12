"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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

export function WorkspaceSwitcher() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [value, setValue] = useState(ALL_OPERATIONS);
  const [loading, setLoading] = useState(true);

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
    setValue(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    window.localStorage.setItem(BEHAVIOR_KEY, behavior);
    window.dispatchEvent(new CustomEvent("hidden-oasis:workspace-change", { detail: { id: next, behavior } }));
    if (behavior === "fnb") router.push("/fnb");
    else if (behavior === "hotel") router.push("/hotel");
    else if (behavior === "assets") router.push("/assets");
    else router.push("/dashboard");
  }

  return <label className="workspace-switcher">
    <span>Workspace</span>
    <select aria-label="Current operating workspace" value={value} disabled={loading} onChange={event => change(event.target.value)}>
      <option value={ALL_OPERATIONS}>All Operations</option>
      {workspaces.map(workspace => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}
    </select>
  </label>;
}
