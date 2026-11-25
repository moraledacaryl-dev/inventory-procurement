export const API = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Turn FastAPI validation details into a readable message, never [object Object]. */
export function formatApiError(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    const messages = detail.slice(0, 5).map((error: unknown) => {
      if (typeof error === "string") return error;
      if (!error || typeof error !== "object") return "";
      const record = error as { loc?: unknown; msg?: unknown };
      const label = Array.isArray(record.loc)
        ? record.loc.filter(part => part !== "body").map(String).join(" > ")
        : "";
      const message = typeof record.msg === "string" ? record.msg : "";
      return label && message ? `${label}: ${message}` : message;
    }).filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as {message?: unknown}).message;
    if (typeof message === "string" && message.trim()) return message.trim();
  }
  return fallback;
}

function safeReturnPath() {
  if (typeof window === "undefined") return "/dashboard";
  const path = `${window.location.pathname}${window.location.search}`;
  return path.startsWith("/") && !path.startsWith("//") ? path : "/dashboard";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const training = process.env.NEXT_PUBLIC_INVENTORY_TRAINING === "1";
  if (training && API !== "/api/v1") throw new Error("Training cannot use an external API address.");
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  headers.set("X-Requested-With", "HiddenOasisInventory");
  if (training && typeof window !== "undefined") {
    const attempt = localStorage.getItem("inventory-training-attempt");
    if (attempt) headers.set("X-Training-Attempt", attempt);
  }

  const response = await fetch(`${API}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    credentials: "include",
  });

  if (response.status === 401 && typeof window !== "undefined" && window.location.pathname !== "/login" && !path.startsWith("/training/")) {
    if (training) { window.location.assign("/training"); throw new Error("Return to Training to continue your session."); }
    const next = encodeURIComponent(safeReturnPath());
    window.location.assign(`/login?expired=1&next=${next}`);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(formatApiError(body?.detail, `Request failed (${response.status})`), response.status, body);
  }

  if (training && !path.startsWith("/training/") && response.headers.get("x-inventory-environment") !== "isolated-training") {
    throw new Error("Practice is unavailable: this API did not identify itself as isolated training.");
  }
  if (training && typeof window !== "undefined" && !path.startsWith("/training/")) {
    window.dispatchEvent(new CustomEvent("inventory-training-action", { detail: { path, method: init.method || "GET" } }));
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function logout() {
  const training = process.env.NEXT_PUBLIC_INVENTORY_TRAINING === "1";
  await api<void>("/auth/logout", { method: "POST" });
  if (typeof window !== "undefined") {
    if (training) {
      for (const key of Object.keys(localStorage)) if (key.startsWith("inventory-training")) localStorage.removeItem(key);
    }
    window.location.assign(training ? "/training" : "/login?signed_out=1");
  }
}
