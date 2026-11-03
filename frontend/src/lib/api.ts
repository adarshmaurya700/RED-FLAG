export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = typeof payload.detail === "string" ? payload.detail : message;
    } catch {}
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export const vectorNames = {
  batch: "Factory batch",
  counterfeit: "Counterfeit",
  dark_store: "Dark store",
  review: "Needs review",
};
export const vectorColors = {
  batch: "#D93025",
  counterfeit: "#FA903E",
  dark_store: "#12B5CB",
  review: "#8b85a5",
};
export function dateLabel(value: string) {
  return new Date(value).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  });
}
export function timeAgo(value: string) {
  const hours = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 3600000),
  );
  return hours < 1
    ? "Just now"
    : hours < 24
      ? `${hours}h ago`
      : `${Math.floor(hours / 24)}d ago`;
}
