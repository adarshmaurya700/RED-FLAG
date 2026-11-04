import { unstable_cache } from "next/cache";
import bundled from "@/data/source-catalog.json";
import { isSourceCatalog } from "./source-catalog-schema";
import type { SourceCatalog, SourceFindingsResponse } from "./types";

const CATALOG_URL =
  "https://raw.githubusercontent.com/adarshmaurya700/RED-FLAG/refs/heads/codex/source-data/catalog.json";
const publishedCatalog = unstable_cache(
  async (): Promise<SourceCatalog> => {
    const response = await fetch(CATALOG_URL, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) throw new Error("Published catalogue unavailable");
    if (Number(response.headers.get("content-length") || 0) > 6_000_000)
      throw new Error("Catalogue too large");
    const reader = response.body?.getReader();
    if (!reader) throw new Error("Catalogue body missing");
    let size = 0;
    const chunks: Uint8Array[] = [];
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 6_000_000) throw new Error("Catalogue too large");
        chunks.push(value);
      }
    } finally {
      await reader.cancel();
    }
    const payload: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!isSourceCatalog(payload))
      throw new Error("Invalid published catalogue");
    return payload;
  },
  ["source-catalogue-v1"],
  { revalidate: 3600 },
);

export async function loadSourceCatalog(): Promise<{
  catalog: SourceCatalog;
  origin: string;
}> {
  try {
    return { catalog: await publishedCatalog(), origin: "published" };
  } catch {
    if (!isSourceCatalog(bundled)) throw new Error("Invalid bundled catalogue");
    return { catalog: bundled, origin: "bundled" };
  }
}

export async function searchSourceFindings(
  params: URLSearchParams,
): Promise<SourceFindingsResponse> {
  const { catalog, origin } = await loadSourceCatalog();
  const q = params.get("q") || "",
    source = params.get("source") || "all",
    outcome = params.get("outcome") || "all";
  const offset = Number(params.get("offset") || 0),
    limit = Number(params.get("limit") || 20);
  if (
    q.length > 160 ||
    !["all", "trustified", "foodpharmer"].includes(source) ||
    !["all", "pass", "fail", "recommended", "expired", "unknown"].includes(
      outcome,
    ) ||
    !Number.isInteger(offset) ||
    offset < 0 ||
    !Number.isInteger(limit) ||
    limit < 1 ||
    limit > 100
  )
    throw new RangeError("Invalid source finding search");
  const terms = q.toLocaleLowerCase().match(/[\p{L}\p{M}\p{N}]+/gu) || [];
  const now = Date.now(),
    stale = (value: string | null) =>
      !value || now - Date.parse(value) > 48 * 3600_000;
  const selected = catalog.items
    .filter((item) => {
      const words: string[] =
        `${item.product_name} ${item.brand || ""} ${item.category || ""}`
          .toLocaleLowerCase()
          .match(/[\p{L}\p{M}\p{N}]+/gu) || [];
      return (
        (source === "all" || source === item.source) &&
        terms.every((term) => words.includes(term)) &&
        (outcome === "all" ||
          (outcome === "expired"
            ? item.testing_status === "expired"
            : outcome === item.outcome))
      );
    })
    .sort(
      (a, b) =>
        a.product_name
          .toLowerCase()
          .localeCompare(b.product_name.toLowerCase()) ||
        a.source.localeCompare(b.source) ||
        a.id.localeCompare(b.id),
    );
  const sources = Object.fromEntries(
    Object.entries(catalog.sources).map(
      ([name, { pending_urls, ...health }]) => [
        name,
        {
          ...health,
          pending: pending_urls.length,
          stale: stale(health.last_success_at),
        },
      ],
    ),
  ) as SourceFindingsResponse["sources"];
  return {
    items: selected
      .slice(offset, offset + limit)
      .map((item) => ({ ...item, stale: stale(item.fetched_at) })),
    total: selected.length,
    generated_at: catalog.generated_at,
    sources,
    catalog_origin: origin,
    notice:
      "Source-authored findings for review. Batch-specific tests and nutrition recommendations are not regulator decisions or safety guarantees.",
  };
}
