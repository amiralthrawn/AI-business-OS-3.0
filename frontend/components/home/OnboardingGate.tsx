"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

// No auth/session in this single-company MVP, so "has this workspace been
// configured" can't be known server-side -- a lightweight, honest
// browser-only signal instead of a fake gate. Never blocks: if the flag is
// already set (or storage is unavailable), nothing happens.
export default function OnboardingGate() {
  const router = useRouter();

  useEffect(() => {
    try {
      if (!localStorage.getItem("aibos_onboarding_done")) {
        router.replace("/onboarding");
      }
    } catch {
      // Storage unavailable (private mode, etc.) -- never block the app over this.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
