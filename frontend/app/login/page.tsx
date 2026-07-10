"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { API } from "../../lib/api";

export default function Login() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${API}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: form.get("email"), password: form.get("password") }) });
      const body = await response.json();
      if (!response.ok) { setError(body.detail || "Unable to sign in"); return; }
      localStorage.setItem("inventory_token", body.access_token);
      router.push("/dashboard");
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
        <form onSubmit={submit}>
          <label className="field">Email address<input autoComplete="email" type="email" name="email" placeholder="name@hiddenoasis.com" required /></label>
          <label className="field">Password<input autoComplete="current-password" type="password" name="password" placeholder="Enter your password" required /></label>
          <button className="primary" disabled={submitting}>{submitting ? "Signing in…" : "Sign in"}</button>
        </form>
        {error && <div className="notice" role="alert">{error}</div>}
      </div>
    </section>
  </main>;
}
