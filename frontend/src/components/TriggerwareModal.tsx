"use client";
import { useEffect, useRef, useState } from "react";
import {
  X,
  Download,
  FileText,
  ArrowUpRight,
  FileJson,
  ShieldAlert,
  CheckCircle2,
  Clock3,
} from "lucide-react";
import { api, dateLabel } from "@/lib/api";
import type { CaseDetail, Packet } from "@/lib/types";
import WorkflowTracker from "./WorkflowTracker";
import { hostedDemo } from "@/lib/demo-mode";
export default function TriggerwareModal({
  item,
  onClose,
  onUpdate,
}: {
  item: CaseDetail;
  onClose: () => void;
  onUpdate: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [selected, setSelected] = useState<Packet | null>(
    item.packets[0] || null,
  );
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const node = dialog.current;
    node?.showModal();
    return () => node?.close();
  }, []);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setPreview(null);
    api<Record<string, unknown>>(`/packets/${selected.id}`, {
      signal: controller.signal,
    })
      .then(setPreview)
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      });
    return () => controller.abort();
  }, [selected]);
  async function resolve(id: string) {
    setBusy(true);
    try {
      await api(`/grievances/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "resolved" }),
      });
      onUpdate();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <dialog
      className="modal drawer"
      ref={dialog}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="drawer-inner">
        <button
          className="icon-button modal-close"
          onClick={onClose}
          aria-label="Close action desk"
        >
          <X size={20} />
        </button>
        <span className="eyebrow red">FROM SIGNAL TO NEXT STEP</span>
        <h2>The action desk.</h2>
        <p className="muted">{item.id} · Drafts ready for operator review</p>
        <div className="draft-notice">
          <ShieldAlert size={19} />
          <span>
            {item.synthetic
              ? "Synthetic scenario. These documents demonstrate the workflow."
              : "Review facts and required fields before any external use."}{" "}
            Exports do not submit a notice.
          </span>
        </div>
        <div className="packet-list">
          {item.packets.map((packet) => (
            <button
              className={`packet-option ${selected?.id === packet.id ? "selected" : ""}`}
              key={packet.id}
              onClick={() => setSelected(packet)}
            >
              <FileText size={20} />
              <span>
                <b>{packet.title}</b>
                <small>Draft · Version {packet.version}</small>
              </span>
              <ArrowUpRight size={17} />
            </button>
          ))}
        </div>
        {!item.packets.length && (
          <div className="empty-state">
            <FileText size={25} />
            <h3>No action packet yet.</h3>
            <p>Packets require risk ≥ 70 and a clear attribution.</p>
          </div>
        )}
        {selected && (
          <>
            <div className="export-buttons">
              <a
                className="button dark"
                href={`/api/v1/packets/${selected.id}?format=pdf`}
                download
              >
                <Download size={16} /> Download PDF
              </a>
              <a
                className="button light"
                href={`/api/v1/packets/${selected.id}?format=json`}
                download
              >
                <FileJson size={16} /> JSON
              </a>
            </div>
            <details className="packet-preview">
              <summary>Inspect the packet</summary>
              <pre>
                {preview ? JSON.stringify(preview, null, 2) : "Loading packet…"}
              </pre>
            </details>
          </>
        )}
        <WorkflowTracker item={item} onUpdate={onUpdate} />
        {item.grievances.length > 0 && (
          <div className="drawer-deadlines">
            <h3>
              <Clock3 size={18} /> On the clock
            </h3>
            {item.grievances.map((grievance) => (
              <div className="deadline-item" key={grievance.id}>
                <div>
                  <b>Food Safety Connect</b>
                  <span>
                    {grievance.status === "resolved"
                      ? "Resolved"
                      : `Day ${grievance.days_elapsed} of 15 · due ${dateLabel(grievance.due_at)}`}
                  </span>
                </div>
                {hostedDemo ? (
                  <span className="demo-badge">SNAPSHOT</span>
                ) : grievance.status !== "resolved" ? (
                  <button
                    className="button light small"
                    onClick={() => resolve(grievance.id)}
                    disabled={busy}
                  >
                    Mark resolved
                  </button>
                ) : (
                  <CheckCircle2 className="green" size={18} />
                )}
              </div>
            ))}
            <small className="muted">
              48-hour priority is an internal target. Authority queries start
              their own 24-hour clock when received.
            </small>
          </div>
        )}
        {error && (
          <div className="error-box" role="alert">
            {error}
          </div>
        )}
      </div>
    </dialog>
  );
}
