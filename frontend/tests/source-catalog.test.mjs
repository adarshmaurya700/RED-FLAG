import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  isSourceCatalog,
  safeProofUrl,
} from "../src/lib/source-catalog-schema.ts";

const catalog = JSON.parse(
  readFileSync(
    new URL("../src/data/source-catalog.json", import.meta.url),
    "utf8",
  ),
);
test("real collected catalogue satisfies the hosted contract", () => {
  assert.equal(isSourceCatalog(catalog), true);
  assert.ok(
    catalog.items.some(
      (item) => item.source === "trustified" && item.outcome === "fail",
    ),
  );
  assert.ok(
    catalog.items.some(
      (item) =>
        item.source === "foodpharmer" &&
        item.review_method === "label_reviewed",
    ),
  );
});
test("invalid and unsafe catalogues are rejected before caching", () => {
  for (const mutate of [
    (value) => {
      value.schema_version = 99;
    },
    (value) => {
      value.items[0].source_url = "https://attacker.example/product";
    },
    (value) => {
      value.items[0].proof_links[0].url = "javascript:alert(1)";
    },
    (value) => {
      value.items[0].outcome = "safe_forever";
    },
    (value) => {
      value.items[0].fetched_at = "yesterday";
    },
    (value) => {
      value.items.push(value.items[0]);
    },
    (value) => {
      delete value.sources.foodpharmer;
    },
  ]) {
    const invalid = structuredClone(catalog);
    mutate(invalid);
    assert.equal(isSourceCatalog(invalid), false);
  }
  for (const url of [
    "http://example.org",
    "https://127.0.0.1",
    "https://[::1]",
    "https://user:password@example.org",
    "https://example.local",
  ])
    assert.equal(safeProofUrl(url), false);
});
