"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import {
  ArrowRight,
  ArrowUpRight,
  ChevronRight,
  Layers3,
  Network,
  ScrollText,
  Clock3,
  MapPin,
  TrendingUp,
  FileCheck2,
  ShieldCheck,
  FlaskConical,
  RefreshCw,
} from "lucide-react";
import { Shell } from "./Shell";
import { FactorBars, AttributionBar } from "./TriVectorCard";
import EvidenceWall from "./EvidenceWall";
import { api, vectorNames, dateLabel } from "@/lib/api";
import type { CaseDetail, EvidenceResponse, Signal } from "@/lib/types";
const KnowledgeGraphView = dynamic(() => import("./KnowledgeGraphView"), {
  ssr: false,
  loading: () => <div className="loading-panel">Connecting the dots…</div>,
});
const RiskHistory = dynamic(() => import("./RiskHistory"), { ssr: false });
const TriggerwareModal = dynamic(() => import("./TriggerwareModal"));
const ScanModal = dynamic(() => import("./ScanModal"));
export default function CaseExplorer({ id }: { id: string }) {
  const params = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") || "evidence");
  const [item, setItem] = useState<CaseDetail | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [error, setError] = useState("");
  const [actions, setActions] = useState(false);
  const [scan, setScan] = useState(false);
  const load = useCallback(async () => {
    try {
      const [detail, evidence] = await Promise.all([
        api<CaseDetail>(`/cases/${id}`),
        api<EvidenceResponse>(`/cases/${id}/evidence?limit=100`),
      ]);
      setItem(detail);
      setSignals(evidence.items);
      setError("");
    } catch (err) {
      setError((err as Error).message);
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <Shell onScan={() => setScan(true)}>
      <div className="breadcrumbs">
        <Link href="/">The radar</Link>
        <ChevronRight size={12} />
        <span>{id}</span>
      </div>
      {error && (
        <div className="error-box" role="alert" style={{ marginTop: 25 }}>
          {error}
          <button onClick={load} className="text-button">
            Retry
          </button>
        </div>
      )}
      {!item ? (
        !error && <div className="loading-panel">Reading the signals…</div>
      ) : (
        <>
          <section className="case-hero">
            <div>
              <span className={`vector-label ${item.dominant_vector}`}>
                {vectorNames[item.dominant_vector]} ·{" "}
                {item.synthetic ? "Synthetic demo" : "Live investigation"}
              </span>
              <h1>{item.title}</h1>
              <p>{item.summary}</p>
              <div className="case-header-meta">
                <span>
                  <MapPin size={12} />
                  {item.cities.join(" · ") || "Location unconfirmed"}
                </span>
                <span>
                  <TrendingUp size={12} />+
                  {Math.round(item.delta_velocity_48h * 100)}% / 48h
                </span>
                <span>{item.complaint_count_48h} complaints / 48h</span>
              </div>
            </div>
            <div className="detail-risk">
              <strong>{item.risk_score}</strong>
              <small>/100</small>
              <span>TRIAGE RISK SCORE</span>
            </div>
          </section>
          <section className="case-overview">
            <div>
              <span className="micro-heading">THE FOUR FACTORS</span>
              <FactorBars scores={item.sub_scores} />
            </div>
            <div className="overview-attribution">
              <span className="micro-heading">WHERE THE EVIDENCE POINTS</span>
              <AttributionBar attribution={item.attribution} detailed />
              <p className="attribution-reason">
                {item.attribution_reasons[item.dominant_vector]
                  ?.slice(0, 2)
                  .join(" · ") || "Attribution requires more evidence."}
              </p>
            </div>
          </section>
          <div className="detail-tabs" role="tablist" aria-label="Case views">
            {[
              { id: "evidence", icon: Layers3, label: "The evidence" },
              { id: "graph", icon: Network, label: "The connections" },
              { id: "records", icon: ScrollText, label: "Official records" },
            ].map((value) => (
              <button
                key={value.id}
                role="tab"
                aria-selected={tab === value.id}
                className={tab === value.id ? "active" : ""}
                onClick={() => setTab(value.id)}
              >
                <value.icon size={14} />
                {value.label}
              </button>
            ))}
          </div>
          <div className="case-body">
            <section role="tabpanel">
              {tab === "evidence" ? (
                <EvidenceWall signals={signals} />
              ) : tab === "graph" ? (
                <KnowledgeGraphView caseId={id} />
              ) : (
                <div className="regulatory-list">
                  {item.regulatory_records.length ? (
                    item.regulatory_records.map((record) => (
                      <article className="record-card" key={record.id}>
                        <span className="eyebrow">
                          {record.source.toUpperCase()}
                          {record.synthetic ? " · SYNTHETIC" : ""}
                        </span>
                        <h3>{record.action_type}</h3>
                        <p>{record.reason_for_recall}</p>
                        <small>Recorded {dateLabel(record.start_date)}</small>
                      </article>
                    ))
                  ) : (
                    <div className="empty-state">
                      <ScrollText size={27} />
                      <h3>No matched official record.</h3>
                      <p>
                        This means no record was observed in the imported
                        sources. It is not regulatory clearance.
                      </p>
                    </div>
                  )}
                  <div className="record-card">
                    <span className="eyebrow">ASSESSMENT HISTORY</span>
                    <h3>What changed.</h3>
                    {item.audit_events.length ? (
                      item.audit_events.map((event, index) => (
                        <div key={index} className="timeline-entry">
                          <b>{event.event.replaceAll("_", " ")}</b>
                          <span>{dateLabel(event.timestamp)}</span>
                        </div>
                      ))
                    ) : (
                      <p>
                        Initial synthetic assessment. New live assessments are
                        versioned and recorded.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </section>
            <aside className="case-aside">
              <div className="aside-card">
                <span className="eyebrow red">THE NEXT MOVE</span>
                <h3>Strong signal. Clear action.</h3>
                <p>
                  {item.packets.length
                    ? `${item.packets.length} draft documents match this case's risk and attribution. Inspect the facts before external use.`
                    : "More corroboration is needed before an action packet is generated."}
                </p>
                <button
                  className="button dark full-width"
                  onClick={() => setActions(true)}
                >
                  <FileCheck2 size={14} />
                  Open action desk
                  <ArrowUpRight size={14} />
                </button>
              </div>
              <RiskHistory data={item.score_history} />
              <div className="aside-card">
                <details className="formula-details">
                  <summary>Why this score?</summary>
                  <p>
                    The four-factor baseline is amplified continuously while
                    regulatory evidence remains low.
                  </p>
                  <div className="formula-line">
                    <span>Baseline</span>
                    <b>{item.assessment.base_score.toFixed(2)}</b>
                  </div>
                  <div className="formula-line">
                    <span>Amplification</span>
                    <b>×{item.assessment.amplification.toFixed(3)}</b>
                  </div>
                  <div className="formula-line">
                    <span>48h velocity</span>
                    <b>{item.assessment.velocity}</b>
                  </div>
                  <p>
                    {item.synthetic
                      ? "Supplied demonstration factors reproduce the flagship scenario exactly."
                      : item.assessment.evidence_policy?.note}
                  </p>
                  {item.assessment.baseline_available === false && (
                    <p>
                      No 48-hour historical baseline yet; growth is zero until
                      supported.
                    </p>
                  )}
                  <p>{item.assessment.policy_version}</p>
                </details>
              </div>
              {item.dark_store_nodes?.map((node) => (
                <div className="aside-card" key={node.id}>
                  <span className="eyebrow">LOCAL NODE</span>
                  <h3>{node.name}</h3>
                  <p>
                    {node.city} · {node.radius_km} km radius
                    <br />
                    {node.complaints} synthetic complaints
                  </p>
                </div>
              ))}
              <div className="aside-card">
                <span className="privacy-badge">
                  <ShieldCheck size={14} />
                  {item.synthetic
                    ? "Synthetic demonstration"
                    : "PII scrubber enabled"}
                </span>
                <p style={{ marginTop: 12, marginBottom: 0 }}>
                  Reported cues support triage. They do not establish clinical
                  causality or an issued recall.
                </p>
              </div>
            </aside>
          </div>
          {item.synthetic && (
            <p className="provenance-note">{item.provenance}</p>
          )}
        </>
      )}
      {actions && item && (
        <TriggerwareModal
          item={item}
          onClose={() => setActions(false)}
          onUpdate={load}
        />
      )}
      {scan && (
        <ScanModal
          initialQuery={item?.product_name}
          onClose={() => setScan(false)}
          onComplete={load}
        />
      )}
    </Shell>
  );
}
