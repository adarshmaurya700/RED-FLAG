"use client";
import { useEffect, useState } from "react";
import { ArrowUpRight, FlaskConical, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { SourceFinding, SourceFindingsResponse } from "@/lib/types";

const publishers = { trustified: "Trustified", foodpharmer: "Food Pharmer" };
function date(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "Asia/Kolkata",
      })
    : "Not stated";
}
function outcome(item: SourceFinding) {
  return item.testing_status === "expired"
    ? "Expired testing status"
    : {
        pass: "Reported pass",
        fail: "Reported fail",
        recommended: "Source recommendation",
        unknown: "Result not stated",
      }[item.outcome];
}
function method(item: SourceFinding) {
  return {
    independent_test: "Independent test report",
    label_reviewed: "Label reviewed",
    reported_lab_test: "Source says lab tested",
    reviewed: "Source reviewed",
    unknown: "Method not stated",
  }[item.review_method];
}

export default function SourceFindings({
  query = "",
  compact = false,
}: {
  query?: string;
  compact?: boolean;
}) {
  const [source, setSource] = useState("all"),
    [filter, setFilter] = useState("all");
  const [page, setPage] = useState(0),
    [data, setData] = useState<SourceFindingsResponse | null>(null);
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const size = compact ? 4 : 9;
  useEffect(() => {
    setPage(0);
  }, [query, source, filter]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(
      () => {
        setLoading(true);
        setError("");
        const params = new URLSearchParams({
          q: query,
          source,
          outcome: filter,
          offset: String(page * size),
          limit: String(size),
        });
        api<SourceFindingsResponse>(`/source-findings?${params}`, {
          signal: controller.signal,
        })
          .then(setData)
          .catch((err) => {
            if (!controller.signal.aborted) setError(err.message);
          })
          .finally(() => {
            if (!controller.signal.aborted) setLoading(false);
          });
      },
      query ? 220 : 0,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, source, filter, page, size, retry]);
  return (
    <section
      className={`source-findings ${compact ? "compact-findings" : ""}`}
      aria-label="Tested and reviewed products"
    >
      <div className="section-heading">
        <div>
          <span className="eyebrow">CHECK THE SOURCE</span>
          <h2>
            Tested &amp; reviewed<span className="heading-dot">.</span>
          </h2>
        </div>
        <span className="reference-pill">
          <FlaskConical size={13} /> Updated daily
        </span>
      </div>
      <p className="reference-intro">
        Trustified test reports and Food Pharmer reviews, with the original
        receipts.{" "}
        {query && (
          <>
            Results for <b>“{query}”</b>.
          </>
        )}
      </p>
      {!compact && data && (
        <div className="source-health-row">
          {Object.entries(data.sources).map(([name, health]) => (
            <div
              className={`source-health ${health.status === "ok" && !health.stale ? "healthy" : "limited"}`}
              key={name}
            >
              <b>{publishers[name as keyof typeof publishers]}</b>
              <span>
                {health.status === "ok"
                  ? "Collection complete"
                  : health.status === "partial"
                    ? "Partial coverage"
                    : "Collection limited"}{" "}
                · {health.checked}/{health.discovered} pages checked
              </span>
              <small>
                Last successful check: {date(health.last_success_at)}
                {health.stale ? " · stale" : ""}
                {health.pending ? ` · ${health.pending} pending` : ""}
              </small>
            </div>
          ))}
        </div>
      )}
      <div className="finding-toolbar">
        <label>
          Source
          <select
            value={source}
            onChange={(event) => setSource(event.target.value)}
          >
            <option value="all">Both sources</option>
            <option value="trustified">Trustified</option>
            <option value="foodpharmer">Food Pharmer</option>
          </select>
        </label>
        <label>
          Outcome
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="all">All outcomes</option>
            <option value="pass">Reported pass</option>
            <option value="fail">Reported fail</option>
            <option value="recommended">Recommendations</option>
            <option value="expired">Expired status</option>
            <option value="unknown">Result not stated</option>
          </select>
        </label>
        <span aria-live="polite">
          {loading
            ? "Checking the catalogue…"
            : `${data?.total ?? 0} matching findings`}
        </span>
      </div>
      {error ? (
        <div className="error-box" role="alert">
          {error}
          <button
            className="text-button"
            onClick={() => setRetry((value) => value + 1)}
          >
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      ) : (
        <div className="finding-grid" aria-busy={loading}>
          {data?.items.map((item) => (
            <article className="finding-card" key={item.id}>
              <div className="finding-top">
                <span className="eyebrow">{publishers[item.source]}</span>
                <span
                  className={`finding-outcome ${item.testing_status === "expired" ? "expired" : item.outcome}`}
                >
                  {outcome(item)}
                </span>
              </div>
              <span className="finding-brand">
                {item.brand || "Brand not stated"}
              </span>
              <h3>{item.product_name}</h3>
              <p className="finding-method">{method(item)}</p>
              <dl>
                <div>
                  <dt>Batch tested</dt>
                  <dd>{item.batch || "Not stated"}</dd>
                </div>
                <div>
                  <dt>
                    {item.last_verified_at ? "Source verified" : "Published"}
                  </dt>
                  <dd>{date(item.last_verified_at || item.published_at)}</dd>
                </div>
                {item.laboratory && (
                  <div>
                    <dt>Lab named by source</dt>
                    <dd>{item.laboratory}</dd>
                  </div>
                )}
                <div>
                  <dt>Last fetched</dt>
                  <dd>
                    {date(item.fetched_at)}
                    {item.stale ? " · stale" : ""}
                  </dd>
                </div>
              </dl>
              {item.availability === "unavailable" && (
                <p className="finding-warning">
                  Source could not be rechecked. Showing the last successful
                  record.
                </p>
              )}
              {item.excerpt && (
                <p className="finding-excerpt">{item.excerpt}</p>
              )}
              {item.criteria.length > 0 && (
                <details className="finding-criteria">
                  <summary>Source category criteria</summary>
                  <ul>
                    {item.criteria.map((criterion, index) => (
                      <li key={index}>{criterion}</li>
                    ))}
                  </ul>
                </details>
              )}
              <div className="finding-proofs">
                {item.proof_links.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {link.label}
                    <ArrowUpRight size={13} />
                  </a>
                ))}
              </div>
              <small className="finding-scope">
                {item.source === "trustified"
                  ? "Applies to the tested sample and the source’s stated scope."
                  : "A source recommendation under its own review criteria."}
              </small>
            </article>
          ))}
        </div>
      )}
      {!loading && !error && data?.total === 0 && (
        <div className="reference-empty">
          No matching review finding. Try a product or brand such as honey, MDH,
          Naturaltein, or paneer.
        </div>
      )}
      {data && data.total > size && (
        <div className="finding-pagination">
          <button
            className="button light small"
            disabled={page === 0 || loading}
            onClick={() => setPage((value) => value - 1)}
          >
            Previous
          </button>
          <span>
            Page {page + 1} of {Math.ceil(data.total / size)}
          </span>
          <button
            className="button light small"
            disabled={(page + 1) * size >= data.total || loading}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </button>
        </div>
      )}
      <p className="reference-footnote">
        Publisher findings support review. They don’t establish a regulator
        decision or guarantee product safety.{" "}
        {data?.catalog_origin === "bundled"
          ? "Showing the saved fallback catalogue."
          : "Search uses the latest available daily catalogue."}
      </p>
    </section>
  );
}
