import test from "node:test";
import assert from "node:assert/strict";

function formatQueryString(params: Record<string, any>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.append(key, String(value));
    }
  }
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}

function normalizeApiError(errPayload: any, status: number): { detail: string; status: number } {
  let detail = "An unexpected error occurred.";
  if (errPayload && typeof errPayload === "object") {
    if (typeof errPayload.detail === "string") {
      detail = errPayload.detail;
    } else if (Array.isArray(errPayload.detail)) {
      detail = errPayload.detail.map((e: any) => e.msg || JSON.stringify(e)).join(", ");
    }
  }
  return { detail, status };
}

test("Query string formatter strips null and undefined values", () => {
  const qs = formatQueryString({
    page: 1,
    limit: 20,
    search: "cardio",
    emptyField: "",
    nullField: null,
    undefinedField: undefined,
  });
  assert.equal(qs, "?page=1&limit=20&search=cardio");
});

test("Query string formatter returns empty string when no valid parameters exist", () => {
  const qs = formatQueryString({ a: null, b: undefined, c: "" });
  assert.equal(qs, "");
});

test("API error normalizer extracts standard detail string", () => {
  const res = normalizeApiError({ detail: "Resource conflict detected" }, 409);
  assert.equal(res.status, 409);
  assert.equal(res.detail, "Resource conflict detected");
});

test("API error normalizer handles Pydantic validation error lists", () => {
  const res = normalizeApiError(
    {
      detail: [
        { loc: ["body", "email"], msg: "value is not a valid email address" },
        { loc: ["body", "password"], msg: "Password must be at least 8 characters long." },
      ],
    },
    422
  );
  assert.equal(res.status, 422);
  assert.ok(res.detail.includes("valid email address"));
  assert.ok(res.detail.includes("at least 8 characters"));
});
