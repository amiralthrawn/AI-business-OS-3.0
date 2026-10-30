"use client";

import { useMemo, useState } from "react";
import type { CatalogCategory, CatalogTool } from "@/lib/types-config";

// Every tool the company runs on, by family (ERP, CRM, compta, banque, BI,
// tableurs, bases de données…). What is ticked drives the integration plan
// and what the AI knows about how this company works.
export default function ToolsPicker({
  tools,
  categories,
  selected,
  customTools,
  onChange,
  onCustomChange,
}: {
  tools: CatalogTool[];
  categories: CatalogCategory[];
  selected: string[];
  customTools: string[];
  onChange: (keys: string[]) => void;
  onCustomChange: (names: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");

  const sections = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return categories
      .map((c) => ({ category: c, items: tools.filter((t) => t.category === c.key && (!needle || t.label.toLowerCase().includes(needle) || c.label.toLowerCase().includes(needle))) }))
      .filter((s) => s.items.length > 0);
  }, [tools, categories, query]);

  function toggle(key: string) {
    onChange(selected.includes(key) ? selected.filter((k) => k !== key) : [...selected, key]);
  }

  function addCustom() {
    const name = draft.trim();
    if (!name || customTools.includes(name)) return;
    onCustomChange([...customTools, name]);
    setDraft("");
  }

  return (
    <div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Rechercher un outil (ex. Sage, Salesforce, Qonto, Power BI…)"
        aria-label="Rechercher un outil"
        className="w-full rounded-xl border-[1.5px] border-border-strong px-4 py-3 text-[14.5px] outline-none focus:border-accent"
      />
      <p className="mt-2 text-[12px] text-text-faint">
        {selected.length + customTools.length} outil{selected.length + customTools.length > 1 ? "s" : ""} sélectionné{selected.length + customTools.length > 1 ? "s" : ""}
      </p>
      <div className="mt-3 max-h-[380px] space-y-5 overflow-y-auto rounded-xl border border-border p-3">
        {sections.length === 0 && <p className="px-1 py-2 text-[13px] text-text-faint">Aucun outil ne correspond : ajoutez-le ci-dessous avec son nom.</p>}
        {sections.map(({ category, items }) => (
          <div key={category.key}>
            <p className="mb-1.5 px-1 text-[11px] font-bold uppercase tracking-wide text-text-faint">{category.label}</p>
            <div className="flex flex-wrap gap-2">
              {items.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  aria-pressed={selected.includes(t.key)}
                  onClick={() => toggle(t.key)}
                  className={`rounded-xl border-[1.5px] px-3 py-2 text-[13px] font-medium transition-colors ${
                    selected.includes(t.key) ? "border-accent bg-accent-soft font-semibold text-accent-strong" : "border-border-strong text-text-soft hover:border-text-faint"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4">
        <label className="mb-1.5 block text-[13px] font-semibold text-text">Un outil qui n&rsquo;est pas dans la liste&nbsp;?</label>
        <div className="flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCustom();
              }
            }}
            placeholder="Nom de l'outil ou du logiciel"
            className="min-w-0 flex-1 rounded-xl border-[1.5px] border-border-strong px-4 py-2.5 text-[14px] outline-none focus:border-accent"
          />
          <button type="button" onClick={addCustom} disabled={!draft.trim()} className="rounded-xl border-[1.5px] border-border-strong px-4 text-[13px] font-semibold text-text-soft hover:border-accent disabled:opacity-40">
            Ajouter
          </button>
        </div>
        {customTools.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-2">
            {customTools.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => onCustomChange(customTools.filter((n) => n !== name))}
                title="Retirer"
                className="rounded-xl border-[1.5px] border-accent bg-accent-soft px-3 py-2 text-[13px] font-semibold text-accent-strong"
              >
                {name} ×
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
