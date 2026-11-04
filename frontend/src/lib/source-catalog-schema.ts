import type { SourceCatalog } from "./types";

const sources = ["trustified", "foodpharmer"] as const;
const outcomes = ["pass", "fail", "recommended", "unknown"];
const statuses = ["passed", "failed", "expired", "unknown"];
const methods = [
  "independent_test",
  "label_reviewed",
  "reported_lab_test",
  "reviewed",
  "unknown",
];
const healthStatuses = ["ok", "partial", "blocked", "error", "unavailable"];
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const date = (value: unknown) =>
  typeof value === "string" && Number.isFinite(Date.parse(value));
const nullableText = (value: unknown) =>
  value === null || (typeof value === "string" && value.length <= 350);
const texts = (value: unknown, max: number) =>
  Array.isArray(value) &&
  value.length <= max &&
  value.every((item) => typeof item === "string" && item.length <= 500);
export function safeProofUrl(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 2000) return false;
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      !url.username &&
      !url.password &&
      (!url.port || url.port === "443") &&
      url.hostname.includes(".") &&
      !/^[\d.]+$/.test(url.hostname) &&
      !url.hostname.endsWith(".local") &&
      !url.hostname.endsWith(".localhost")
    );
  } catch {
    return false;
  }
}

export function isSourceCatalog(value: unknown): value is SourceCatalog {
  if (
    !object(value) ||
    value.schema_version !== 1 ||
    !date(value.generated_at) ||
    !object(value.sources) ||
    !Array.isArray(value.items) ||
    value.items.length > 5000
  )
    return false;
  for (const name of sources) {
    const info = value.sources[name];
    if (
      !object(info) ||
      !healthStatuses.includes(String(info.status)) ||
      ![info.last_attempt_at, info.last_success_at].every(
        (item) => item === null || date(item),
      ) ||
      ![info.discovered, info.checked, info.failed].every(
        (item) => Number.isInteger(item) && Number(item) >= 0,
      ) ||
      !texts(info.errors, 20) ||
      !Array.isArray(info.pending_urls) ||
      info.pending_urls.length > 5000 ||
      !info.pending_urls.every(safeProofUrl)
    )
      return false;
  }
  const seen = new Set<string>();
  return value.items.every((item) => {
    if (
      !object(item) ||
      !sources.includes(item.source as (typeof sources)[number]) ||
      typeof item.id !== "string" ||
      !/^[a-f0-9]{24}$/.test(item.id) ||
      seen.has(item.id) ||
      !safeProofUrl(item.source_url)
    )
      return false;
    seen.add(item.id);
    const host = new URL(item.source_url).hostname;
    if (
      host !==
      (item.source === "trustified"
        ? "www.trustified.in"
        : "foodpharmer.health")
    )
      return false;
    if (
      typeof item.product_name !== "string" ||
      !item.product_name.trim() ||
      item.product_name.length > 240 ||
      ![
        item.brand,
        item.category,
        item.batch,
        item.manufactured,
        item.expires,
        item.laboratory,
      ].every(nullableText)
    )
      return false;
    if (
      ![item.published_at, item.last_verified_at].every(
        (value) => value === null || date(value),
      ) ||
      ![item.fetched_at, item.first_seen_at, item.updated_at].every(date)
    )
      return false;
    if (
      !outcomes.includes(String(item.outcome)) ||
      !statuses.includes(String(item.testing_status)) ||
      !methods.includes(String(item.review_method)) ||
      !["available", "unavailable"].includes(String(item.availability)) ||
      !Number.isInteger(item.revision) ||
      Number(item.revision) < 1
    )
      return false;
    if (
      typeof item.content_hash !== "string" ||
      !/^[a-f0-9]{64}$/.test(item.content_hash) ||
      typeof item.excerpt !== "string" ||
      item.excerpt.length > 350 ||
      !texts(item.criteria, 12)
    )
      return false;
    if (
      !Array.isArray(item.proof_links) ||
      item.proof_links.length > 12 ||
      !item.proof_links.every(
        (link) =>
          object(link) &&
          typeof link.label === "string" &&
          link.label.length <= 120 &&
          safeProofUrl(link.url),
      )
    )
      return false;
    return (
      Array.isArray(item.history) &&
      item.history.length <= 5 &&
      item.history.every(
        (change) =>
          object(change) &&
          date(change.changed_at) &&
          outcomes.includes(String(change.outcome)) &&
          typeof change.testing_status === "string" &&
          typeof change.content_hash === "string",
      )
    );
  });
}
