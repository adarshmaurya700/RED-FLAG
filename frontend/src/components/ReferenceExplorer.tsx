"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  ChevronRight,
  BookOpenCheck,
  FileText,
  Globe2,
  CalendarDays,
  ArrowRight,
} from "lucide-react";
import { Shell } from "./Shell";
import { api, dateLabel } from "@/lib/api";
import type { ReferenceCase } from "@/lib/types";
export default function ReferenceExplorer({ id }: { id: string }) {
  const [item, setItem] = useState<ReferenceCase | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    api<ReferenceCase>(`/reference-cases/${id}`, { signal: controller.signal })
      .then(setItem)
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      });
    return () => controller.abort();
  }, [id]);
  return (
    <Shell>
      <div className="breadcrumbs">
        <Link href="/">The radar</Link>
        <ChevronRight size={12} />
        <span>Real reports</span>
      </div>
      {error && <div className="error-box">{error}</div>}
      {!item ? (
        !error && (
          <div className="loading-panel">Opening the source record…</div>
        )
      ) : (
        <>
          <section className="report-hero">
            <span className="reference-pill">
              <BookOpenCheck size={14} /> REAL-WORLD SOURCE PROFILE
            </span>
            <span className="eyebrow">
              {item.brand} / {item.product}
            </span>
            <h1>{item.title}</h1>
            <p>{item.summary}</p>
            <div className="report-meta">
              <span>
                <CalendarDays size={14} />
                {dateLabel(item.published_at)}{" "}
                {new Date(item.published_at).getFullYear()}
              </span>
              <span>
                <Globe2 size={14} />
                {item.jurisdiction}
              </span>
              <span>{item.status}</span>
            </div>
          </section>
          <div className="report-body">
            <div>
              <section className="report-section">
                <span className="eyebrow">WHAT THE SOURCES ESTABLISH</span>
                <h2>Here are the receipts.</h2>
                {item.findings.map((finding, index) => (
                  <div className="report-finding" key={finding}>
                    <span>0{index + 1}</span>
                    <p>{finding}</p>
                  </div>
                ))}
              </section>
              <section className="report-section">
                <span className="eyebrow">OPEN THE ORIGINALS</span>
                <h2>Read it for yourself.</h2>
                <div className="source-links">
                  {item.sources.map((source) => (
                    <a
                      key={source.url}
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="source-link"
                    >
                      <span className="source-document">
                        <FileText size={22} />
                      </span>
                      <div>
                        <span className="source-publisher">
                          {source.publisher} <i>{source.kind}</i>
                        </span>
                        <h3>{source.title}</h3>
                        <p>{source.supports}</p>
                        <small>
                          {new URL(source.url).hostname} ·{" "}
                          {source.published_at
                            ? `${dateLabel(source.published_at)} ${new Date(source.published_at).getFullYear()}`
                            : "Publisher date not independently verified"}
                        </small>
                      </div>
                      <ArrowUpRight size={19} />
                    </a>
                  ))}
                </div>
              </section>
            </div>
            <aside>
              <div className="aside-card">
                <span className="eyebrow">KEEP THE CONTEXT</span>
                <h3>What this does — and doesn&apos;t — show.</h3>
                <p>{item.limitations}</p>
              </div>
              <div className="aside-card">
                <span className="eyebrow">COMPANY RESPONSE</span>
                <p style={{ marginTop: 14 }}>{item.company_response}</p>
              </div>
              <div className="aside-card">
                <span className="eyebrow">SOURCE REVIEW</span>
                <p style={{ marginTop: 14 }}>
                  Reviewed{" "}
                  {item.reviewed_at
                    ? `${dateLabel(item.reviewed_at)} ${new Date(item.reviewed_at).getFullYear()}`
                    : "November 2026"}
                  . This curated profile does not claim a fresh inspection or
                  live recall status.
                </p>
                <Link href="/" className="text-link">
                  Back to the radar <ArrowRight size={14} />
                </Link>
              </div>
            </aside>
          </div>
        </>
      )}
    </Shell>
  );
}
