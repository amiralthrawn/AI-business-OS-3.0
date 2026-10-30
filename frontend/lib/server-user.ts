import { cookies } from "next/headers";
import { setServerCookieResolver } from "@/lib/api";

// Server side of the session (see lib/api.ts): Server Components' API calls
// carry the access token (and, in legacy demo mode, the selected profile)
// from the browser's cookies. Imported once, for its side effect, by the root
// layout -- never by a Client Component.
setServerCookieResolver(async (name) => (await cookies()).get(name)?.value ?? null);
