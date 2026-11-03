"use client";
import { useState } from "react";
import { Clock3, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";
function when(value: string) {
  return (
    new Date(value).toLocaleString("en-IN", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Kolkata",
    }) + " IST"
  );
}
function currentIST() {
  return new Date()
    .toLocaleString("sv-SE", { timeZone: "Asia/Kolkata" })
    .replace(" ", "T")
    .slice(0, 16);
}
export default function WorkflowTracker({
  item,
  onUpdate,
}: {
  item: CaseDetail;
  onUpdate: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reference, setReference] = useState("");
  const [received, setReceived] = useState(currentIST);
  const [distributed, setDistributed] = useState(4800);
  const [recovered, setRecovered] = useState(0);
  const [notes, setNotes] = useState("");
  async function send(path: string, body?: unknown, method = "POST") {
    setBusy(true);
    setError("");
    try {
      await api(`/cases/${item.id}/${path}`, {
        method,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      onUpdate();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="workflow-tracker">
      <h3>
        <Clock3 size={17} /> Workflow clocks
      </h3>
      {item.dominant_vector === "batch" && item.risk_score >= 70 && (
        <>
          {item.recall_workflow ? (
            <>
              <div className="workflow-clock">
                <b>Initial authority notification</b>
                <span>
                  Due {when(item.recall_workflow.notification_due_at)}
                </span>
              </div>
              <div className="workflow-clock">
                <b>Weekly recall status</b>
                <span>
                  Next due{" "}
                  {when(item.recall_workflow.next_weekly_status_due_at)}
                </span>
                <small>
                  {item.recall_workflow.reports.length} submission record(s)
                </small>
              </div>
              <details className="workflow-form">
                <summary>Record a weekly report submission</summary>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void send("weekly-status", {
                      submitted_at: new Date().toISOString(),
                      distributed_units: distributed,
                      recovered_units: recovered,
                      effectiveness_notes: notes,
                    });
                  }}
                >
                  <div className="workflow-fields">
                    <label className="field-label">
                      Units distributed
                      <input
                        type="number"
                        min={1}
                        required
                        value={distributed}
                        onChange={(event) =>
                          setDistributed(Number(event.target.value))
                        }
                      />
                    </label>
                    <label className="field-label">
                      Units recovered
                      <input
                        type="number"
                        min={0}
                        max={distributed}
                        required
                        value={recovered}
                        onChange={(event) =>
                          setRecovered(Number(event.target.value))
                        }
                      />
                    </label>
                  </div>
                  <label className="field-label">
                    Effectiveness notes
                    <textarea
                      required
                      maxLength={1500}
                      value={notes}
                      onChange={(event) => setNotes(event.target.value)}
                      placeholder="Record recovery checks and unresolved accounts"
                    />
                  </label>
                  <button className="button light small" disabled={busy}>
                    Record submission
                  </button>
                </form>
              </details>
            </>
          ) : (
            <div className="workflow-start">
              <p>
                Start the initial 24-hour notification and weekly status clocks
                when the recall decision is recorded.
              </p>
              <button
                className="button light small"
                disabled={busy}
                onClick={() =>
                  send("recall-decision", {
                    decision_at: new Date().toISOString(),
                  })
                }
              >
                {item.synthetic
                  ? "Simulate recall decision"
                  : "Record recall decision"}
              </button>
            </div>
          )}
        </>
      )}
      {(item.authority_queries || []).map((query) => (
        <div className="workflow-clock" key={query.id}>
          <b>Authority query · {query.reference}</b>
          <span>
            {query.status === "responded"
              ? "Response recorded"
              : `Due ${when(query.due_at)}`}
          </span>
          {query.status === "open" ? (
            <button
              className="text-button"
              disabled={busy}
              onClick={() =>
                send(
                  `authority-queries/${query.id}/responded`,
                  undefined,
                  "PATCH",
                )
              }
            >
              Mark response recorded
            </button>
          ) : (
            <CheckCircle2 size={13} className="green" />
          )}
        </div>
      ))}
      <details className="workflow-form">
        <summary>Log an authority query</summary>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void send("authority-queries", {
              reference,
              received_at: new Date(received + "+05:30").toISOString(),
            });
          }}
        >
          <label className="field-label">
            Query reference
            <input
              required
              maxLength={120}
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              placeholder="Authority's reference number"
            />
          </label>
          <label className="field-label">
            Received at (IST)
            <input
              type="datetime-local"
              required
              value={received}
              onChange={(event) => setReceived(event.target.value)}
            />
          </label>
          <button className="button light small" disabled={busy}>
            Start query response clock
          </button>
        </form>
      </details>
      <p className="small-text muted">
        Records track operator activity. No notice, response or report is sent
        by this app.
      </p>
      {error && <div className="error-box">{error}</div>}
    </div>
  );
}
