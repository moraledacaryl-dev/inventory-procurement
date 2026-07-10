import { ReactNode } from "react";

export function DataTable({ columns, rows, emptyTitle = "No records yet", emptyMessage = "Records will appear here once activity begins." }: { columns: string[]; rows: ReactNode[][]; emptyTitle?: string; emptyMessage?: string }) {
  return <div className="data-table-shell">
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map(column => <th scope="col" key={column}>{column}</th>)}</tr></thead>
        <tbody>{rows.length ? rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((value, cellIndex) => <td key={cellIndex}>{value}</td>)}</tr>) : <tr><td className="empty-cell" colSpan={columns.length}><div className="empty-state"><div className="empty-icon" aria-hidden="true">—</div><strong>{emptyTitle}</strong><span>{emptyMessage}</span></div></td></tr>}</tbody>
      </table>
    </div>
    {rows.length > 0 && <div className="table-footer"><span>{rows.length} {rows.length === 1 ? "record" : "records"}</span></div>}
  </div>;
}
