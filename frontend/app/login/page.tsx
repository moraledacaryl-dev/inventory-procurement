"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { API } from "../../lib/api";

type LoginResponse = {
  user: { id: string; email: string; full_name: string; role: string };
};

function safeNextPath(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/login")) return "/dashboard";
  return value;
}

export default function Login() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [notice, setNotice] = useState<"expired" | "signed_out" | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("expired") === "1") setNotice("expired");
    else if (params.get("signed_out") === "1") setNotice("signed_out");
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-With": "HiddenOasisInventory" },
        credentials: "include",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      const body = await response.json().catch(() => ({})) as Partial<LoginResponse> & { detail?: string };
      if (!response.ok) {
        setError(body.detail || "Unable to sign in");
        return;
      }
      const params = new URLSearchParams(window.location.search);
      router.replace(safeNextPath(params.get("next")));
      router.refresh();
    } catch {
      setError("The system could not be reached. Check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return <main className="login">
    <section className="login-visual" aria-label="Application overview">
      <div className="login-brand"><div className="brand-mark">HO</div><div><div className="brand-name">Hidden Oasis</div><div className="brand-subtitle">Operations Platform</div></div></div>
      <div className="login-copy">
        <div className="eyebrow" style={{color:"#a9cbbd"}}>Inventory & procurement</div>
        <h1>One operational view from supplier to sale.</h1>
        <p>Control stock, purchasing, receiving, recipes, production, and connected accounting activity with a complete audit trail.</p>
        <div className="login-points"><div className="login-point"><span>✓</span><span>Immutable stock and costing records</span></div><div className="login-point"><span>✓</span><span>Controlled approvals and receiving</span></div><div className="login-point"><span>✓</span><span>Recipe, production, POS, and accounting flows</span></div></div>
      </div>
      <div className="brand-subtitle">Authorized Hidden Oasis personnel only</div>
    </section>
    <section className="login-panel">
      <div className="login-card">
        <div className="eyebrow">Secure access</div>
        <h2>Welcome back</h2>
        <p>Sign in with your assigned work account.</p>
        {notice === "expired" ? <FeedbackBanner tone="warning" title="Session expired" message="Sign in again to return to the page you were using." /> : null}
        {notice === "signed_out" ? <FeedbackBanner tone="success" title="Signed out" message="Your session has been closed on this device." /> : null}
        <form onSubmit={submit}>
          <label className="field">Email address<input autoComplete="email" type="email" name="email" placeholder="name@hiddenoasis.com" required /></label>
          <label className="field">Password
            <span className="password-field">
              <input autoComplete="current-password" type={showPassword ? "text" : "password"} name="password" placeholder="Enter your password" required />
              <button type="button" className="password-toggle" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button>
            </span>
          </label>
          <button className="primary" disabled={submitting}>{submitting ? "Signing in…" : "Sign in"}</button>
        </form>
        {error ? <div className="notice" role="alert">{error}</div> : null}
      </div>
    </section>
  </main>;
}
