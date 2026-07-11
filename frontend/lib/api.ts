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

function safeReturnPath() {
  if (typeof window === "undefined") return "/dashboard";
  const path = `${window.location.pathname}${window.location.search}`;
  return path.startsWith("/") && !path.startsWith("//") ? path : "/dashboard";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  headers.set("X-Requested-With", "HiddenOasisInventory");

  const response = await fetch(`${API}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    credentials: "include",
  });

  if (response.status === 401 && typeof window !== "undefined" && window.location.pathname !== "/login") {
    const next = encodeURIComponent(safeReturnPath());
    window.location.assign(`/login?expired=1&next=${next}`);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(body.detail || `Request failed (${response.status})`, response.status, body);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function logout() {
  await api<void>("/auth/logout", { method: "POST" });
  if (typeof window !== "undefined") window.location.assign("/login?signed_out=1");
}
