"use client";

import Link from "next/link";
import { useState } from "react";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Chip from "@/components/ui/Chip";
import ConfigurationPanel from "@/components/configuration/ConfigurationPanel";
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

export default function SettingsForm({
  company,
  context,
  suggestions,
  canEdit,
}: {
  company: CompanyRead;
  context: BusinessContextRead;
  suggestions: ConfigurationSuggestionRead[];
  canEdit: boolean;
}) {
  // Section 1 -- Profil
  const [name, setName] = useState(company.name);
  const [size, setSize] = useState(context.company_size ?? "11–50");
  const [country, setCountry] = useState(context.country ?? "FR");
  const [profileStatus, setProfileStatus] = useState<SaveStatus>("idle");

  // Section 3 -- Priorités du Centre de contrôle
  const [focus, setFocus] = useState(context.home_focus);
  const [focusStatus, setFocusStatus] = useState<SaveStatus>("idle");

  // Section 4 -- Objectifs
  const [objectives, setObjectives] = useState(context.stated_objectives ?? "");
  const [objectivesStatus, setObjectivesStatus] = useState<SaveStatus>("idle");

  // Section 5 -- Notifications
  const [notificationLevel, setNotificationLevel] = useState(context.notification_level);
  const [notificationStatus, setNotificationStatus] = useState<SaveStatus>("idle");

  function flash(setStatus: (s: SaveStatus) => void, ok: boolean) {
    setStatus(ok ? "saved" : "error");
    if (ok) setTimeout(() => setStatus("idle"), 2200);
  }

  async function saveProfile() {
    setProfileStatus("saving");
    try {
      await Promise.all([
        updateCompany({ name: name.trim() }),
        updateBusinessContext({ company_size: size, country }),
      ]);
      flash(setProfileStatus, true);
    } catch {
      flash(setProfileStatus, false);
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
        <p className="mt-2.5 text-[12px] text-text-faint">Les montants sont affichés en euros.</p>
      </Card>

      <ConfigurationPanel canEdit={canEdit} />

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
