import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE } from "@/lib/api-types";

/** Optimistic redirect for signed-out visitors. The real check is server-side against the API. */
export function proxy(request: NextRequest) {
  if (!request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/home/:path*", "/advisor/:path*", "/questionnaire/:path*", "/estimate/:path*", "/timeline/:path*", "/documents/:path*"],
};
