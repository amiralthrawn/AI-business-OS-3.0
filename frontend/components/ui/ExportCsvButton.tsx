"use client";

type CsvCell = string | number | null;

function toCsv(headers: string[], rows: CsvCell[][]): string {
  const escape = (v: CsvCell) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers, ...rows].map((row) => row.map(escape).join(";"));
  return lines.join("\r\n");
}

// A real, downloadable CSV built client-side from data already on the page
// -- no backend export endpoint needed for this. Uses ";" as the separator
// (Excel FR's default) and a BOM so accents render correctly.
//
// Takes plain `headers`/`rows` data (never a per-column extractor function):
// the page that renders this is a Server Component, and a function cannot
// cross the server -> client boundary as a prop, only serializable data can
// -- so the caller computes each row's cell values itself (Server Components
// can run arbitrary JS, just never hand a closure to a Client Component) and
// this component's only job is turning that data into a CSV download.
export default function ExportCsvButton({ headers, rows, filename }: { headers: string[]; rows: CsvCell[][]; filename: string }) {
  function download() {
    const csv = "﻿" + toCsv(headers, rows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <button
      type="button"
      onClick={download}
      disabled={rows.length === 0}
      className="inline-flex items-center gap-2 rounded-xl border-[1.5px] border-border-strong px-3.5 py-2 text-[13px] font-semibold text-text hover:border-text-faint disabled:opacity-40"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
      </svg>
      Exporter CSV
    </button>
  );
}
