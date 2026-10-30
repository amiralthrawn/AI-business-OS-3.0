"use client";

import Link from "next/link";
import { useState } from "react";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Chip from "@/components/ui/Chip";
import Toggle from "@/components/ui/Toggle";
import { updateBusinessContext, updateCompany } from "@/lib/api";
import type { BusinessContextRead, CompanyRead, ConfigurationSuggestionRead } from "@/lib/types";

type SaveStatus = "idle" | "saving" | "saved" | "error";

const SIZE_OPTIONS = ["1–10", "11–50", "51–200", "200+"];
const COUNTRY_OPTIONS = [
  { code: "FR", label: "France" },
  { code: "DE", label: "Allemagne" },
  { code: "BE", label: "Belgique" },
  { code: "CH", label: "Suisse" },
];
const DOMAIN_OPTIONS = [
  { value: "finance", label: "Finance", enabled: true },
  { value: "procurement", label: "Achats / Procurement", enabled: true },
  { value: "sales", label: "Ventes", enabled: true },
  { value: "hr", label: "Ressources humaines", enabled: false },
  { value: "marketing", label: "Marketing", enabled: false },
  { value: "supply_chain", label: "Supply Chain", enabled: false },
];
const FOCUS_OPTIONS = [
  { value: "priorities", label: "Priorités IA" },
  { value: "risks", label: "Risques" },
  { value: "opportunities", label: "Opportunités" },
  { value: "decisions", label: "Décisions" },
  { value: "actions", label: "Actions" },
];
const NOTIFICATION_OPTIONS = [
  { value: "low", label: "Faible" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "Élevé" },
];
const SYSTEMS = [
  { key: "erp", label: "ERP" },
  { key: "crm", label: "CRM" },
  { key: "accounting", label: "Comptabilité" },
  { key: "ecommerce", label: "E-commerce" },
  { key: "hr", label: "RH / Paie" },
] as const;

function SaveButton({ status, onClick }: { status: SaveStatus; onClick: () => void }) {
  return (
    <div className="flex items-center gap-2.5">
      {status === "error" && <span className="text-[12.5px] text-danger">Échec de l&rsquo;enregistrement.</span>}
      {status === "saved" && <Badge label="Enregistré" tone="success" />}
      <Button onClick={onClick} loading={status === "saving"}>
        Enregistrer
      </Button>
    </div>
  );
}

function readSystemsFromStorage(): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem("aibos_systems") ?? "{}");
  } catch {
    return {};
  }
}

export default function SettingsForm({
  company,
  context,
  suggestions,
}: {
  company: CompanyRead;
  context: BusinessContextRead;
  suggestions: ConfigurationSuggestionRead[];
}) {
  // Section 1 -- Profil
  const [name, setName] = useState(company.name);
  const [industry, setIndustry] = useState(company.industry ?? "");
  const [size, setSize] = useState(context.company_size ?? "11–50");
  const [country, setCountry] = useState(context.country ?? "FR");
  const [profileStatus, setProfileStatus] = useState<SaveStatus>("idle");

  // Section 2 -- Domaines
  const [domains, setDomains] = useState(context.monitored_domains);
  const [domainsStatus, setDomainsStatus] = useState<SaveStatus>("idle");

  // Section 3 -- Priorités du Centre de contrôle
  const [focus, setFocus] = useState(context.home_focus);
  const [focusStatus, setFocusStatus] = useState<SaveStatus>("idle");

  // Section 4 -- Objectifs
  const [objectives, setObjectives] = useState(context.stated_objectives ?? "");
  const [objectivesStatus, setObjectivesStatus] = useState<SaveStatus>("idle");

  // Section 5 -- Notifications
  const [notificationLevel, setNotificationLevel] = useState(context.notification_level);
  const [notificationStatus, setNotificationStatus] = useState<SaveStatus>("idle");

  // Section 7 -- Systèmes (frontend-only)
  const [systems, setSystems] = useState<Record<string, boolean>>(() => readSystemsFromStorage());

  function flash(setStatus: (s: SaveStatus) => void, ok: boolean) {
    setStatus(ok ? "saved" : "error");
    if (ok) setTimeout(() => setStatus("idle"), 2200);
  }

  async function saveProfile() {
    setProfileStatus("saving");
    try {
      await Promise.all([
        updateCompany({ name: name.trim(), industry: industry.trim() || undefined }),
        updateBusinessContext({ company_size: size, country }),
      ]);
      flash(setProfileStatus, true);
    } catch {
      flash(setProfileStatus, false);
    }
  }

  async function saveDomains() {
    setDomainsStatus("saving");
    try {
      await updateBusinessContext({ monitored_domains: domains });
      flash(setDomainsStatus, true);
    } catch {
      flash(setDomainsStatus, false);
    }
  }

  async function saveFocus() {
    setFocusStatus("saving");
    try {
      await updateBusinessContext({ home_focus: focus });
      flash(setFocusStatus, true);
    } catch {
      flash(setFocusStatus, false);
    }
  }

  async function saveObjectives() {
    setObjectivesStatus("saving");
    try {
      await updateBusinessContext({ stated_objectives: objectives.trim() });
      flash(setObjectivesStatus, true);
    } catch {
      flash(setObjectivesStatus, false);
    }
  }

  async function saveNotificationLevel(level: string) {
    setNotificationLevel(level);
    setNotificationStatus("saving");
    try {
      await updateBusinessContext({ notification_level: level });
      flash(setNotificationStatus, true);
    } catch {
      flash(setNotificationStatus, false);
    }
  }

  function toggleSystem(key: string) {
    setSystems((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        localStorage.setItem("aibos_systems", JSON.stringify(next));
      } catch {
        // Frontend-only preference -- fine to lose silently if storage is unavailable.
      }
      return next;
    });
  }

  return (
    <div className="max-w-3xl space-y-8">
      {suggestions.length > 0 && (
        <Card className="border-accent-soft bg-accent-soft/40 p-6">
          <span className="text-[11.5px] font-bold tracking-wide text-accent-strong uppercase">Suggestion de l&rsquo;IA</span>
          {suggestions.map((s, i) => (
            <div key={i} className="mt-2.5">
              <p className="text-[13.5px] text-text">{s.reason}</p>
              <Button
                variant="ghost"
                className="mt-3"
                onClick={() => s.field === "notification_level" && saveNotificationLevel(String(s.suggested_value))}
              >
                Appliquer
              </Button>
            </div>
          ))}
        </Card>
      )}

      <Card className="p-7">
        <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Profil de l&rsquo;entreprise</span>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-[12.5px] font-semibold text-text-soft">Nom de l&rsquo;entreprise</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-xl border-[1.5px] border-border-strong px-3.5 py-2.5 text-[14px] outline-none focus:border-accent" />
          </div>
          <div>
            <label className="mb-2 block text-[12.5px] font-semibold text-text-soft">Secteur d&rsquo;activité</label>
            <input value={industry} onChange={(e) => setIndustry(e.target.value)} className="w-full rounded-xl border-[1.5px] border-border-strong px-3.5 py-2.5 text-[14px] outline-none focus:border-accent" />
          </div>
          <div>
            <label className="mb-2 block text-[12.5px] font-semibold text-text-soft">Taille de l&rsquo;entreprise</label>
            <div className="flex flex-wrap gap-2">
              {SIZE_OPTIONS.map((opt) => (
                <Chip key={opt} label={opt} selected={size === opt} onClick={() => setSize(opt)} />
              ))}
            </div>
          </div>
          <div>
            <label className="mb-2 block text-[12.5px] font-semibold text-text-soft">Pays</label>
            <div className="flex flex-wrap gap-2">
              {COUNTRY_OPTIONS.map((opt) => (
                <Chip key={opt.code} label={opt.label} selected={country === opt.code} onClick={() => setCountry(opt.code)} />
              ))}
            </div>
          </div>
        </div>
        <div className="mt-6 flex justify-end">
          <SaveButton status={profileStatus} onClick={saveProfile} />
        </div>
      </Card>

      <Card className="p-7">
        <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Domaines surveillés par l&rsquo;IA</span>
        <p className="mt-2 text-[12.5px] text-text-faint">Ces domaines déterminent où l&rsquo;Intelligence recherche activement des risques et opportunités.</p>
        <div className="mt-4 flex flex-wrap gap-2.5">
          {DOMAIN_OPTIONS.map((opt) => (
            <Chip
              key={opt.value}
              label={opt.label}
              selected={domains.includes(opt.value)}
              onClick={opt.enabled ? () => setDomains((d) => (d.includes(opt.value) ? d.filter((x) => x !== opt.value) : [...d, opt.value])) : undefined}
            />
          ))}
        </div>
        <div className="mt-6 flex justify-end">
          <SaveButton status={domainsStatus} onClick={saveDomains} />
        </div>
      </Card>

      <Card className="p-7">
        <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Priorités du Centre de contrôle</span>
        <p className="mt-2 text-[12.5px] text-text-faint">Ce qui doit être mis en avant en premier lorsque vous ouvrez AI Business OS.</p>
        <div className="mt-4 flex flex-wrap gap-2.5">
          {FOCUS_OPTIONS.map((opt) => (
            <Chip
              key={opt.value}
              label={opt.label}
              selected={focus.includes(opt.value)}
              onClick={() => setFocus((f) => (f.includes(opt.value) ? f.filter((x) => x !== opt.value) : [...f, opt.value]))}
            />
          ))}
        </div>
        <div className="mt-6 flex justify-end">
          <SaveButton status={focusStatus} onClick={saveFocus} />
        </div>
      </Card>

      <Card className="p-7">
        <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Objectifs déclarés</span>
        <textarea
          value={objectives}
          onChange={(e) => setObjectives(e.target.value)}
          rows={3}
          placeholder="ex. Protéger la marge sur nos produits clés et réduire la dépendance à un fournisseur unique."
          className="mt-4 w-full resize-none rounded-xl border-[1.5px] border-border-strong px-4 py-3 text-[13.5px] outline-none focus:border-accent"
        />
        <p className="mt-2 text-[12px] text-text-faint">Cet objectif oriente les recommandations de l&rsquo;IA et la priorisation du Centre de contrôle.</p>
        <div className="mt-4 flex justify-end">
          <SaveButton status={objectivesStatus} onClick={saveObjectives} />
        </div>
      </Card>

      <Card className="p-7">
        <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Notifications</span>
        <div className="mt-4 flex items-center justify-between">
          <div>
            <p className="text-[13.5px] font-semibold text-text">Niveau de notification</p>
            <p className="mt-0.5 text-[12px] text-text-faint">Fréquence des alertes envoyées pour les nouveaux signaux.</p>
          </div>
          <div className="flex items-center gap-2">
            {notificationStatus === "saving" && <span className="text-[11.5px] text-text-faint">Enregistrement…</span>}
            {notificationStatus === "saved" && <Badge label="Enregistré" tone="success" />}
            <div className="flex gap-2">
              {NOTIFICATION_OPTIONS.map((opt) => (
                <Chip key={opt.value} label={opt.label} selected={notificationLevel === opt.value} onClick={() => saveNotificationLevel(opt.value)} />
              ))}
            </div>
          </div>
        </div>
      </Card>

      <Card className="p-7">
        <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Devise</span>
        <div className="mt-4 flex items-center justify-between rounded-xl border border-border px-4 py-3.5">
          <span className="text-[13px] text-text-soft">Devise utilisée dans vos données</span>
          <Badge label="EUR — Euro" tone="neutral" />
        </div>
        <p className="mt-2.5 text-[12px] text-text-faint">La prise en charge d&rsquo;autres devises n&rsquo;est pas encore disponible.</p>
      </Card>

      <Card className="p-7">
        <div className="flex items-center justify-between">
          <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Systèmes connectés</span>
          <Badge label="Configuration seulement — aucune intégration active" tone="neutral" />
        </div>
        <div className="mt-4 divide-y divide-border">
          {SYSTEMS.map((sys) => (
            <div key={sys.key} className="flex items-center justify-between py-3.5">
              <div className="flex items-center gap-3">
                <div className={`flex h-9 w-9 items-center justify-center rounded-[10px] ${systems[sys.key] ? "bg-accent-soft text-accent-strong" : "bg-surface-sunken text-text-faint"}`}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="4" width="18" height="16" rx="2" /><line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                </div>
                <div>
                  <p className="text-[13.5px] font-semibold text-text">{sys.label}</p>
                  <p className="text-[11.5px] text-text-faint">{systems[sys.key] ? "Signalé — connexion à venir" : "Non connecté"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button type="button" disabled className="cursor-not-allowed rounded-lg border-[1.5px] border-border px-3 py-1.5 text-[12px] font-semibold text-text-faint">
                  Bientôt disponible
                </button>
                <Toggle on={!!systems[sys.key]} onChange={() => toggleSystem(sys.key)} label={sys.label} />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {context.learned_notes.length > 0 && (
        <Card className="p-7">
          <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Notes apprises par l&rsquo;IA</span>
          <ul className="mt-4 space-y-2">
            {context.learned_notes.map((note, i) => (
              <li key={i} className="rounded-xl bg-surface-sunken px-4 py-2.5 text-[13px] text-text-soft">
                {note}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="flex justify-center pb-4">
        <Link href="/onboarding" className="text-[13px] font-medium text-text-soft hover:text-text">
          Relancer la configuration initiale
        </Link>
      </div>
    </div>
  );
}
