import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// V3: every product page needs a signed-in session (the `aibos_session`
// cookie, lib/api.ts). Without one, go to the sign-in page and come back after.
// The token itself is verified by the backend on every API call; this only
// avoids rendering pages that would all answer "please sign in".
// NEXT_PUBLIC_AUTH_MODE=legacy (the bundled demo) keeps the V2 open access.
const PUBLIC_PATHS = ["/login", "/signup", "/invitation"];

export function proxy(request: NextRequest) {
  if (process.env.NEXT_PUBLIC_AUTH_MODE === "legacy") return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return NextResponse.next();
  if (request.cookies.get("aibos_session")?.value) return NextResponse.next();
  const login = new URL("/login", request.url);
  login.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
