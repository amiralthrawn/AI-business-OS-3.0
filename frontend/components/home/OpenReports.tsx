"use client";

export default function OpenReports() {
  return (
    <button type="button" onClick={() => window.dispatchEvent(new Event("aibos:reports"))} className="text-[12.5px] font-semibold text-accent-strong hover:underline">
      Lire les comptes rendus de mes agents →
    </button>
  );
}
