"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { type BrowserStatus, browserCall } from "@/lib/api";

// On the decisions page: when the AI browser is working, or needs the person
// (login, code), say so right here.
export default function BrowserNotice() {
  const [active, setActive] = useState<BrowserStatus["active"]>(null);
  useEffect(() => {
    let live = true;
    const tick = () => browserCall<BrowserStatus>("/status").then((s) => live && setActive(s.active)).catch(() => undefined);
    void tick();
    const t = setInterval(() => void tick(), 5000);
    return () => { live = false; clearInterval(t); };
  }, []);
  if (!active) return null;
  const needs = active.status === "needs_human";
  return (
    <Link href="/agents" className={`block rounded-[20px] border p-5 shadow-card ${needs ? "border-warning bg-warning-soft" : "border-border bg-surface"}`}>
      <p className="text-[14px] font-semibold text-text">{needs ? "L'IA a besoin de vous dans le navigateur" : active.status === "human" ? "Vous avez la main dans le navigateur" : "L'IA travaille dans le navigateur"}</p>
      <p className="mt-1 text-[13px] text-text-soft">{needs ? active.reason : active.goal}</p>
      <p className="mt-2 text-[12.5px] font-semibold text-accent-strong">{needs ? "Ouvrir pour vous identifier →" : "Suivre en direct →"}</p>
    </Link>
  );
}
