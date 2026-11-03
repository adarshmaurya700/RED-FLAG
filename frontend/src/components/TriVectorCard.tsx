"use client";
import Link from "next/link";
import {
  ArrowUpRight,
  ArrowRight,
  MapPin,
  TrendingUp,
  Factory,
  ScanLine,
  Snowflake,
} from "lucide-react";
import type { CaseSummary, Attribution, Scores } from "@/lib/types";
import { vectorColors, vectorNames } from "@/lib/api";
import { ProductArt } from "./ProductArt";
const factors: { key: keyof Scores; label: string }[] = [
  { key: "regulatory", label: "Regulatory" },
  { key: "adverse_events", label: "Adverse events" },
  { key: "live_web", label: "Live web" },
  { key: "credibility", label: "Credibility" },
];
export function FactorBars({ scores }: { scores: Scores }) {
  return (
    <div className="factor-bars">
      {factors.map(({ key, label }) => (
        <div className="factor-row" key={key}>
          <span>{label}</span>
          <div className="factor-track">
            <i style={{ width: `${scores[key]}%` }} className={key} />
          </div>
          <b>{Math.round(scores[key])}</b>
        </div>
      ))}
    </div>
  );
}
export function AttributionBar({
  attribution,
  detailed = false,
}: {
  attribution: Attribution;
  detailed?: boolean;
}) {
  return (
    <div className="attribution">
      <div
        className="stacked-bar"
        aria-label={`Factory ${Math.round(attribution.batch * 100)}%, counterfeit ${Math.round(attribution.counterfeit * 100)}%, dark store ${Math.round(attribution.dark_store * 100)}%`}
      >
        {(Object.keys(attribution) as (keyof Attribution)[]).map((key) => (
          <span
            key={key}
            style={{
              width: `${attribution[key] * 100}%`,
              background: vectorColors[key],
            }}
          />
        ))}
      </div>
      <div className={`attribution-legend ${detailed ? "detailed" : ""}`}>
        {(Object.keys(attribution) as (keyof Attribution)[]).map((key) => (
          <span key={key}>
            <i style={{ background: vectorColors[key] }} />
            {detailed
              ? vectorNames[key]
              : key === "batch"
                ? "Factory"
                : key === "dark_store"
                  ? "Dark store"
                  : "Counterfeit"}
            <b>{Math.round(attribution[key] * 100)}%</b>
          </span>
        ))}
      </div>
    </div>
  );
}
export default function TriVectorCard({
  item,
  index,
}: {
  item: CaseSummary;
  index: number;
}) {
  const Icon =
    item.dominant_vector === "batch"
      ? Factory
      : item.dominant_vector === "counterfeit"
        ? ScanLine
        : Snowflake;
  return (
    <article
      className="case-card"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <div className="case-card-top">
        <span className={`vector-label ${item.dominant_vector}`}>
          <Icon size={13} />
          {vectorNames[item.dominant_vector]}
        </span>
        <span className="case-number">0{index + 1}</span>
      </div>
      <ProductArt vector={item.dominant_vector} />
      <div className="case-content">
        <div className="case-brand-row">
          <span className="eyebrow">{item.brand_name}</span>
          <span className="score-tag">{item.synthetic ? "DEMO" : "LIVE"}</span>
        </div>
        <div className="case-title-row">
          <h3>
            <Link href={`/cases/${item.id}`}>{item.title}</Link>
          </h3>
          <div className="hero-score">
            <strong>{Math.round(item.risk_score)}</strong>
            <small>/ 100</small>
          </div>
        </div>
        <p className="case-subtitle">{item.subtitle}</p>
        <div className="signal-meta">
          <span>
            <TrendingUp size={12} />
            {Math.round(item.delta_velocity_48h * 100)}% velocity
          </span>
          <span>
            <MapPin size={12} />
            {item.cities.length || "—"} cities
          </span>
        </div>
        <div className="card-divider" />
        <div className="micro-heading">WHAT&apos;S DRIVING THE SIGNAL</div>
        <FactorBars scores={item.sub_scores} />
        <div className="micro-heading attribution-heading">WHERE IT POINTS</div>
        <AttributionBar attribution={item.attribution} />
        <Link className="case-footer" href={`/cases/${item.id}`}>
          <span>
            Open case file <ArrowRight size={14} />
          </span>
          <ArrowUpRight size={18} />
        </Link>
      </div>
    </article>
  );
}
