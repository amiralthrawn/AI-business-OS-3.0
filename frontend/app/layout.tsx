import type { Metadata } from "next";
// Fonts are bundled with the app (no download from Google at build time),
// so the product starts the same way with or without internet access.
import "@fontsource-variable/fraunces/wght.css";
import "@fontsource-variable/fraunces/wght-italic.css";
import "@fontsource-variable/plus-jakarta-sans/wght.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";
// Registers the server-side profile resolver used by lib/api.ts (V2 roles).
import "@/lib/server-user";

export const metadata: Metadata = {
  title: "AI Business OS",
  description: "Système d'exploitation d'entreprise piloté par l'IA",
};

// Deliberately minimal: fonts and the html/body shell only. The Sidebar/
// Topbar chrome lives in app/(app)/layout.tsx so that routes outside that
// group -- Onboarding -- render full-screen, with no product chrome around
// a setup wizard the user hasn't gone through yet.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="fr"
      className="h-full antialiased"
    >
      <body className="min-h-full bg-bg text-text">{children}</body>
    </html>
  );
}
