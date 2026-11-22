/** Escape both CSV syntax and spreadsheet formula cells (Excel/Sheets). */
export function csvCell(value: string): string {
  // A leading tab, newline or whitespace can be used to disguise a formula.
  // Preserve genuine negative/positive numeric quantities as numbers in CSV.
  const trimmed = value.trimStart();
  const startsLikeFormula = /^[=+@-]/.test(trimmed);
  const isNumeric = /^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(trimmed);
  const needsNeutralizing = /^[\s\uFEFF]*[=+@-]/.test(value) && (startsLikeFormula && !isNumeric);
  const startsWithControl = /^[\t\r\n]/.test(value);
  const safe = needsNeutralizing || startsWithControl ? "'" + value : value;
  return '"' + safe.replace(/"/g, '""') + '"';
}
