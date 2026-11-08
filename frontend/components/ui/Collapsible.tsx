"use client";

import { useEffect, useState } from "react";

// A section that folds away so a long page stays short. The choice is kept per person.
export default function Collapsible({ id, title, hint, defaultOpen = true, children }: { id: string; title: string; hint?: string; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`aibos_fold_${id}`);
      if (saved !== null) setOpen(saved === "1");
    } catch {
      /* storage unavailable */
    }
  }, [id]);
  function toggle() {
    setOpen((o) => {
      try {
        localStorage.setItem(`aibos_fold_${id}`, o ? "0" : "1");
      } catch {
        /* storage unavailable */
      }
      return !o;
    });
  }
  return (
    <section id={id} className="scroll-mt-16">
      <button type="button" onClick={toggle} aria-expanded={open} className="flex w-full items-center justify-between gap-3 rounded-xl py-1 text-left">
        <span className="text-[11.5px] font-bold uppercase tracking-wide text-text-faint">
          {title}
          {hint && <span className="ml-2 font-semibold normal-case tracking-normal text-text-soft">{hint}</span>}
        </span>
        <span className={`text-[14px] text-text-faint transition-transform ${open ? "rotate-180" : ""}`} aria-hidden>⌄</span>
      </button>
      {open && <div className="mt-3 space-y-5">{children}</div>}
    </section>
  );
}
