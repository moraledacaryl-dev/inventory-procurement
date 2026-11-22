import { expect, test } from "@playwright/test";
import { formatApiError } from "../lib/api";

test("validation errors show field paths and human-readable messages", () => {
  const detail = [
    { loc: ["body", "lines", 0, "received_quantity"], msg: "Input should be greater than 0" },
    { loc: ["body", "delivery_reference"], msg: "Field required" },
  ];
  expect(formatApiError(detail, "fallback")).toBe(
    "lines > 0 > received_quantity: Input should be greater than 0; delivery_reference: Field required"
  );
  expect(formatApiError({ problem: { nested: true } }, "Request failed (500)")).toBe("Request failed (500)");
  expect(formatApiError({ message: "Delivery already recorded" }, "fallback")).toBe("Delivery already recorded");
  expect(formatApiError(" Stock not available ", "fallback")).toBe("Stock not available");
});
