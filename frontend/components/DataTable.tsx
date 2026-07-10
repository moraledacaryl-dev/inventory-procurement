import { ReactNode } from "react";
export function DataTable({columns,rows}:{columns:string[];rows:ReactNode[][]}){return <div className="table-wrap"><table><thead><tr>{columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{rows.length?rows.map((r,i)=><tr key={i}>{r.map((v,j)=><td key={j}>{v}</td>)}</tr>):<tr><td colSpan={columns.length}>No records yet.</td></tr>}</tbody></table></div>}
