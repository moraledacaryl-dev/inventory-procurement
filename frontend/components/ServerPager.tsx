"use client";

export type PageInfo = {
  page: number;
  page_size: number;
  total: number;
  has_previous: boolean;
  has_next: boolean;
};

/** Shared pagination for server-backed lists; totals refer to the whole query. */
export function ServerPager({
  pagination,
  name,
  previousLabel,
  nextLabel,
  onPrevious,
  onNext,
  busy = false,
  note,
}: {
  pagination: PageInfo | null;
  name: string;
  previousLabel: string;
  nextLabel: string;
  onPrevious: () => void;
  onNext: () => void;
  busy?: boolean;
  note?: string;
}) {
  return (
    <div className="count-server-pager" role="group" aria-label={`${name} pages`}>
      <span role="status" aria-live="polite">
        {pagination
          ? `Page ${pagination.page} · ${pagination.total} matching ${name.toLowerCase()}(s).`
          : "Loading pages…"}
        {note ? ` ${note}` : ""}
      </span>
      <div>
        <button type="button" className="secondary" disabled={busy || !pagination?.has_previous} onClick={onPrevious}>
          {previousLabel}
        </button>
        <button type="button" className="secondary" disabled={busy || !pagination?.has_next} onClick={onNext}>
          {nextLabel}
        </button>
      </div>
    </div>
  );
}
