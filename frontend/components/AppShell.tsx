"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { AuthenticatedUserMenu } from "./AuthenticatedUserMenu";
import { GlobalSearch } from "./GlobalSearch";
import { HelpPanel } from "./HelpPanel";
import { NotificationCenter } from "./NotificationCenter";
import { SessionProvider, useSession } from "./SessionContext";
import { SystemHealth } from "./SystemHealth";
import { readWorkspaceBehavior, WorkspaceSwitcher } from "./WorkspaceSwitcher";

type NavItem = { href: string; label: string; icon: IconName; module: string; scopes?: string[] };
type NavGroup = { label: string; items: NavItem[] };
type IconName = "home"|"box"|"map"|"layers"|"factory"|"cart"|"truck"|"clipboard"|"chart"|"plug"|"shield"|"rocket"|"users"|"settings"|"hotel"|"linen";

const groups: NavGroup[] = [
  { label: "Overview", items: [
    { href: "/dashboard", label: "All Operations", icon: "home", module: "dashboard", scopes: ["all","shared","assets"] },
    { href: "/fnb", label: "F&B Overview", icon: "factory", module: "dashboard", scopes: ["fnb"] },
    { href: "/hotel", label: "Hotel Overview", icon: "hotel", module: "dashboard", scopes: ["hotel"] },
  ]},
  { label: "Catalogue & Stock", items: [
    { href: "/items", label: "Items", icon: "box", module: "items" },
    { href: "/locations", label: "Locations", icon: "map", module: "locations" },
    { href: "/stock", label: "Stock Movements", icon: "layers", module: "stock" },
    { href: "/inventory-operations", label: "Adjustments & Waste", icon: "clipboard", module: "inventory-operations" },
    { href: "/counts", label: "Inventory Counts", icon: "clipboard", module: "counts" },
  ]},
  { label: "Hotel Operations", items: [
    { href: "/hotel/property", label: "Property & Linen", icon: "linen", module: "inventory-operations", scopes: ["hotel","all"] },
  ]},
  { label: "Procurement", items: [
    { href: "/suppliers", label: "Suppliers", icon: "users", module: "suppliers" },
    { href: "/purchasing", label: "Purchasing", icon: "cart", module: "purchasing" },
    { href: "/receiving", label: "Receiving", icon: "truck", module: "receiving" },
  ]},
  { label: "F&B Operations", items: [
    { href: "/production", label: "Recipes & Production", icon: "factory", module: "production", scopes: ["fnb","all"] },
    { href: "/integrations/pos", label: "POS Consumption", icon: "plug", module: "integrations", scopes: ["fnb","all"] },
  ]},
  { label: "Reports", items: [{ href: "/reports", label: "Reports", icon: "chart", module: "reports" }] },
  { label: "System", items: [
    { href: "/settings/classification", label: "Operating Structure", icon: "settings", module: "items", scopes: ["all","shared","assets"] },
    { href: "/integrations", label: "Integrations", icon: "plug", module: "integrations", scopes: ["all","shared","assets"] },
    { href: "/readiness", label: "Readiness", icon: "shield", module: "readiness", scopes: ["all","shared","assets"] },
    { href: "/rollout", label: "Rollout", icon: "rocket", module: "rollout", scopes: ["all","shared","assets"] },
  ]},
];

function Icon({ name }: { name: IconName }) {
  const common = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
  const paths: Record<IconName, ReactNode> = {
    home: <><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/></>,
    box: <><path d="m21 8-9 5-9-5"/><path d="m3 8 9-5 9 5v8l-9 5-9-5Z"/><path d="M12 13v8"/></>,
    map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z"/><path d="M9 3v15M15 6v15"/></>,
    layers: <><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/></>,
    factory: <><path d="M3 21V9l6 3V9l6 3V5h6v16Z"/><path d="M7 21v-4h3v4M14 17h3"/></>,
    hotel: <><path d="M4 21V4h16v17"/><path d="M8 8h2M14 8h2M8 12h2M14 12h2M8 16h8M2 21h20"/></>,
    linen: <><path d="M5 5h14v14H5z"/><path d="M8 8h8v8H8z"/><path d="M5 11h3M16 11h3"/></>,
    cart: <><circle cx="9" cy="20" r="1"/><circle cx="19" cy="20" r="1"/><path d="M3 4h2l2.5 11h11l2-7H7"/></>,
    truck: <><path d="M3 6h11v11H3Z"/><path d="M14 10h4l3 3v4h-7Z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></>,
    clipboard: <><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M9 10h6M9 14h6"/></>,
    chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
    plug: <><path d="m8 12 8-8M14 4l6 6M4 14l6 6M10 14l-6 6"/><path d="m12 10 2 2-4 4-2-2Z"/></>,
    shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></>,
    rocket: <><path d="M14 4c3-3 6-2 6-2s1 3-2 6l-6 6-4-4Z"/><path d="m9 15-4 1 3-3M13 19l1-4-3 3M5 19l-1 2 2-1"/></>,
    users: <><circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-7 7-7s7 3 7 7"/><path d="M16 4c3 0 5 2 5 5M17 14c3 1 5 3 5 7"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21h-4v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H3v-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6V3h4v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.1v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
  };
  return <svg {...common}>{paths[name]}</svg>;
}

function AppShellContent({ title, children, description }: { title: string; children: ReactNode; description?: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [scope, setScope] = useState("all");
  const { loading, canAccessModule } = useSession();
  useEffect(() => {
    setScope(readWorkspaceBehavior());
    const listener = (event: Event) => setScope((event as CustomEvent<{behavior:string}>).detail?.behavior || "all");
    window.addEventListener("hidden-oasis:workspace-change", listener);
    return () => window.removeEventListener("hidden-oasis:workspace-change", listener);
  }, []);
  const pageDescription = description || "Hidden Oasis inventory and procurement operations";
  const visibleGroups = useMemo(() => groups.map(group => ({ ...group, items: group.items.filter(item => (!item.scopes || item.scopes.includes(scope)) && (loading || canAccessModule(item.module))) })).filter(group => group.items.length), [scope, loading, canAccessModule]);
  const allItems = groups.flatMap(group => group.items);
  const currentItem = allItems.find(item => pathname === item.href || pathname.startsWith(`${item.href}/`));
  const routeDenied = !loading && currentItem && !canAccessModule(currentItem.module);
  const scopeLabel = scope === "fnb" ? "F&B workspace" : scope === "hotel" ? "Hotel workspace" : scope === "assets" ? "Assets & Property" : "All Operations";

  return <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <div className={`mobile-scrim ${open ? "is-open" : ""}`} onClick={() => setOpen(false)} aria-hidden="true" />
    <aside className={`sidebar ${open ? "is-open" : ""}`} aria-label="Primary navigation">
      <div className="brand-block"><div className="brand-mark" aria-hidden="true">HO</div><div className="brand-copy"><div className="brand-name">Hidden Oasis</div><div className="brand-subtitle">{scopeLabel}</div></div></div>
      <nav className="nav" aria-label="Application modules">{visibleGroups.map(group => <div className="nav-group" key={group.label}><div className="nav-label">{group.label}</div>{group.items.map(item => { const active = pathname === item.href || pathname.startsWith(`${item.href}/`); return <Link className={`nav-link ${active ? "active" : ""}`} aria-current={active ? "page" : undefined} title={collapsed ? item.label : undefined} key={item.href} href={item.href} onClick={() => setOpen(false)}><Icon name={item.icon}/><span>{item.label}</span></Link>; })}</div>)}</nav>
      <div className="sidebar-footer"><SystemHealth /></div>
    </aside>
    <main className="main-area" id="main-content" tabIndex={-1}>
      <header className="app-header"><div className="header-left"><button className="menu-button" type="button" onClick={() => setOpen(true)} aria-label="Open navigation" aria-expanded={open}><span/><span/><span/></button><button className="desktop-menu-button" type="button" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} aria-pressed={collapsed}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg></button><GlobalSearch /></div><div className="header-actions"><WorkspaceSwitcher /><NotificationCenter /><HelpPanel /><AuthenticatedUserMenu /></div></header>
      <div className="page-heading-bar"><div className="page-heading"><div className="page-kicker">{scopeLabel}</div><h1>{title}</h1><p>{pageDescription}</p></div></div>
      <div className="page-content">{routeDenied ? <section className="card access-denied" role="alert"><div className="access-denied__icon" aria-hidden="true">!</div><h2>Access restricted</h2><p>Your current role does not include access to this module.</p><Link className="primary compact" href="/dashboard">Return to dashboard</Link></section> : children}</div>
    </main>
  </div>;
}

export function AppShell(props: { title: string; children: ReactNode; description?: string }) { return <SessionProvider><AppShellContent {...props} /></SessionProvider>; }
