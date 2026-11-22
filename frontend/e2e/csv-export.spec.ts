import { expect, test } from "@playwright/test";
import { csvCell } from "../lib/csv";

test("CSV export prevents formula injection without changing numeric stock values", () => {
  expect(csvCell("=1+1")).toBe("\"'=1+1\"");
  expect(csvCell(" +SUM(A1:A2)")).toBe("\"' +SUM(A1:A2)\"");
  expect(csvCell("-HYPERLINK(A1)")).toBe("\"'-HYPERLINK(A1)\"");
  expect(csvCell("@cmd")).toBe("\"'@cmd\"");
  expect(csvCell("\t=1+1")).toBe("\"'\t=1+1\"");
  expect(csvCell("-14.50")).toBe('\"-14.50\"');
  expect(csvCell("100.25")).toBe('\"100.25\"');
  expect(csvCell('milk "1L"')).toBe('\"milk ""1L""\"');
});
