import Link from "next/link";
import { ReactNode } from "react";
import { AppShell } from "../../components/AppShell";

const StrokeIcon = ({ children }: { children: ReactNode }) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>;

const metrics = [
  { label: "Total Products", value: "0", note: "Catalogue records", tone: "blue", icon: <StrokeIcon><path d="m21 8-9 5-9-5"/><path d="m3 8 9-5 9 5v8l-9 5-9-5Z"/><path d="M12 13v8"/></StrokeIcon> },
  { label: "Inventory Value", value: "₱0.00", note: "Current valuation", tone: "green", icon: <StrokeIcon><path d="M4 19V5h16v14Z"/><path d="M8 9h8M8 13h5"/></StrokeIcon> },
  { label: "Pending POs", value: "0", note: "Awaiting action", tone: "amber", icon: <StrokeIcon><circle cx="9" cy="20" r="1"/><circle cx="19" cy="20" r="1"/><path d="M3 4h2l2.5 11h11l2-7H7"/></StrokeIcon> },
  { label: "Low Stock Items", value: "0", note: "Require attention", tone: "violet", icon: <StrokeIcon><path d="M6 3h12v18H6Z"/><path d="M9 8h6M9 12h6M9 16h3"/></StrokeIcon> },
  { label: "Total Suppliers", value: "0", note: "Active suppliers", tone: "cyan", icon: <StrokeIcon><circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-7 7-7s7 3 7 7M16 5c3 0 5 2 5 5M17 14c3 1 5 3 5 7"/></StrokeIcon> },
];

export default function Dashboard() {
  const date = new Intl.DateTimeFormat("en-PH", { weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: "Asia/Manila" }).format(new Date());

  return <AppShell title="Dashboard" description="Monitor inventory, procurement, receiving, and production from one workspace.">
    <div className="dashboard-overview">
      <section className="dashboard-welcome">
        <div><h2>Welcome back, Administrator</h2><p>Here is the current operating picture for Hidden Oasis inventory.</p></div>
        <div className="date-chip"><StrokeIcon><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></StrokeIcon>{date}</div>
      </section>

      <section className="metric-grid" aria-label="Inventory summary">
        {metrics.map(metric => <article className="metric-card" key={metric.label}>
          <div className={`metric-icon ${metric.tone}`}>{metric.icon}</div>
          <div className="metric-copy"><div className="metric-label">{metric.label}</div><div className="metric-value">{metric.value}</div><div className="metric-note">{metric.note}</div></div>
        </article>)}
      </section>

      <section className="dashboard-primary-grid">
        <article className="dashboard-panel">
          <div className="panel-header"><div><h3>Inventory Value Overview</h3><p>Valuation trend will appear as stock transactions are recorded.</p></div><button className="panel-select" type="button">This month ▾</button></div>
          <div className="chart-stage" aria-label="Inventory value chart awaiting data">
            <div className="chart-axis"><span>₱2.0M</span><span>₱1.5M</span><span>₱1.0M</span><span>₱500K</span><span>₱0</span></div>
            <div className="chart-gridlines"><span/><span/><span/><span/></div>
            <svg className="chart-svg" viewBox="0 0 700 210" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="dashboardArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2f6fed" stopOpacity=".18"/><stop offset="1" stopColor="#2f6fed" stopOpacity="0"/></linearGradient></defs><path d="M0 190 L700 190 L700 210 L0 210 Z" fill="url(#dashboardArea)"/><path d="M0 190 L700 190" fill="none" stroke="#9ab6ec" strokeWidth="2" strokeDasharray="5 5"/></svg>
            <div className="chart-empty-note"><strong>No valuation history yet</strong><span>Receipts, issues, and adjustments will populate this chart.</span></div>
            <div className="chart-labels"><span>Week 1</span><span>Week 2</span><span>Week 3</span><span>Week 4</span></div>
          </div>
        </article>

        <article className="dashboard-panel">
          <div className="panel-header"><div><h3>Stock Status</h3><p>Availability across active catalogue items.</p></div><Link className="panel-link" href="/stock">View stock</Link></div>
          <div className="stock-panel-body">
            <div className="donut empty"><div className="donut-copy"><strong>0</strong><span>Total items</span></div></div>
            <div className="legend">
              <div className="legend-row"><span className="legend-dot" style={{background:"#42bd73"}}/><span>In stock</span><strong>0</strong></div>
              <div className="legend-row"><span className="legend-dot" style={{background:"#f7b928"}}/><span>Low stock</span><strong>0</strong></div>
              <div className="legend-row"><span className="legend-dot" style={{background:"#ef5555"}}/><span>Out of stock</span><strong>0</strong></div>
              <div className="legend-row"><span className="legend-dot" style={{background:"#aeb9c5"}}/><span>Inactive</span><strong>0</strong></div>
            </div>
          </div>
        </article>
      </section>

      <section className="dashboard-secondary-grid">
        <article className="dashboard-panel">
          <div className="panel-header"><div><h3>Recent Purchase Orders</h3><p>Latest procurement documents and approval states.</p></div><Link className="panel-link" href="/purchasing">View all</Link></div>
          <table className="compact-table"><thead><tr><th>PO Number</th><th>Supplier</th><th>Status</th><th>Total</th></tr></thead><tbody><tr className="empty-row"><td colSpan={4}>No purchase orders have been created yet.</td></tr></tbody></table>
        </article>

        <article className="dashboard-panel">
          <div className="panel-header"><div><h3>Low Stock Alerts</h3><p>Items below configured reorder levels.</p></div><Link className="panel-link" href="/reports">View all</Link></div>
          <div className="empty-list"><div><strong>No low-stock alerts</strong><span>Alerts will appear after items and reorder thresholds are configured.</span></div></div>
        </article>

        <article className="dashboard-panel">
          <div className="panel-header"><div><h3>Recent Activity</h3><p>Latest inventory and procurement actions.</p></div><Link className="panel-link" href="/reports">View all</Link></div>
          <div className="empty-list"><div><strong>No recent activity</strong><span>Completed transactions and approvals will be listed here.</span></div></div>
        </article>
      </section>

      <section className="quick-actions-row" aria-label="Quick actions">
        <Link className="quick-action-button primary-action" href="/receiving"><StrokeIcon><path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 21h16"/></StrokeIcon>Receive delivery</Link>
        <Link className="quick-action-button" href="/purchasing"><StrokeIcon><path d="M3 4h2l2.5 11h11l2-7H7"/><circle cx="9" cy="20" r="1"/><circle cx="19" cy="20" r="1"/></StrokeIcon>Create purchase order</Link>
        <Link className="quick-action-button" href="/counts"><StrokeIcon><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M9 10h6M9 14h6"/></StrokeIcon>Start stock count</Link>
        <Link className="quick-action-button" href="/items"><StrokeIcon><path d="m21 8-9 5-9-5"/><path d="m3 8 9-5 9 5v8l-9 5-9-5Z"/></StrokeIcon>Add product</Link>
      </section>
    </div>
  </AppShell>;
}
