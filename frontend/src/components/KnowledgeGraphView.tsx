"use client";
import { useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Network, Factory } from "lucide-react";
import { api } from "@/lib/api";
import type { GraphData } from "@/lib/types";
export default function KnowledgeGraphView({ caseId }: { caseId: string }) {
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    api<GraphData>(`/cases/${caseId}/graph`, { signal: controller.signal })
      .then(setData)
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      });
    return () => controller.abort();
  }, [caseId]);
  if (error) return <div className="error-box">{error}</div>;
  if (!data) return <div className="loading-panel">Connecting the dots…</div>;
  const levels: Record<string, number> = {
    supplier: 0,
    facility: 1,
    product: 2,
    brand: 3,
    case: 4,
  };
  const slots: Record<string, number> = {};
  const nodes: Node[] = data.nodes.map((node) => {
    const slot = slots[node.kind] || 0;
    slots[node.kind] = slot + 1;
    return {
      id: node.id,
      position: { x: (levels[node.kind] ?? 2) * 215, y: slot * 125 },
      data: {
        label: (
          <div className="graph-node-label">
            <small>
              {node.kind === "facility"
                ? "FSSAI MANUFACTURING LICENSE"
                : node.kind.toUpperCase()}
            </small>
            <b>{node.label}</b>
          </div>
        ),
      },
      style: {
        borderRadius: 12,
        background: node.kind === "facility" ? "#fff0e9" : "white",
        border:
          node.kind === "facility" ? "1px solid #f9a995" : "1px solid #deded8",
        width: 190,
        padding: 12,
      },
    };
  });
  const edges: Edge[] = data.edges.map((edge) => ({
    ...edge,
    type: "smoothstep",
    animated: true,
    label: edge.label.replaceAll("_", " "),
    labelStyle: { fontSize: 9, fill: "#777b80" },
    style: { stroke: "#b9b6ae" },
    markerEnd: { type: MarkerType.ArrowClosed, color: "#b9b6ae" },
  }));
  return (
    <div className="graph-panel">
      <div className="section-heading small-heading">
        <div>
          <span className="eyebrow">FOLLOW THE CONNECTIONS</span>
          <h3>Different labels. Shared roots.</h3>
        </div>
        <Network size={22} />
      </div>
      <div
        className="graph-canvas"
        aria-label="Interactive product and manufacturing graph"
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          minZoom={0.25}
          nodesDraggable
          nodesConnectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#dddcd4" gap={20} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      {data.facility_alerts.map((alert) => (
        <div key={alert.license} className="facility-alert">
          <Factory size={18} />
          <div>
            <b>Shared facility · {alert.license}</b>
            <p>{alert.message}</p>
          </div>
        </div>
      ))}
      {!data.nodes.length && (
        <p className="muted">
          No resolved manufacturing connections yet. A product name alone does
          not establish a facility link.
        </p>
      )}
      <p className="graph-footnote">
        Drag to explore · Scroll to zoom · License links require identity
        verification before action.
      </p>
    </div>
  );
}
