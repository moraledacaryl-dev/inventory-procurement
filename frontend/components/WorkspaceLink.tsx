import Link from "next/link";

const paths: Record<string, string> = {
  "/items": "m3 7 9-4 9 4-9 5-9-5Zm0 0v10l9 4 9-4V7M12 12v9",
  "/stock": "m3 7 9-4 9 4-9 4-9-4Zm0 5 9 4 9-4M3 17l9 4 9-4",
  "/counts": "M9 4H5v17h14V4h-4M9 2h6v4H9V2Zm0 9 2 2 4-4M9 17h6",
  "/purchasing": "M3 4h2l3 12h11l2-9H6M9 20h.01M18 20h.01",
  "/receiving": "M3 6h11v11H3V6Zm11 4h4l3 3v4h-7M7 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm11 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  "/production": "M3 21V9l6 3V9l6 3V4h6v17H3Zm4-4h2m5 0h3",
  "/fnb/menu": "M5 3h14v18H5V3Zm4 5h6m-6 4h6m-6 4h3",
  "/fnb/staff-meals": "M4 3v7a3 3 0 0 0 6 0V3M7 3v18M18 3v18m0-18c-4 3-4 9 0 10",
  "/inventory-operations": "M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4",
  "/integrations/pos": "M3 4h18v13H3V4Zm5 17h8m-4-4v4M7 8h3m4 0h3",
};

export function WorkspaceLink({href, label, description}: {href:string; label:string; description:string}) {
  return <Link className="card workspace-launch" href={href}>
    <span className="workspace-launch-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={paths[href] || paths["/items"]}/></svg></span>
    <span className="workspace-launch-arrow" aria-hidden="true">↗</span>
    <h2>{label}</h2><p>{description}</p>
  </Link>;
}
