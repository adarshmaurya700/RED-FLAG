import { createHash, timingSafeEqual } from "node:crypto";

export function operatorAccess(
  authorization: string | null,
): { status: number; message: string } | null {
  const password = process.env.HOSTED_OPERATOR_PASSWORD;
  if (process.env.APP_ENV === "production" && !password)
    return { status: 503, message: "Operator gateway is not configured" };
  if (!password) return null;
  const expected = `Basic ${Buffer.from(`operator:${password}`).toString("base64")}`;
  const digest = (value: string) => createHash("sha256").update(value).digest();
  return timingSafeEqual(digest(authorization || ""), digest(expected))
    ? null
    : { status: 401, message: "Operator access required" };
}
