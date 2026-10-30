"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AUTH_REQUIRED } from "@/lib/api";

// Sends the person who set up the company to the initial configuration.
// V3 (sign-in required): the server knows -- `needsSetup` is true only for
// someone managing the company while its sector is still undeclared, so an
// invited colleague never lands on it. Legacy demo mode: no session, so a
// lightweight browser-only flag instead. "Passer pour l'instant" sets that
// flag in both modes. Never blocks if storage is unavailable.
export default function OnboardingGate({ needsSetup }: { needsSetup: boolean }) {
  const router = useRouter();

  useEffect(() => {
    try {
      const skipped = !!localStorage.getItem("aibos_onboarding_done");
      if (AUTH_REQUIRED ? needsSetup && !skipped : !skipped) {
        router.replace("/onboarding");
      }
    } catch {
      // Storage unavailable (private mode, etc.) -- never block the app over this.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
