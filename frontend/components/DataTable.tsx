"use client";

import { ReactNode, isValidElement, useEffect, useMemo, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "./AsyncState";

export type DataTableDensity = "comfortable" | "compact";

export type DataTableProps = {
  columns: string[];
  rows: ReactNode[][];
  rowIds?: string[];
  emptyTitle?: string;
  emptyMessage?: string;
  emptyAction?: ReactNode;
  loading?: boolean;
  loadingRows?: number;
  error?: string;
  onRetry?: () => void;
  searchable?: boolean;
  searchPlaceholder?: string;
  sortable?: boolean;
  paginated?: boolean;
  pageSize?: number;
  pageSizeOptions?: number[];
  exportFileName?: string;
  selectable?: boolean;
  selectedRowIds?: string[];
  onSelectionChange?: (rowIds: string[]) => void;
  density?: DataTableDensity;
  caption?: string;
};

type SortState = { column: number; direction: "asc" | "desc" } | null;

function nodeText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number" || typeof node === "bigint") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join(" ");
  if (isValidElement<{ children?: ReactNode }>(node)) return nodeText(node.props.children);
  return "";
}

function csvCell(value: string) {
  return `"${value.replace(/"/g, '""')}"`;
}

export function DataTable({
  columns, rows, rowIds, emptyTitle = "No records yet", emptyMessage = "Records will appear here once activity begins.", emptyAction,
  loading = false, loadingRows = 5, error, onRetry, searchable = true, searchPlaceholder = "Search records", sortable = true,
  paginated = true, pageSize = 10, pageSizeOptions = [10, 25, 50], exportFileName, selectable = false, selectedRowIds,
  onSelectionChange, density = "comfortable", caption,
}: DataTableProps) {
  const columnKey = columns.join("\u0000");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortState>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [currentPageSize, setCurrentPageSize] = useState(pageSize);
  const [visibleColumns, setVisibleColumns] = useState(() => columns.map(() => true));
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [internalSelection, setInternalSelection] = useState<string[]>([]);

  useEffect(() => { setVisibleColumns(columns.map(() => true)); setSort(null); }, [columnKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => setCurrentPage(1), [query, currentPageSize, rows.length]);

  const selected = selectedRowIds ?? internalSelection;
  const resolvedRows = useMemo(() => rows.map((cells, index) => ({ id: rowIds?.[index] ?? String(index), cells })), [rowIds, rows]);
  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const result = normalizedQuery ? resolvedRows.filter(row => row.cells.some(cell => nodeText(cell).toLocaleLowerCase().includes(normalizedQuery))) : resolvedRows;
    if (!sort) return result;
    return [...result].sort((left, right) => {
      const comparison = nodeText(left.cells[sort.column]).localeCompare(nodeText(right.cells[sort.column]), "en-PH", { numeric: true, sensitivity: "base" });
      return sort.direction === "asc" ? comparison : -comparison;
    });
  }, [query, resolvedRows, sort]);

  const totalPages = paginated ? Math.max(1, Math.ceil(filteredRows.length / currentPageSize)) : 1;
  const safePage = Math.min(currentPage, totalPages);
  const displayedRows = paginated ? filteredRows.slice((safePage - 1) * currentPageSize, safePage * currentPageSize) : filteredRows;

  function toggleSort(column: number) {
    if (!sortable) return;
    setSort(current => {
      if (!current || current.column !== column) return { column, direction: "asc" };
      if (current.direction === "asc") return { column, direction: "desc" };
      return null;
    });
  }
  function updateSelection(next: string[]) { if (selectedRowIds === undefined) setInternalSelection(next); onSelectionChange?.(next); }
  function toggleRow(id: string) { updateSelection(selected.includes(id) ? selected.filter(value => value !== id) : [...selected, id]); }
  function toggleDisplayedRows() {
    const pageIds = displayedRows.map(row => row.id);
    const allSelected = pageIds.length > 0 && pageIds.every(id => selected.includes(id));
    updateSelection(allSelected ? selected.filter(id => !pageIds.includes(id)) : Array.from(new Set([...selected, ...pageIds])));
  }
  function exportCsv() {
    const visibleIndexes = columns.map((_, index) => index).filter(index => visibleColumns[index]);
    const lines = [visibleIndexes.map(index => csvCell(columns[index])).join(","), ...filteredRows.map(row => visibleIndexes.map(index => csvCell(nodeText(row.cells[index]))).join(","))];
    const blob = new Blob([`\uFEFF${lines.join("\n")}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${exportFileName || "records"}.csv`; anchor.click(); URL.revokeObjectURL(url);
  }

  if (loading) return <LoadingState title="Loading table records" rows={loadingRows} />;
  if (error) return <ErrorState message={error} onRetry={onRetry} />;

  const firstRecord = filteredRows.length ? (safePage - 1) * currentPageSize + 1 : 0;
  const lastRecord = paginated ? Math.min(safePage * currentPageSize, filteredRows.length) : filteredRows.length;
  const selectedOnPage = displayedRows.length > 0 && displayedRows.every(row => selected.includes(row.id));

  return <div className={`data-table-shell data-table-shell--${density}`}>
    {(searchable || exportFileName || columns.length > 1) && <div className="data-table-toolbar"><div className="data-table-toolbar__primary">
      {searchable ? <label className="data-table-search"><span className="sr-only">Search table records</span><span aria-hidden="true">⌕</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder={searchPlaceholder} type="search" /></label> : null}
      {selectable && selected.length ? <span className="data-table-selection-count">{selected.length} selected</span> : null}
    </div><div className="data-table-toolbar__actions"><div className="data-table-columns">
      <button type="button" className="secondary data-table-tool-button" onClick={() => setColumnsOpen(open => !open)} aria-expanded={columnsOpen}>Columns</button>
      {columnsOpen ? <div className="data-table-columns__menu">{columns.map((column, index) => <label key={`${column}-${index}`}><input type="checkbox" checked={visibleColumns[index]} disabled={visibleColumns.filter(Boolean).length === 1 && visibleColumns[index]} onChange={() => setVisibleColumns(current => current.map((value, currentIndex) => currentIndex === index ? !value : value))}/><span>{column}</span></label>)}</div> : null}
    </div>{exportFileName ? <button type="button" className="secondary data-table-tool-button" onClick={exportCsv}>Export CSV</button> : null}</div></div>}
    <div className="table-wrap"><table>{caption ? <caption className="sr-only">{caption}</caption> : null}<thead><tr>
      {selectable ? <th className="data-table-select-cell" scope="col"><input type="checkbox" checked={selectedOnPage} onChange={toggleDisplayedRows} aria-label="Select all records on this page" /></th> : null}
      {columns.map((column, index) => visibleColumns[index] ? <th scope="col" key={`${column}-${index}`} aria-sort={sort?.column === index ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}>{sortable ? <button type="button" className="data-table-sort" onClick={() => toggleSort(index)}><span>{column}</span><span className="data-table-sort__icon" aria-hidden="true">{sort?.column === index ? (sort.direction === "asc" ? "↑" : "↓") : "↕"}</span></button> : column}</th> : null)}
    </tr></thead><tbody>{displayedRows.length ? displayedRows.map(row => <tr key={row.id}>
      {selectable ? <td className="data-table-select-cell" data-label="Select"><input type="checkbox" checked={selected.includes(row.id)} onChange={() => toggleRow(row.id)} aria-label={`Select record ${row.id}`} /></td> : null}
      {row.cells.map((value, cellIndex) => visibleColumns[cellIndex] ? <td key={cellIndex} data-label={columns[cellIndex]}>{value}</td> : null)}
    </tr>) : <tr><td className="empty-cell" colSpan={visibleColumns.filter(Boolean).length + (selectable ? 1 : 0)}><EmptyState title={query ? "No matching records" : emptyTitle} message={query ? "Try a different search term or clear the current search." : emptyMessage} action={query ? <button type="button" className="secondary" onClick={() => setQuery("")}>Clear search</button> : emptyAction}/></td></tr>}</tbody></table></div>
    <div className="table-footer data-table-footer"><span>{filteredRows.length ? `${firstRecord}–${lastRecord} of ${filteredRows.length}` : "0 records"}</span>
      {paginated && filteredRows.length > 0 ? <div className="data-table-pagination"><label><span>Rows</span><select aria-label="Rows per page" value={currentPageSize} onChange={event => setCurrentPageSize(Number(event.target.value))}>{Array.from(new Set([pageSize, ...pageSizeOptions])).sort((a, b) => a - b).map(option => <option key={option} value={option}>{option}</option>)}</select></label><button type="button" className="secondary" disabled={safePage <= 1} onClick={() => setCurrentPage(page => Math.max(1, page - 1))} aria-label="Previous page">←</button><span>Page {safePage} of {totalPages}</span><button type="button" className="secondary" disabled={safePage >= totalPages} onClick={() => setCurrentPage(page => Math.min(totalPages, page + 1))} aria-label="Next page">→</button></div> : null}
    </div>
  </div>;
}
