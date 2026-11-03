"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  BookOpenCheck,
  Search,
  Cookie,
  PackageSearch,
  FlaskConical,
} from "lucide-react";
import { api, dateLabel } from "@/lib/api";
import type { ReferenceCase } from "@/lib/types";
export default function ReferenceLibrary({
  query,
  compact = false,
  onOpen,
}: {
  query?: string;
  compact?: boolean;
  onOpen?: () => void;
}) {
  const [localQuery, setLocalQuery] = useState("");
  const [items, setItems] = useState<ReferenceCase[]>([]);
  const [error, setError] = useState("");
  const search = query ?? localQuery;
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(
      () => {
        api<{ items: ReferenceCase[] }>(
          `/reference-cases?q=${encodeURIComponent(search)}`,
          { signal: controller.signal },
        )
          .then((result) => {
            setItems(result.items);
            setError("");
          })
          .catch((err) => {
            if (!controller.signal.aborted) setError(err.message);
          });
      },
      search ? 220 : 0,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [search]);
  if (compact && !items.length) return null;
  return (
    <section
      className={`reference-library ${compact ? "compact-library" : ""}`}
    >
      {!compact && (
        <>
          <div className="section-heading">
            <div>
              <span className="eyebrow">REAL REPORTS. ACTUAL RECEIPTS.</span>
              <h2>
                Seen it in the headlines<span className="heading-dot">?</span>
              </h2>
            </div>
            <span className="reference-pill">
              <BookOpenCheck size={13} /> Source-backed profiles
            </span>
          </div>
          <p className="reference-intro">
            Search a brand or incident. Get the story, the original notices, and
            the context.
          </p>
          <label className="reference-search">
            <Search size={17} />
            <input
              aria-label="Search real reports"
              value={localQuery}
              onChange={(event) => setLocalQuery(event.target.value)}
              placeholder="Try Priyagold, pari, husk, Delhi, or MDH…"
            />
          </label>
          <div className="reference-chips">
            {["Priyagold", "Delhi expiry", "MDH"].map((term) => (
              <button key={term} onClick={() => setLocalQuery(term)}>
                {term}
                <ArrowUpRight size={11} />
              </button>
            ))}
            {localQuery && (
              <button onClick={() => setLocalQuery("")}>Show all</button>
            )}
          </div>
        </>
      )}
      {compact && (
        <div className="micro-heading" style={{ marginBottom: 10 }}>
          KNOWN REPORTS MATCH YOUR SEARCH
        </div>
      )}
      {error && <p className="small-text muted">{error}</p>}
      <div className="reference-grid">
        {items.map((item) => {
          const Icon = item.id.startsWith("priyagold")
            ? Cookie
            : item.id.startsWith("delhi")
              ? PackageSearch
              : FlaskConical;
          return (
            <Link
              key={item.id}
              href={`/reports/${item.id}`}
              className="reference-card"
              onClick={onOpen}
            >
              <div className="reference-card-top">
                <span className="reference-icon">
                  <Icon size={20} />
                </span>
                <span>
                  {dateLabel(item.published_at)}{" "}
                  {new Date(item.published_at).getFullYear()}
                </span>
                <ArrowUpRight size={17} />
              </div>
              <span className="eyebrow">{item.brand}</span>
              <h3>{item.title}</h3>
              <p>{item.summary}</p>
              <div className="reference-card-bottom">
                <span>{item.status}</span>
                <b>
                  {item.sources.length} sources <ArrowUpRight size={12} />
                </b>
              </div>
            </Link>
          );
        })}
      </div>
      {!items.length && !error && (
        <div className="reference-empty">
          No curated match yet. Run a live scan for fresh public signals.
        </div>
      )}
      {!compact && (
        <p className="reference-footnote">
          Source profiles preserve their original dates and jurisdictions. Open
          the original notices for product and batch scope.
        </p>
      )}
    </section>
  );
}
