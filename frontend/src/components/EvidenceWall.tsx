"use client";
import { useMemo, useState } from "react";
import {
  Search,
  SlidersHorizontal,
  ShieldCheck,
  ExternalLink,
  BadgeCheck,
  Play,
  MessageSquare,
  Newspaper,
  Clock3,
  ChevronDown,
  FlaskConical,
} from "lucide-react";
import type { Entity, Signal } from "@/lib/types";
import { timeAgo } from "@/lib/api";

function Highlighted({ text, entities }: { text: string; entities: Entity[] }) {
  const matches = entities
    .filter((entity) => entity.text.length > 2)
    .sort((a, b) => b.text.length - a.text.length);
  if (!matches.length) return <>{text}</>;
  const pattern = new RegExp(
    `(${matches.map((entity) => entity.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`,
    "gi",
  );
  return (
    <>
      {text.split(pattern).map((part, index) => {
        const entity = matches.find(
          (item) => item.text.toLowerCase() === part.toLowerCase(),
        );
        return entity ? (
          <mark
            key={index}
            className={`entity-${entity.kind}`}
            title={entity.normalized}
          >
            {part}
          </mark>
        ) : (
          part
        );
      })}
    </>
  );
}

export function EvidenceCard({ item }: { item: Signal }) {
  const [expanded, setExpanded] = useState(false);
  const Icon =
    item.evidence_type === "video"
      ? Play
      : item.evidence_type === "news"
        ? Newspaper
        : MessageSquare;
  const onset = item.clinical.onset_latency_hours;
  return (
    <article className="evidence-card">
      <div className="evidence-top">
        <span className={`source-icon ${item.evidence_type}`}>
          <Icon size={16} />
        </span>
        <div>
          <b>{item.platform}</b>
          <span>
            {item.geography.city ||
              (item.evidence_type === "news" && "News report") ||
              "Public signal"}{" "}
            · {timeAgo(item.timestamp)}
          </span>
        </div>
        <span className="evidence-language">{item.language.toUpperCase()}</span>
      </div>
      <div className={`evidence-text ${expanded ? "expanded" : ""}`}>
        <Highlighted text={item.text} entities={item.entities} />
      </div>
      {item.text.length > 260 && (
        <button className="text-button" onClick={() => setExpanded(!expanded)}>
          {expanded ? "Show less" : "Read full signal"}
        </button>
      )}
      <div className="causality-badges">
        {onset !== null && (
          <span>
            <Clock3 size={11} /> Onset:{" "}
            {onset < 1 ? `${Math.round(onset * 60)}m` : `${onset}h`}
          </span>
        )}
        {item.clinical.dechallenge_status !== "unknown" && (
          <span>Dechallenge: {item.clinical.dechallenge_status}</span>
        )}
        {item.clinical.rechallenge_status !== "unknown" && (
          <span>Rechallenge: {item.clinical.rechallenge_status}</span>
        )}
        {item.lab_evidence !== "none" && (
          <span>
            <FlaskConical size={11} /> Lab attachment ·{" "}
            {item.lab_evidence === "verified" ? "verified" : "unverified"}
          </span>
        )}
        {item.verified_purchase && (
          <span>
            <BadgeCheck size={11} /> Verified purchase
            {item.synthetic ? " · demo" : ""}
          </span>
        )}
      </div>
      <div className="evidence-bottom">
        <span className="privacy-badge">
          <ShieldCheck size={12} />
          {item.synthetic ? "Synthetic evidence" : "PII scrubbed"}
        </span>
        {item.source_url ? (
          <a href={item.source_url} target="_blank" rel="noreferrer">
            Source <ExternalLink size={12} />
          </a>
        ) : (
          <span className="muted small-text">Demo source</span>
        )}
      </div>
    </article>
  );
}

export default function EvidenceWall({
  signals,
  compact = false,
}: {
  signals: Signal[];
  compact?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState("all");
  const [kind, setKind] = useState("all");
  const [visible, setVisible] = useState(12);
  const platforms = useMemo(
    () => [...new Set(signals.map((item) => item.platform))].sort(),
    [signals],
  );
  const filtered = useMemo(
    () =>
      signals.filter(
        (item) =>
          (platform === "all" || platform === item.platform) &&
          (kind === "all" || item.evidence_type === kind) &&
          item.text.toLowerCase().includes(query.toLowerCase()),
      ),
    [signals, platform, kind, query],
  );
  return (
    <div className="evidence-wall">
      {!compact && (
        <div className="evidence-toolbar">
          <label className="search-field">
            <Search size={16} />
            <input
              aria-label="Search evidence"
              placeholder="Find a symptom, batch or phrase…"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setVisible(12);
              }}
            />
          </label>
          <select
            aria-label="Filter by platform"
            value={platform}
            onChange={(event) => setPlatform(event.target.value)}
          >
            <option value="all">All sources</option>
            {platforms.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
          <select
            aria-label="Filter by evidence type"
            value={kind}
            onChange={(event) => setKind(event.target.value)}
          >
            <option value="all">All evidence</option>
            <option value="complaint">Complaints</option>
            <option value="news">News</option>
            <option value="video">Videos</option>
          </select>
        </div>
      )}
      <div className={`evidence-grid ${compact ? "compact" : ""}`}>
        {filtered.slice(0, compact ? 3 : visible).map((item) => (
          <EvidenceCard key={item.id} item={item} />
        ))}
      </div>
      {!filtered.length && (
        <div className="empty-state">
          <Search size={28} />
          <h3>No signals match that filter.</h3>
          <p>Try a broader phrase or another source.</p>
        </div>
      )}
      {!compact && filtered.length > visible && (
        <button
          className="button light load-more"
          onClick={() => setVisible((value) => value + 12)}
        >
          More evidence <ChevronDown size={15} />
        </button>
      )}
    </div>
  );
}
