import { NextRequest } from "next/server";
import { operatorAccess } from "@/lib/operator-auth";
const ALLOWED = new Set([
  "telemetry",
  "cases",
  "scans",
  "packets",
  "grievances",
  "regulatory",
  "audio",
  "reference-cases",
  "source-findings",
]);
async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const denial = operatorAccess(request.headers.get("authorization"));
  if (denial)
    return Response.json({ detail: denial.message }, { status: denial.status });
  const { path } = await context.params;
  if (process.env.HOSTED_DEMO === "true") {
    const { serveHostedDemo } = await import("@/lib/demo-api");
    return serveHostedDemo(request, path);
  }
  if (
    !ALLOWED.has(path[0]) ||
    path.some(
      (part) => part === ".." || part.includes("/") || part.includes("\\"),
    )
  )
    return Response.json({ detail: "Unknown endpoint" }, { status: 404 });
  if (!["GET", "HEAD"].includes(request.method)) {
    const origin = request.headers.get("origin");
    if (
      origin &&
      origin !== request.nextUrl.origin &&
      new URL(origin).host !== request.headers.get("host")
    )
      return Response.json(
        { detail: "Cross-origin writes are disabled" },
        { status: 403 },
      );
    const length = Number(request.headers.get("content-length") || 0);
    if (length > 11_000_000)
      return Response.json(
        { detail: "Request exceeds upload limit" },
        { status: 413 },
      );
  }
  const base =
    process.env.API_BASE_URL ||
    (process.env.API_HOST
      ? `http://${process.env.API_HOST}:${process.env.API_PORT || "8000"}`
      : "http://127.0.0.1:8000");
  const headers: Record<string, string> = {};
  for (const name of ["content-type", "idempotency-key"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  if (process.env.INTERNAL_API_KEY)
    headers.authorization = `Bearer ${process.env.INTERNAL_API_KEY}`;
  try {
    const response = await fetch(
      `${base}/api/v1/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body: ["GET", "HEAD"].includes(request.method)
          ? undefined
          : await request.arrayBuffer(),
        cache: "no-store",
        signal: AbortSignal.timeout(45_000),
        redirect: "error",
      },
    );
    const outgoing = new Headers({
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    });
    for (const name of ["content-type", "content-disposition"]) {
      const value = response.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return Response.json(
      { detail: "The API is unavailable. Start the backend and try again." },
      { status: 503 },
    );
  }
}
export { forward as GET, forward as POST, forward as PATCH };
