import { NextRequest } from "next/server";
import rawSnapshot from "@/data/demo-snapshot.json";
import rawReports from "@/data/real-cases.json";
import type {
  CaseSummary,
  CaseDetail,
  EvidenceResponse,
  GraphData,
  ReferenceCase,
  Telemetry,
} from "./types";

type Snapshot = {
  captured_at: string;
  telemetry: Telemetry;
  cases: CaseSummary[];
  details: Record<string, CaseDetail>;
  evidence: Record<string, EvidenceResponse>;
  graphs: Record<string, GraphData>;
  packets: Record<
    string,
    { json: Record<string, unknown>; pdf_base64: string }
  >;
};
const snapshot = rawSnapshot as unknown as Snapshot;
const reports = rawReports as {
  reviewed_at: string;
  notice: string;
  cases: ReferenceCase[];
};

function reply(value: unknown, status = 200) {
  return Response.json(value, {
    status,
    headers: {
      "Cache-Control": "private, no-store",
      "X-Red-Flag-Mode": "readonly-demo",
    },
  });
}

function matchingReports(query: string) {
  const terms = query
    .toLocaleLowerCase()
    .split(/[^\p{L}\p{M}\p{N}_]+/u)
    .filter(
      (term) =>
        term && !["case", "cases", "the", "report", "reports"].includes(term),
    );
  return reports.cases.filter((item) => {
    const words =
      `${item.brand} ${item.product} ${item.summary} ${item.aliases.join(" ")}`
        .toLocaleLowerCase()
        .split(/[^\p{L}\p{M}\p{N}_]+/u);
    return terms.every((term) => words.includes(term));
  });
}

export async function serveHostedDemo(request: NextRequest, path: string[]) {
  if (!["GET", "HEAD"].includes(request.method))
    return reply(
      {
        detail:
          "This free hosted demo is read-only. Run the local application for live scans and saved workflow changes.",
      },
      405,
    );
  const params = request.nextUrl.searchParams;
  if (path[0] === "source-findings" && path.length === 1) {
    const { searchSourceFindings } = await import("./source-catalog");
    try {
      return reply(await searchSourceFindings(params));
    } catch (error) {
      return reply(
        {
          detail:
            error instanceof RangeError
              ? error.message
              : "Source catalogue unavailable",
        },
        error instanceof RangeError ? 422 : 503,
      );
    }
  }
  if (path[0] === "telemetry" && path.length === 1)
    return reply(snapshot.telemetry);
  if (path[0] === "reference-cases") {
    if (path.length === 1)
      return reply({
        items: matchingReports(params.get("q") || ""),
        reviewed_at: reports.reviewed_at,
        notice: reports.notice,
      });
    const item = reports.cases.find((record) => record.id === path[1]);
    if (item && path.length === 2)
      return reply({
        ...item,
        reviewed_at: reports.reviewed_at,
        notice: reports.notice,
      });
  }
  if (path[0] === "cases") {
    if (path.length === 1) {
      const mode = params.get("mode") || "all";
      const vector = params.get("vector") || "all";
      const query = (params.get("q") || "").toLocaleLowerCase();
      return reply(
        snapshot.cases.filter(
          (item) =>
            mode !== "live" &&
            (vector === "all" || vector === item.dominant_vector) &&
            `${item.title} ${item.product_name} ${item.brand_name}`
              .toLocaleLowerCase()
              .includes(query),
        ),
      );
    }
    const item = Object.hasOwn(snapshot.details, path[1])
      ? snapshot.details[path[1]]
      : undefined;
    if (item && path.length === 2) return reply(item);
    if (item && path.length === 3 && path[2] === "graph")
      return reply(snapshot.graphs[path[1]]);
    if (item && path.length === 3 && path[2] === "evidence") {
      const data = snapshot.evidence[path[1]];
      const platform = params.get("platform") || "all";
      const kind = params.get("kind") || "all";
      const query = (params.get("q") || "").toLocaleLowerCase();
      const offset = Number(params.get("offset") || 0),
        limit = Number(params.get("limit") || 30);
      if (
        !Number.isInteger(offset) ||
        offset < 0 ||
        !Number.isInteger(limit) ||
        limit < 1 ||
        limit > 100
      )
        return reply({ detail: "Invalid evidence pagination" }, 422);
      const items = data.items.filter(
        (signal) =>
          (platform === "all" || platform === signal.platform) &&
          (kind === "all" || kind === signal.evidence_type) &&
          signal.text.toLocaleLowerCase().includes(query),
      );
      return reply({
        items: items.slice(offset, offset + limit),
        total: items.length,
        platforms: data.platforms,
      });
    }
  }
  if (path[0] === "packets" && path.length === 2) {
    const packet = Object.hasOwn(snapshot.packets, path[1])
      ? snapshot.packets[path[1]]
      : undefined;
    if (packet) {
      if ((params.get("format") || "json") === "json")
        return reply(packet.json);
      if (params.get("format") === "pdf")
        return new Response(
          new Uint8Array(Buffer.from(packet.pdf_base64, "base64")),
          {
            headers: {
              "Content-Type": "application/pdf",
              "Content-Disposition": `attachment; filename="red-flag-${String(packet.json.case_id)}-draft.pdf"`,
              "Cache-Control": "private, no-store",
            },
          },
        );
      return reply({ detail: "Unsupported export format" }, 422);
    }
  }
  return reply({ detail: "No matching record in the hosted demo" }, 404);
}
