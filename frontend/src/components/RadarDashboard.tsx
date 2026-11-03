"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import {
  Radar,
  ArrowUpRight,
  ArrowRight,
  ShieldCheck,
  TrendingUp,
  Clock3,
  Search,
  RefreshCw,
  Activity,
  Factory,
  Flag,
  ScanLine,
  Snowflake,
  Network,
  ChevronRight,
  CheckCircle2,
} from "lucide-react";
import { Shell } from "./Shell";
import TriVectorCard from "./TriVectorCard";
import EvidenceWall from "./EvidenceWall";
import ReferenceLibrary from "./ReferenceLibrary";
import { api, vectorNames, dateLabel } from "@/lib/api";
import { hostedDemo } from "@/lib/demo-mode";
import type {
  CaseSummary,
  CaseDetail,
  Telemetry,
  EvidenceResponse,
  Signal,
} from "@/lib/types";
const ScanModal = dynamic(() => import("./ScanModal"));
const TriggerwareModal = dynamic(() => import("./TriggerwareModal"));

export default function RadarDashboard() {
  const params = useSearchParams();
  const view = params.get("view") || "radar";
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [details, setDetails] = useState<CaseDetail[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [mode, setMode] = useState("all");
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [scanQuery, setScanQuery] = useState("");
  const [scanOpen, setScanOpen] = useState(false);
  const [activeAction, setActiveAction] = useState<CaseDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setError("");
    try {
      const [nextCases, nextTelemetry] = await Promise.all([
        api<CaseSummary[]>(`/cases?mode=${mode}`),
        api<Telemetry>("/telemetry"),
      ]);
      setCases(nextCases);
      setTelemetry(nextTelemetry);
      const results = await Promise.all(
        nextCases.map(async (item) => {
          const [detail, evidence] = await Promise.all([
            api<CaseDetail>(`/cases/${item.id}`),
            api<EvidenceResponse>(`/cases/${item.id}/evidence?limit=100`),
          ]);
          return { detail, evidence };
        }),
      );
      setDetails(results.map((item) => item.detail));
      setSignals(results.flatMap((item) => item.evidence.items));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [mode]);
  useEffect(() => {
    void load();
  }, [load]);
  const filtered = cases.filter(
    (item) =>
      (filter === "all" || item.dominant_vector === filter) &&
      `${item.title} ${item.product_name} ${item.brand_name}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const openScan = () => {
    setScanQuery("");
    setScanOpen(true);
  };
  const featured = details.find((item) => item.dominant_vector === "batch");
  const pending = details.flatMap((item) =>
    item.grievances.map((grievance) => ({ ...grievance, caseId: item.id })),
  );
  return (
    <Shell onScan={openScan}>
      {view === "radar" ? (
        <>
          <section className="hero">
            <div className="hero-copy">
              <div className="hero-eyebrow">
                <span className="live-dot" /> BEFORE THE RECALL. AHEAD OF THE
                CURVE.
              </div>
              <h1>
                Bad stuff.
                <br />
                Good <span>intel.</span>
              </h1>
              <p>
                Sketchy sellers. Bad batches. Cold-chain fails.
                <br />
                We connect the signals before they become your problem.
              </p>
              <form
                className="hero-search"
                onSubmit={(event) => {
                  event.preventDefault();
                  setScanOpen(true);
                }}
              >
                <Search size={20} />
                <input
                  aria-label={
                    hostedDemo ? "Search source reports" : "Product to scan"
                  }
                  placeholder={
                    hostedDemo
                      ? "Try pari case, MDH, Delhi…"
                      : "What's in your cart?"
                  }
                  value={scanQuery}
                  onChange={(event) => setScanQuery(event.target.value)}
                />
                <button type="submit">
                  {hostedDemo ? "Find reports" : "Scan it"}{" "}
                  <ArrowUpRight size={17} />
                </button>
              </form>
              <div className="hero-search-note">
                <ShieldCheck size={13} />{" "}
                {hostedDemo
                  ? "Curated public reports. Original sources. Free demo."
                  : "Public signals. Personal details scrubbed. No guesswork."}
              </div>
            </div>
            <div className="hero-radar" aria-hidden="true">
              <div className="radar-ring r1" />
              <div className="radar-ring r2" />
              <div className="radar-ring r3" />
              <div className="radar-axis x" />
              <div className="radar-axis y" />
              <div className="radar-sweep" />
              <div className="radar-center">
                <Flag size={28} fill="currentColor" />
                <span>red flag.</span>
              </div>
              <span className="radar-blip b1" />
              <span className="radar-blip b2" />
              <span className="radar-blip b3" />
              <div className="floating-signal fs1">
                <span className="floating-icon red-bg">
                  <Factory size={16} />
                </span>
                <div>
                  Same batch. 4 cities.<small>Connecting the dots.</small>
                </div>
                <span className="mini-pill">+56%</span>
              </div>
              <div className="floating-signal fs2">
                <span className="floating-icon cyan-bg">
                  <Snowflake size={16} />
                </span>
                <div>
                  A local cold-chain fail.
                  <small>Kept local. Not nationwide.</small>
                </div>
              </div>
              <div className="radar-caption">
                <span className="status-dot" /> THREE VECTORS. ONE CLEARER
                PICTURE.
              </div>
            </div>
          </section>
          <section className="telemetry-grid" aria-label="Vigilance telemetry">
            {[
              {
                icon: Radar,
                label: "Open investigations",
                value: telemetry?.active_cases ?? "—",
                note: "Signals worth a closer look",
                color: "red",
              },
              {
                icon: TrendingUp,
                label: "Velocity alerts",
                value: telemetry?.velocity_alerts ?? "—",
                note: "Picking up in the last 48h",
                color: "orange",
              },
              {
                icon: Clock3,
                label: "Grievances on the clock",
                value: telemetry?.pending_grievances ?? "—",
                note: "15-day resolution tracker",
                color: "purple",
              },
              {
                icon: ShieldCheck,
                label: hostedDemo
                  ? "Investigation data"
                  : "Privacy at the edge",
                value: hostedDemo ? "Demo" : "On",
                note: hostedDemo
                  ? "Three synthetic scenarios"
                  : "Personal details scrubbed",
                color: "green",
              },
            ].map((metric) => (
              <div className="metric" key={metric.label}>
                <div className="metric-label">
                  <span className={`metric-icon ${metric.color}`}>
                    <metric.icon size={15} />
                  </span>
                  {metric.label}
                </div>
                <div className="metric-value">
                  {metric.value}
                  {metric.color === "green" && <span className="status-dot" />}
                </div>
                <span className="metric-note">{metric.note}</span>
              </div>
            ))}
          </section>
        </>
      ) : (
        <section className="page-intro">
          <span className="hero-eyebrow">
            <span className="live-dot" /> KNOW BEFORE YOU CONSUME
          </span>
          <h1>
            {view === "evidence" ? "Receipts, please." : "Make the next move."}
          </h1>
          <p>
            {view === "evidence"
              ? "The reviews, reports and lab-test clips behind the signals."
              : "Turn a strong signal into a clear, reviewable next step."}
          </p>
        </section>
      )}
      <div className="demo-strip">
        <span className="demo-badge">
          {hostedDemo ? "READ-ONLY DEMO" : "DEMO + LIVE"}
        </span>
        <p>
          {hostedDemo
            ? "Saved synthetic investigations + curated real reports. "
            : "Three fictional scenarios show how it works. "}
          <button onClick={openScan}>
            {hostedDemo ? "Search real reports" : "Run a live scan"}{" "}
            <ArrowUpRight size={12} />
          </button>{" "}
          {hostedDemo
            ? "Live scans and editing run locally."
            : "to bring your own product into the radar."}
        </p>
        {!hostedDemo && (
          <div className="mode-switch" aria-label="Data mode">
            {["all", "demo", "live"].map((value) => (
              <button
                key={value}
                className={mode === value ? "selected" : ""}
                onClick={() => setMode(value)}
              >
                {value === "all" ? "All" : value === "demo" ? "Demo" : "Live"}
              </button>
            ))}
          </div>
        )}
      </div>
      {error && (
        <div className="error-box" role="alert">
          {error}
          <button className="text-button" onClick={load}>
            Retry
          </button>
        </div>
      )}
      {view === "radar" && (
        <>
          <ReferenceLibrary />
          <section className="radar-section">
            <div className="section-heading">
              <div>
                <span className="eyebrow">THE BIG PICTURE</span>
                <h2>
                  {hostedDemo
                    ? "A closer look at the signals"
                    : "Your radar, right now"}
                  <span className="heading-dot">.</span>
                </h2>
              </div>
              <button
                className="refresh-button"
                onClick={load}
                aria-label="Refresh radar"
              >
                <RefreshCw size={14} />
                <span>
                  {hostedDemo ? "Snapshot" : "Updated"}{" "}
                  {telemetry ? dateLabel(telemetry.last_updated) : "…"}
                </span>
              </button>
            </div>
            <div className="case-toolbar">
              <div className="filter-tabs">
                {[
                  { id: "all", label: "All signals", icon: Activity },
                  { id: "batch", label: "Factory batch", icon: Factory },
                  { id: "counterfeit", label: "Counterfeit", icon: ScanLine },
                  { id: "dark_store", label: "Dark store", icon: Snowflake },
                ].map((tab) => (
                  <button
                    className={filter === tab.id ? "active" : ""}
                    key={tab.id}
                    onClick={() => setFilter(tab.id)}
                  >
                    <tab.icon size={14} />
                    {tab.label}
                    {tab.id === "all" && <span>{cases.length}</span>}
                  </button>
                ))}
              </div>
              <label className="mini-search">
                <Search size={15} />
                <input
                  aria-label="Filter cases"
                  placeholder="Find a case"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
            </div>
            {loading ? (
              <div className="loading-panel">Following the signals…</div>
            ) : (
              <div className="case-grid">
                {filtered.map((item, index) => (
                  <TriVectorCard key={item.id} item={item} index={index} />
                ))}
              </div>
            )}
            {!loading && !filtered.length && (
              <div className="empty-state">
                <Radar size={30} />
                <h3>
                  {mode === "live"
                    ? "Your next investigation starts here."
                    : "No matching cases."}
                </h3>
                <p>
                  {mode === "live"
                    ? "Scan a product to collect public evidence and build a live case."
                    : "Try another filter or search."}
                </p>
                <button className="button dark" onClick={openScan}>
                  {hostedDemo ? "Search reports" : "Scan a product"}{" "}
                  <ArrowUpRight size={16} />
                </button>
              </div>
            )}
          </section>
        </>
      )}
      {view === "radar" && (
        <>
          <div className="interpretation-note">
            <span className="note-symbol">↗</span>
            <p>
              <b>Not every red flag points to the factory.</b>
              <br />
              <span>
                Our three-vector view separates bad batches, sketchy sellers and
                local storage fails. Better attribution. Smarter action.
              </span>
            </p>
            <div className="three-dots">
              <i />
              <i />
              <i />
            </div>
          </div>
          <section className="insight-grid">
            <div className="connection-teaser">
              <div className="section-heading small-heading">
                <div>
                  <span className="eyebrow">THE PLOT THICKENS</span>
                  <h3>Different brands. Same plant.</h3>
                </div>
                <Network size={20} />
              </div>
              <p className="muted">
                A manufacturing license can connect signals that look unrelated.
              </p>
              <div className="mini-network">
                <span className="mini-brand">
                  MasalaClub<small>SPICE BLEND</small>
                </span>
                <span className="network-line" />
                <span className="mini-facility">
                  <Factory size={22} />
                  <small>10012021000518</small>
                </span>
                <span className="network-line" />
                <span className="mini-brand">
                  SnackLab<small>CHILLI MIX</small>
                </span>
              </div>
              {featured && (
                <Link
                  href={`/cases/${featured.id}?tab=graph`}
                  className="text-link"
                >
                  Follow the connection <ArrowRight size={14} />
                </Link>
              )}
              <span className="synthetic-footnote">
                Illustrative synthetic linkage
              </span>
            </div>
            <div className="clock-teaser">
              <div className="section-heading small-heading">
                <div>
                  <span className="eyebrow">TIME MATTERS</span>
                  <h3>Don&apos;t let it slip.</h3>
                </div>
                <Clock3 size={20} />
              </div>
              {pending.length ? (
                pending.map((item) => (
                  <Link
                    href={`/cases/${item.caseId}`}
                    className="clock-row"
                    key={item.id}
                  >
                    <span className="clock-icon">
                      <Clock3 size={20} />
                    </span>
                    <div>
                      <b>Food Safety Connect</b>
                      <small>
                        {item.id} ·{" "}
                        {item.status === "resolved"
                          ? "Resolved"
                          : `Day ${item.days_elapsed} of 15`}
                      </small>
                      <div className="deadline-track">
                        <span
                          style={{
                            width: `${(item.days_elapsed / 15) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                    <ChevronRight size={17} />
                  </Link>
                ))
              ) : (
                <div className="all-clear">
                  <CheckCircle2 size={20} />
                  No open grievance timers.
                </div>
              )}
              <p className="small-text muted">
                Draft actions help an operator respond. External submissions
                remain manual.
              </p>
            </div>
          </section>
          <section className="evidence-preview">
            <div className="section-heading">
              <div>
                <span className="eyebrow">STRAIGHT FROM THE SIGNALS</span>
                <h2>
                  The evidence wall<span className="heading-dot">.</span>
                </h2>
              </div>
              <Link href="/?view=evidence" className="text-link">
                All evidence <ArrowRight size={14} />
              </Link>
            </div>
            <EvidenceWall
              signals={signals.filter((item) => item.entities.length > 0)}
              compact
            />
          </section>
        </>
      )}
      {view === "evidence" && <EvidenceWall signals={signals} />}
      {view === "actions" && (
        <div className="actions-grid">
          {details.map((item) => (
            <article className="action-case" key={item.id}>
              <span className={`vector-label ${item.dominant_vector}`}>
                {vectorNames[item.dominant_vector]}
              </span>
              <h3>{item.title}</h3>
              <p className="muted">
                {item.id} · Risk {item.risk_score}/100
              </p>
              <div className="action-count">
                {item.packets.length}
                <span>
                  draft documents
                  <br />
                  ready to review
                </span>
              </div>
              <button
                className="button dark full-width"
                onClick={() => setActiveAction(item)}
              >
                Open action desk <ArrowUpRight size={16} />
              </button>
            </article>
          ))}
        </div>
      )}
      {scanOpen && (
        <ScanModal
          initialQuery={scanQuery}
          providers={telemetry?.providers}
          onClose={() => setScanOpen(false)}
          onComplete={load}
        />
      )}
      {activeAction && (
        <TriggerwareModal
          item={activeAction}
          onClose={() => setActiveAction(null)}
          onUpdate={async () => {
            await load();
            const fresh = await api<CaseDetail>(`/cases/${activeAction.id}`);
            setActiveAction(fresh);
          }}
        />
      )}
    </Shell>
  );
}
