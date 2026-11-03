"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  X,
  Radar,
  ArrowUpRight,
  ArrowRight,
  LoaderCircle,
  CheckCircle2,
  CircleAlert,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Scan } from "@/lib/types";
import ReferenceLibrary from "./ReferenceLibrary";

export default function ScanModal({
  onClose,
  initialQuery = "",
  providers = {},
  onComplete,
}: {
  onClose: () => void;
  initialQuery?: string;
  providers?: Record<string, boolean>;
  onComplete?: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [product, setProduct] = useState(initialQuery);
  const [brand, setBrand] = useState("");
  const [urls, setUrls] = useState("");
  const [tinyfish, setTinyfish] = useState(false);
  const [scan, setScan] = useState<Scan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [jobId, setJobId] = useState("");
  useEffect(() => {
    const node = dialog.current;
    node?.showModal();
    return () => node?.close();
  }, []);
  useEffect(() => {
    if (!jobId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const next = await api<Scan>(`/scans/${jobId}`, {
          signal: controller.signal,
        });
        if (!active) return;
        setScan(next);
        if (["completed", "partial", "failed"].includes(next.state)) {
          setBusy(false);
          onComplete?.();
        } else timer = setTimeout(poll, 2000);
      } catch (err) {
        if (active) {
          setError((err as Error).message);
          setBusy(false);
        }
      }
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [jobId]); // One polling lifecycle per immutable scan ID.
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    setScan(null);
    try {
      const next = await api<{ id: string }>("/scans", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          product_name: product.trim(),
          brand: brand.trim(),
          sources: ["reddit", "google_news", ...(tinyfish ? ["tinyfish"] : [])],
          product_urls: urls
            .split("\n")
            .map((url) => url.trim())
            .filter(Boolean),
        }),
      });
      if (next.id === jobId) {
        const cached = await api<Scan>(`/scans/${next.id}`);
        setScan(cached);
        setBusy(!["completed", "partial", "failed"].includes(cached.state));
      } else setJobId(next.id);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }
  const terminal =
    scan && ["completed", "partial", "failed"].includes(scan.state);
  return (
    <dialog
      className="modal scan-modal"
      ref={dialog}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal-inner">
        <button
          className="icon-button modal-close"
          onClick={onClose}
          aria-label="Close scan"
        >
          <X size={20} />
        </button>
        <span className="modal-icon">
          <Radar size={25} />
        </span>
        <span className="eyebrow red">A LITTLE DUE DILIGENCE</span>
        <h2>
          Check the vibe.
          <br />
          Scan a product.
        </h2>
        <p className="muted">
          Pull real public signals into one evidence-led case file.
        </p>
        <form onSubmit={submit}>
          <label className="field-label">
            Product name
            <input
              required
              minLength={2}
              maxLength={160}
              autoFocus
              placeholder="e.g. whey protein, masala, milk"
              value={product}
              onChange={(event) => setProduct(event.target.value)}
              disabled={busy}
            />
          </label>
          {product.trim().length >= 2 && (
            <ReferenceLibrary query={product} compact onOpen={onClose} />
          )}
          <label className="field-label">
            Brand <span className="muted">optional</span>
            <input
              maxLength={100}
              placeholder="Narrow it down to a brand"
              value={brand}
              onChange={(event) => setBrand(event.target.value)}
              disabled={busy}
            />
          </label>
          <div className="scan-source-row">
            <span>Reddit public search</span>
            <span>Google News RSS</span>
          </div>
          {providers.tinyfish && (
            <details className="advanced-scan">
              <summary>Enhanced collection</summary>
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={tinyfish}
                  onChange={(event) => setTinyfish(event.target.checked)}
                />{" "}
                Include TinyFish
              </label>
              <label className="field-label">
                Supported product URLs
                <textarea
                  placeholder="https://www.amazon.in/… (one per line)"
                  value={urls}
                  onChange={(event) => setUrls(event.target.value)}
                  required={tinyfish}
                />
              </label>
            </details>
          )}
          <p className="scan-note">
            <ShieldCheck size={14} />
            Personal details are scrubbed before evidence is stored. Sources may
            restrict access; each result shows its status.
          </p>
          {error && (
            <div className="error-box" role="alert">
              {error}
            </div>
          )}
          <button
            className="button dark full-width"
            disabled={busy || !product.trim()}
          >
            {busy ? (
              <>
                <LoaderCircle className="spin" size={17} /> Following the
                signals…
              </>
            ) : (
              <>
                <Radar size={17} />
                {terminal ? "Scan again" : "Start live scan"}
                <ArrowUpRight size={17} />
              </>
            )}
          </button>
        </form>
        {scan && (
          <div className="scan-results" aria-live="polite">
            <div className="scan-state">
              {busy ? (
                <LoaderCircle size={17} className="spin" />
              ) : scan.state === "failed" ? (
                <CircleAlert size={17} />
              ) : (
                <CheckCircle2 size={17} />
              )}
              <b>
                {scan.state === "partial"
                  ? "Scan finished with source limits"
                  : scan.state === "completed"
                    ? "Scan complete"
                    : scan.state === "failed"
                      ? "Scan could not complete"
                      : "Collecting evidence"}
              </b>
            </div>
            {Object.entries(scan.results.sources || {}).map(
              ([name, result]) => (
                <div className="source-outcome" key={name}>
                  <div>
                    <b>{name.replaceAll("_", " ")}</b>
                    <small>
                      {result.message || `${result.count} records collected`}
                    </small>
                  </div>
                  <span className={result.status === "ok" ? "good" : ""}>
                    {result.status}
                  </span>
                </div>
              ),
            )}
            <p>{scan.results.message}</p>
            {scan.results.case_ids?.map((id) => (
              <Link
                className="button accent full-width"
                key={id}
                href={`/cases/${id}`}
                onClick={onClose}
              >
                Open live case <ArrowRight size={16} />
              </Link>
            ))}
          </div>
        )}
      </div>
    </dialog>
  );
}
