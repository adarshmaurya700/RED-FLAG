import { NextRequest, NextResponse } from "next/server";
import { operatorAccess } from "@/lib/operator-auth";
export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname === "/health") return NextResponse.next();
  const denial = operatorAccess(request.headers.get("authorization"));
  if (denial)
    return new NextResponse(denial.message, {
      status: denial.status,
      headers: {
        "WWW-Authenticate": 'Basic realm="red flag operator", charset="UTF-8"',
      },
    });
  return NextResponse.next();
}
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
