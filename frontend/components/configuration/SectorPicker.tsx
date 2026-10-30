"use client";

import { useMemo, useState } from "react";
import type { CatalogSector } from "@/lib/types-config";

const OTHER = "autre";

// Searchable, grouped sector choice. "Autre" opens a free-text field: the AI
// works from the company's own words when no listed sector fits.
export default function SectorPicker({
  sectors,
  sectorKey,
  custom,
  onChange,
}: {
  sectors: CatalogSector[];
  sectorKey: string;
  custom: string;
  onChange: (sectorKey: string, custom: string) => void;
}) {
  const [query, setQuery] = useState("");
  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = sectors.filter((s) => !needle || s.label.toLowerCase().includes(needle) || s.group_label.toLowerCase().includes(needle));
    const byGroup = new Map<string, CatalogSector[]>();
    for (const s of filtered) byGroup.set(s.group_label, [...(byGroup.get(s.group_label) ?? []), s]);
    return [...byGroup.entries()];
  }, [sectors, query]);

  return (
    <div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Rechercher un secteur (ex. négoce, hôtel, SaaS, BTP…)"
        aria-label="Rechercher un secteur"
        className="w-full rounded-xl border-[1.5px] border-border-strong px-4 py-3 text-[14.5px] outline-none focus:border-accent"
      />
      <div className="mt-3 max-h-[300px] space-y-4 overflow-y-auto rounded-xl border border-border p-3">
        {groups.length === 0 && <p className="px-1 py-2 text-[13px] text-text-faint">Aucun secteur ne correspond : choisissez « Autre » et décrivez votre activité.</p>}
        {groups.map(([label, items]) => (
          <div key={label}>
            <p className="mb-1.5 px-1 text-[11px] font-bold uppercase tracking-wide text-text-faint">{label}</p>
            <div className="flex flex-wrap gap-2">
              {items.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  aria-pressed={sectorKey === s.key}
                  onClick={() => onChange(s.key, s.key === OTHER ? custom : "")}
                  className={`rounded-xl border-[1.5px] px-3 py-2 text-left text-[13px] font-medium transition-colors ${
                    sectorKey === s.key ? "border-accent bg-accent-soft font-semibold text-accent-strong" : "border-border-strong text-text-soft hover:border-text-faint"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      {sectorKey === OTHER && (
        <input
          value={custom}
          onChange={(e) => onChange(OTHER, e.target.value)}
          placeholder="Décrivez votre activité en quelques mots"
          aria-label="Votre activité"
          className="mt-3 w-full rounded-xl border-[1.5px] border-border-strong px-4 py-3 text-[14.5px] outline-none focus:border-accent"
        />
      )}
    </div>
  );
}
