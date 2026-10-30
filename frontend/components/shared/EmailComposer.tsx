"use client";

import { useState } from "react";
import Button from "@/components/ui/Button";

interface EmailComposerProps {
  to: string;
  toName: string;
  defaultSubject: string;
  defaultBody: string;
}

// "Préparer un email" (Step 27) -- composes a real mailto: link from real
// contact data and lets the user copy the text, but NEVER sends anything
// itself: there is no email account connected in this MVP, so pretending to
// send would be exactly the kind of simulated action the product must never
// claim. Opens as an inline panel rather than a separate route so it stays
// attached to the contact it was prepared for.
export default function EmailComposer({ to, toName, defaultSubject, defaultBody }: EmailComposerProps) {
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState(defaultSubject);
  const [body, setBody] = useState(defaultBody);
  const [copied, setCopied] = useState(false);

  const mailtoHref = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(`À : ${to}\nObjet : ${subject}\n\n${body}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API unavailable -- the text is still selectable/visible, so this is a soft failure.
    }
  }

  if (!open) {
    return (
      <Button variant="ghost" onClick={() => setOpen(true)}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 4h16v16H4z" /><path d="m22 6-10 7L2 6" />
        </svg>
        Préparer un email
      </Button>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-surface-alt p-5">
      <div className="flex items-center justify-between">
        <p className="text-[12px] font-semibold uppercase tracking-wide text-text-faint">Préparer un email — {toName}</p>
        <button type="button" onClick={() => setOpen(false)} className="text-text-faint hover:text-text" aria-label="Fermer">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div className="mt-3.5 space-y-3">
        <div>
          <label className="mb-1 block text-[11.5px] font-medium text-text-faint">Destinataire</label>
          <p className="text-[13.5px] text-text">{to}</p>
        </div>
        <div>
          <label className="mb-1 block text-[11.5px] font-medium text-text-faint">Objet</label>
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full rounded-lg border-[1.5px] border-border-strong px-3 py-2 text-[13.5px] outline-none focus:border-accent"
          />
        </div>
        <div>
          <label className="mb-1 block text-[11.5px] font-medium text-text-faint">Message</label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={5}
            className="w-full resize-none rounded-lg border-[1.5px] border-border-strong px-3 py-2 text-[13.5px] outline-none focus:border-accent"
          />
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2.5">
        <Button variant="ghost" onClick={copy}>
          {copied ? "Copié" : "Copier"}
        </Button>
        <a href={mailtoHref}>
          <Button variant="primary">Ouvrir dans mon application email</Button>
        </a>
      </div>
      <p className="mt-2.5 text-[11px] text-text-faint">Rien n&rsquo;est envoyé depuis AI Business OS — ceci prépare le message pour votre propre messagerie.</p>
    </div>
  );
}
