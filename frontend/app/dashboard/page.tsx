import Link from "next/link";
import { AppShell } from "../../components/AppShell";

const modules = [
  { href: "/items", code: "IT", title: "Item Catalogue", text: "Maintain SKUs, units, barcodes, conversions, and item controls." },
  { href: "/stock", code: "ST", title: "Stock Control", text: "Post receipts, issues, transfers, adjustments, and review balances." },
  { href: "/purchasing", code: "PO", title: "Purchasing", text: "Manage requisitions, quotations, approvals, and purchase orders." },
  { href: "/receiving", code: "GR", title: "Receiving", text: "Inspect supplier deliveries and record accepted or rejected stock." },
  { href: "/production", code: "PR", title: "Recipes & Production", text: "Cost recipes, plan batches, and consume ingredients accurately." },
  { href: "/reports", code: "RP", title: "Reports & Controls", text: "Review valuation, activity, supplier performance, and exceptions." },
];

export default function Dashboard() {
  return <AppShell title="Dashboard" description="Your starting point for daily inventory, purchasing, and production work.">
    <div className="dashboard-hero">
      <section className="hero-panel">
        <div className="eyebrow" style={{color:"#b9d7cb"}}>Hidden Oasis operations</div>
        <h2>Keep purchasing, inventory, and production moving from one workspace.</h2>
        <p>Use the action queues for daily work, then review reports and controls before closing the day.</p>
        <div className="hero-actions"><Link href="/inventory-operations">Open inventory operations</Link><Link className="secondary-link" href="/purchasing">Review purchasing</Link></div>
      </section>
      <aside className="quick-panel" aria-label="Quick actions">
        <Link className="quick-link" href="/receiving"><div><strong>Receive a delivery</strong><br/><span>Post accepted and rejected quantities</span></div><span className="module-arrow">→</span></Link>
        <Link className="quick-link" href="/counts"><div><strong>Start a stock count</strong><br/><span>Run blind counts and variance approval</span></div><span className="module-arrow">→</span></Link>
        <Link className="quick-link" href="/rollout"><div><strong>Check system health</strong><br/><span>Review feedback, incidents, and rollout gates</span></div><span className="module-arrow">→</span></Link>
      </aside>
    </div>

    <div className="section-title"><div><h2>Operations</h2><p>Core workspaces organized by task.</p></div></div>
    <div className="module-grid">
      {modules.map(module => <Link className="module-card" href={module.href} key={module.href}>
        <div className="module-card-top"><span className="module-icon">{module.code}</span><span className="module-arrow">→</span></div>
        <div><h3>{module.title}</h3><p>{module.text}</p></div>
      </Link>)}
    </div>
  </AppShell>;
}
