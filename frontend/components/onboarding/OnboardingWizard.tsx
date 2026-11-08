"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import DataImport from "@/components/configuration/DataImport";
import QcmQuestions from "@/components/configuration/QcmQuestions";
import SectorPicker from "@/components/configuration/SectorPicker";
import ToolSyncPage from "@/components/configuration/ToolSyncPage";
import ToolsPicker from "@/components/configuration/ToolsPicker";
import { AUTH_REQUIRED, createUser, getConfigCatalog, getConfiguration, saveConfiguration, setSelectedProfile, updateCompany } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/objects";
import type { BusinessContextRead, CompanyRead, Role } from "@/lib/types";
import type { ConfigCatalog, ConfigurationUpdate } from "@/lib/types-config";

const SIZE_OPTIONS = ["1–10", "11–50", "51–200", "200+"];
const COUNTRY_OPTIONS = [
  { code: "FR", label: "France" },
  { code: "BE", label: "Belgique" },
  { code: "CH", label: "Suisse" },
  { code: "LU", label: "Luxembourg" },
  { code: "DE", label: "Allemagne" },
  { code: "ES", label: "Espagne" },
  { code: "IT", label: "Italie" },
  { code: "PT", label: "Portugal" },
  { code: "NL", label: "Pays-Bas" },
  { code: "GB", label: "Royaume-Uni" },
  { code: "MA", label: "Maroc" },
  { code: "DZ", label: "Algérie" },
  { code: "TN", label: "Tunisie" },
  { code: "SN", label: "Sénégal" },
  { code: "CI", label: "Côte d'Ivoire" },
  { code: "AE", label: "Émirats arabes unis" },
  { code: "US", label: "États-Unis" },
  { code: "CA", label: "Canada" },
];

// V2 roles: the second part of the setup in the legacy demo mode only
// (brain/permissions.md). With sign-in the person already has their role.
const ROLE_OPTIONS: { role: Role; hint: string }[] = [
  { role: "director", hint: "Vue globale, valide toutes les actions" },
  { role: "sales", hint: "Demandes, devis, commandes, relances clients" },
  { role: "procurement", hint: "Demandes d'achat, fournisseurs, commandes" },
  { role: "operations", hint: "Réceptions, livraisons, stock" },
  { role: "hr", hint: "Communications et actions (RH)" },
  { role: "employee", hint: "Consultation et tâches" },
];

// One question per family of tools ("Quel est votre ERP ?"). Clicking a tool
// opens its synchronisation page straight away; the next question follows.
const CATEGORY_QUESTIONS: [string, string][] = [
  ["erp", "Quel est votre ERP ?"],
  ["crm", "Quel est votre CRM ?"],
  ["accounting", "Quel logiciel de comptabilité utilisez-vous ?"],
  ["invoicing", "Avec quel outil facturez-vous ?"],
  ["procurement", "Quel outil utilisez-vous pour vos achats ?"],
  ["ecommerce", "Vendez-vous en ligne ? Sur quelle plateforme ?"],
  ["bank", "Quelle est votre banque ?"],
  ["payment", "Quels outils de paiement en ligne utilisez-vous ?"],
  ["expenses", "Comment gérez-vous vos notes de frais et vos cartes ?"],
  ["stock", "Quel outil gère votre stock et votre logistique ?"],
  ["production", "Quel outil suit votre production et votre qualité ?"],
  ["hr", "Quel outil gère vos RH et votre paie ?"],
  ["messaging", "Quelle messagerie et quels outils d'équipe utilisez-vous ?"],
  ["projects", "Quel outil suit vos projets et vos tâches ?"],
  ["support", "Quel outil gère votre support client ?"],
  ["marketing", "Quels outils utilisez-vous pour votre site et votre marketing ?"],
  ["legal", "Quels outils juridiques ou de signature utilisez-vous ?"],
  ["spreadsheet", "Quels tableurs font tourner votre entreprise ?"],
  ["bi", "Quel outil de reporting ou de BI utilisez-vous ?"],
  ["database", "Quelle base de données ou quel cloud utilisez-vous ?"],
];
const STEPS = ["Entreprise", "Activité", ...CATEGORY_QUESTIONS.map(([k]) => `Cat:${k}`), "Autres outils", "Documents", ...(AUTH_REQUIRED ? [] : ["Votre rôle"]), "Récapitulatif"];

export default function OnboardingWizard({
  initialCompany,
  initialContext,
}: {
  initialCompany: CompanyRead | null;
  initialContext: BusinessContextRead | null;
}) {
  const router = useRouter();
  const [step, setStepRaw] = useState(0);
  const setStep = (v: number | ((s: number) => number)) =>
    setStepRaw((prev) => {
      const n = typeof v === "function" ? v(prev) : v;
      try {
        localStorage.setItem("aibos_onboarding_step", String(n));
      } catch {
        /* storage unavailable */
      }
      return n;
    });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ConfigCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [importRefresh, setImportRefresh] = useState(0);

  const [name, setName] = useState(initialCompany?.name ?? "");
  const [website, setWebsite] = useState(initialCompany?.website_url ?? "");
  const [sectorKey, setSectorKey] = useState("");
  const [sectorCustom, setSectorCustom] = useState("");
  const [userName, setUserName] = useState("");
  const [role, setRole] = useState<Role>("director");
  const [size, setSize] = useState(initialContext?.company_size ?? "11–50");
  const [country, setCountry] = useState(initialContext?.country ?? "FR");
  const [businessModel, setBusinessModel] = useState(initialContext?.business_model ?? "");
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [toolKeys, setToolKeys] = useState<string[]>([]);
  const [customTools, setCustomTools] = useState<string[]>([]);

  // Set when a tool was just clicked: its synchronisation page replaces the question.
  const [syncing, setSyncing] = useState<string | null>(null);

  useEffect(() => {
    // A reload (or a network hiccup at the end of an import) resumes where the person was.
    try {
      const saved = Number(localStorage.getItem("aibos_onboarding_step"));
      if (Number.isInteger(saved) && saved > 0 && saved < STEPS.length) setStepRaw(saved);
    } catch {
      /* storage unavailable */
    }
    getConfigCatalog().then(setCatalog).catch((err) => setCatalogError(err instanceof Error ? err.message : "Catalogue indisponible."));
    getConfiguration()
      .then((c) => {
        const cfg = c.configuration;
        if (cfg.sector_key) setSectorKey(cfg.sector_key);
        if (cfg.sector_custom) setSectorCustom(cfg.sector_custom);
        if (cfg.answers) setAnswers(cfg.answers);
        if (cfg.answer_notes) setNotes(cfg.answer_notes);
        if (cfg.tools) setToolKeys(Object.keys(cfg.tools));
        if (cfg.custom_tools) setCustomTools(cfg.custom_tools);
      })
      .catch(() => undefined);
  }, []);

  const group = catalog?.sectors.find((s) => s.key === sectorKey)?.group;
  const groupInfo = catalog?.groups.find((g) => g.key === group) ?? catalog?.groups.find((g) => g.key === "generic");
  const sectorLabel = sectorKey === "autre" ? sectorCustom.trim() : catalog?.sectors.find((s) => s.key === sectorKey)?.label ?? "";

  function payload(): ConfigurationUpdate {
    return {
      sector_key: sectorKey || undefined,
      sector_custom: sectorCustom,
      tools: toolKeys,
      custom_tools: customTools,
      company_size: size,
      country,
      business_model: businessModel || undefined,
      answers,
      answer_notes: notes,
    };
  }

  async function persist() {
    await Promise.all([updateCompany({ name: name.trim() || undefined, website_url: website.trim() || undefined }), saveConfiguration(payload())]);
  }

  function stepReady(): boolean {
    if (STEPS[step] === "Entreprise") return !!name.trim() && !!sectorKey && (sectorKey !== "autre" || !!sectorCustom.trim());
    return true;
  }

  async function next() {
    setError(null);
    // The tools are saved before the data step so every upload attaches to a declared tool.
    if (STEPS[step] === "Autres outils") {
      setSaving(true);
      try {
        await persist();
        setImportRefresh((n) => n + 1);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Une erreur est survenue lors de l'enregistrement.");
        setSaving(false);
        return;
      }
      setSaving(false);
    }
    setSyncing(null);
    setStep((s) => s + 1);
  }

  async function pickTool(key: string) {
    setError(null);
    try {
      // The tool must be declared before a file is attached to it.
      await saveConfiguration({ ...payload(), tools: toolKeys.includes(key) ? toolKeys : [...toolKeys, key] });
      setSyncing(key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue.");
    }
  }

  async function removeTool(key: string) {
    const rest = toolKeys.filter((k) => k !== key);
    setToolKeys(rest);
    setSyncing(null);
    await saveConfiguration({ ...payload(), tools: rest }).catch(() => undefined);
  }

  async function skipToDocuments() {
    setError(null);
    setSaving(true);
    try {
      await persist();
      setImportRefresh((n) => n + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue lors de l'enregistrement.");
      setSaving(false);
      return;
    }
    setSaving(false);
    setSyncing(null);
    setStep(STEPS.indexOf("Documents"));
  }

  function skipToProduct() {
    { localStorage.setItem("aibos_onboarding_done", "1"); localStorage.removeItem("aibos_onboarding_step"); }
    router.push("/");
  }

  async function finish() {
    setSaving(true);
    setError(null);
    try {
      await persist();
      // Legacy demo mode only: the person and their role -> a profile selected for every API call.
      if (!AUTH_REQUIRED) {
        const profile = await createUser({ name: userName.trim() || "Moi", role });
        setSelectedProfile(profile.id);
      }
      { localStorage.setItem("aibos_onboarding_done", "1"); localStorage.removeItem("aibos_onboarding_step"); }
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue lors de l'enregistrement.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex min-h-full flex-col items-center bg-bg px-3 pb-4 pt-5 sm:px-6 sm:py-10">
      <div className="flex w-full max-w-3xl flex-wrap items-center justify-between gap-x-4 gap-y-2.5 px-1">
        <div className="flex items-center gap-2.5">
          <div className="flex h-[26px] w-[26px] items-center justify-center rounded-lg bg-accent font-display text-[13px] font-semibold text-white">B</div>
          <span className="hidden font-display text-[15px] font-semibold sm:inline">AI Business OS</span>
        </div>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-3 sm:flex-none">
          <span className="h-[7px] min-w-0 flex-1 overflow-hidden rounded-full bg-border-strong sm:w-40 sm:flex-none">
            <span className="block h-full rounded-full bg-accent transition-all" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
          </span>
          <span className="shrink-0 whitespace-nowrap font-mono text-[11.5px] text-text-faint">
            {step + 1} / {STEPS.length}
          </span>
        </div>
      </div>

      <div key={step} className={`animate-reveal mt-5 w-full rounded-[20px] border border-border bg-surface p-5 shadow-card sm:mt-10 sm:p-10 md:p-14 ${STEPS[step]?.startsWith("Cat:") && syncing ? "max-w-[760px]" : "max-w-[640px]"}`}>
        <p className="text-[12.5px] font-semibold uppercase tracking-wide text-accent-strong">Configuration initiale</p>

        {STEPS[step] === "Entreprise" && (
          <>
            <h1 className="mt-3 break-words font-display text-[26px] italic leading-tight sm:text-[32px] md:text-[36px]">
              Faisons connaissance
              <br />
              avec votre entreprise
            </h1>
            <p className="mt-3.5 max-w-lg text-[15px] text-text-soft">
              L&rsquo;IA adapte son vocabulaire, ses indicateurs et ses questions à votre secteur. Vous pourrez tout modifier plus tard dans Configuration.
            </p>

            <div className="mt-9">
              <label className="mb-2 block text-[13px] font-semibold text-text">Nom de l&rsquo;entreprise</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="ex. Acme Négoce"
                className="w-full rounded-xl border-[1.5px] border-border-strong px-4 py-3.5 text-[17px] font-semibold outline-none focus:border-accent"
              />
            </div>

            <div className="mt-7">
              <label className="mb-2 block text-[13px] font-semibold text-text">Site web de l&rsquo;entreprise <span className="font-normal text-text-faint">(facultatif)</span></label>
              <input
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="www.votre-entreprise.fr"
                inputMode="url"
                className="w-full rounded-xl border-[1.5px] border-border-strong px-4 py-3 text-[15px] outline-none focus:border-accent"
              />
              <p className="mt-1.5 text-[12.5px] text-text-faint">L&rsquo;Analyste le lira pour comprendre votre métier. Pas de site ? Vous pourrez nous demander d&rsquo;en créer un.</p>
            </div>

            <div className="mt-7">
              <label className="mb-2 block text-[13px] font-semibold text-text">Secteur d&rsquo;activité</label>
              {catalog ? (
                <SectorPicker sectors={catalog.sectors} sectorKey={sectorKey} custom={sectorCustom} onChange={(k, c) => { setSectorKey(k); setSectorCustom(c); }} />
              ) : (
                <p className="text-[13px] text-text-faint">{catalogError ?? "Chargement des secteurs…"}</p>
              )}
            </div>

            <div className="mt-7">
              <label className="mb-2 block text-[13px] font-semibold text-text">Taille de l&rsquo;entreprise (personnes)</label>
              <div className="flex flex-wrap gap-2.5">
                {SIZE_OPTIONS.map((opt) => (
                  <Chip key={opt} label={opt} selected={size === opt} onClick={() => setSize(opt)} />
                ))}
              </div>
            </div>

            <div className="mt-7">
              <label className="mb-2 block text-[13px] font-semibold text-text">Pays principal</label>
              <div className="flex flex-wrap gap-2">
                {COUNTRY_OPTIONS.map((opt) => (
                  <Chip key={opt.code} label={opt.label} selected={country === opt.code} onClick={() => setCountry(opt.code)} />
                ))}
              </div>
            </div>
          </>
        )}

        {STEPS[step] === "Activité" && (
          <>
            <h1 className="mt-3 break-words font-display text-[26px] italic leading-tight sm:text-[32px] md:text-[36px]">
              Parlons de
              <br />
              votre activité
            </h1>
            <p className="mt-3.5 max-w-lg text-[15px] text-text-soft">
              {sectorLabel ? `Pour ${sectorLabel.toLowerCase()}, voici ce que nous rencontrons le plus souvent. ` : ""}Cochez simplement ce qui vous correspond : pas besoin de rédiger. Cela permet à l&rsquo;IA de comprendre vos enjeux dès le départ.
            </p>

            {groupInfo && groupInfo.business_models.length > 0 && (
              <div className="mt-8">
                <label className="mb-2 block text-[15px] font-semibold text-text">Votre modèle</label>
                <div className="flex flex-wrap gap-2.5">
                  {groupInfo.business_models.map((m) => (
                    <Chip key={m} label={m} selected={businessModel === m} onClick={() => setBusinessModel(businessModel === m ? "" : m)} />
                  ))}
                </div>
              </div>
            )}

            {groupInfo && (
              <div className="mt-9">
                <QcmQuestions questions={groupInfo.qcm} answers={answers} notes={notes} onAnswers={setAnswers} onNotes={setNotes} />
              </div>
            )}
          </>
        )}

        {STEPS[step].startsWith("Cat:") && (() => {
          const catKey = STEPS[step].slice(4);
          const question = CATEGORY_QUESTIONS.find(([k]) => k === catKey)?.[1] ?? "Quel outil utilisez-vous ?";
          const category = catalog?.categories.find((c) => c.key === catKey);
          const index = CATEGORY_QUESTIONS.findIndex(([k]) => k === catKey) + 1;
          if (syncing) {
            return (
              <ToolSyncPage
                key={syncing}
                toolKey={syncing}
                label={catalog?.tools.find((t) => t.key === syncing)?.label ?? syncing}
                onRemove={() => void removeTool(syncing)}
              />
            );
          }
          return (
            <>
              <p className="mt-3 text-[12px] font-semibold text-text-faint">Vos outils · {index} sur {CATEGORY_QUESTIONS.length}</p>
              <h1 className="mt-2 break-words font-display text-[26px] italic leading-tight sm:text-[32px] md:text-[36px]">{question}</h1>
              {category && <p className="mt-3.5 max-w-lg text-[14.5px] text-text-soft">{category.ai_use}</p>}
              <p className="mt-4 text-[13px] text-text-faint">Cliquez sur votre outil pour le synchroniser. Vous n&rsquo;en utilisez pas ? Passez simplement à la question suivante.</p>
              <button type="button" onClick={() => void skipToDocuments()} className="mt-4 w-full rounded-xl border-[1.5px] border-border-strong bg-surface-alt px-4 py-3 text-left text-[13.5px] font-semibold text-text hover:border-accent sm:w-auto">
                Je ne me connecte à aucun logiciel pour l&rsquo;instant
                <span className="block text-[12.5px] font-normal text-text-soft">Passer directement à l&rsquo;envoi de vos documents →</span>
              </button>
              {error && <p className="mt-3 text-[13px] text-danger">{error}</p>}
              <div className="mt-5">
                {catalog ? (
                  <ToolsPicker
                    tools={catalog.tools}
                    categories={catalog.categories}
                    categoryKeys={[catKey]}
                    selected={toolKeys}
                    customTools={customTools}
                    onChange={setToolKeys}
                    onCustomChange={setCustomTools}
                    showCustom={false}
                    compact
                    onPick={(k) => void pickTool(k)}
                  />
                ) : (
                  <p className="text-[13px] text-text-faint">{catalogError ?? "Chargement…"}</p>
                )}
              </div>
            </>
          );
        })()}

        {STEPS[step] === "Autres outils" && (
          <>
            <h1 className="mt-3 break-words font-display text-[26px] italic leading-tight sm:text-[32px] md:text-[36px]">
              Un autre outil
              <br />
              important ?
            </h1>
            <p className="mt-3.5 max-w-lg text-[15px] text-text-soft">Un logiciel métier ou un outil maison qui n&rsquo;est apparu dans aucune liste : donnez son nom, l&rsquo;IA saura qu&rsquo;il existe. Sinon, passez à la suite.</p>
            <div className="mt-6">
              {catalog && (
                <ToolsPicker tools={catalog.tools} categories={catalog.categories} categoryKeys={[]} selected={toolKeys} customTools={customTools} onChange={setToolKeys} onCustomChange={setCustomTools} showCustom compact />
              )}
            </div>
          </>
        )}

        {STEPS[step] === "Documents" && (
          <>
            <h1 className="mt-3 break-words font-display text-[26px] italic leading-tight sm:text-[30px] md:text-[34px]">
              Vos autres
              <br />
              documents
            </h1>
            <p className="mt-3.5 max-w-lg text-[15px] text-text-soft">
              Des fichiers qui ne viennent d&rsquo;aucun de vos outils : un suivi Excel tenu à la main, une liste de prix, un export de comptabilité. Ils sont lus pour de vrai et alimentent votre espace. Vous pouvez aussi y revenir plus tard.
            </p>
            <div className="mt-7">
              <DataImport refreshKey={importRefresh} documentsOnly />
            </div>
          </>
        )}

        {STEPS[step] === "Votre rôle" && (
          <>
            <h1 className="mt-3 break-words font-display text-[26px] italic leading-tight sm:text-[32px] md:text-[36px]">
              Et vous, quel est
              <br />
              votre rôle&nbsp;?
            </h1>
            <p className="mt-3.5 max-w-lg text-[15px] text-text-soft">
              Le rôle détermine ce que vous voyez, ce que vous pouvez modifier et les actions que vous pouvez valider. D&rsquo;autres profils se créent ensuite dans Configuration.
            </p>

            <div className="mt-9">
              <label className="mb-2 block text-[13px] font-semibold text-text">Votre nom</label>
              <input
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                placeholder="ex. Camille Laurent"
                className="w-full rounded-xl border-[1.5px] border-border-strong px-4 py-3 text-[14.5px] outline-none focus:border-accent"
              />
            </div>

            <div className="mt-7 grid gap-2.5 sm:grid-cols-2">
              {ROLE_OPTIONS.map((opt) => (
                <button
                  key={opt.role}
                  type="button"
                  onClick={() => setRole(opt.role)}
                  aria-pressed={role === opt.role}
                  className={`rounded-xl border-[1.5px] px-4 py-3 text-left transition-colors ${role === opt.role ? "border-accent bg-accent-soft" : "border-border-strong hover:border-text-faint"}`}
                >
                  <span className={`block text-[13.5px] font-semibold ${role === opt.role ? "text-accent-strong" : "text-text"}`}>{ROLE_LABEL[opt.role]}</span>
                  <span className="mt-0.5 block text-[12px] text-text-faint">{opt.hint}</span>
                </button>
              ))}
            </div>
          </>
        )}

        {STEPS[step] === "Récapitulatif" && (
          <>
            <div className="flex flex-col items-center text-center">
              <div className="animate-pop flex h-[52px] w-[52px] items-center justify-center rounded-full bg-success">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
              </div>
              <h1 className="mt-5 break-words font-display text-[26px] italic leading-tight sm:text-[32px] md:text-[36px]">
                Tout est prêt{name ? `, ${name}` : ""}.
              </h1>
              <p className="mt-2.5 max-w-md text-[14.5px] text-text-soft">
                Ces informations personnalisent vos tableaux de bord et les recommandations de l&rsquo;IA. Vous pourrez
                les modifier à tout moment dans Configuration.
              </p>
            </div>

            <div className="mt-9 divide-y divide-border rounded-2xl border border-border px-6">
              <RecapRow label="Secteur d'activité" value={sectorLabel || "Non renseigné"} />
              {!AUTH_REQUIRED && <RecapRow label="Votre profil" value={`${userName.trim() || "Moi"} · ${ROLE_LABEL[role]}`} />}
              <RecapRow label="Taille de l'entreprise" value={size} />
              <RecapRow label="Pays" value={COUNTRY_OPTIONS.find((c) => c.code === country)?.label ?? country} />
              <RecapRow label="Vos enjeux" value={Object.values(answers).flat().length ? `${Object.values(answers).flat().length} réponses` : "Non renseignés"} />
              <RecapRow
                label="Outils déclarés"
                value={[...toolKeys.map((k) => catalog?.tools.find((t) => t.key === k)?.label ?? k), ...customTools].join(" · ") || "Aucun"}
              />
            </div>

            {error && <p className="mt-4 text-center text-[13px] text-danger">{error}</p>}
          </>
        )}

        <div className="sticky bottom-0 -mx-5 mt-8 flex items-center justify-between gap-3 border-t border-border bg-surface/95 px-5 py-3 backdrop-blur sm:static sm:mx-0 sm:mt-11 sm:border-0 sm:bg-transparent sm:p-0">
          <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1">
            {(step > 0 || syncing) && (
              <button type="button" onClick={() => (syncing ? setSyncing(null) : setStep((s) => s - 1))} className="flex items-center gap-1.5 whitespace-nowrap py-2 text-[13.5px] font-medium text-text-soft hover:text-text">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
                Retour
              </button>
            )}
            {syncing ? (
              <button type="button" onClick={() => void next()} className="whitespace-nowrap py-2 text-[13.5px] font-medium text-text-soft hover:text-text">
                Ignorer<span className="hidden sm:inline">&nbsp;cette étape</span>
              </button>
            ) : (
              <button type="button" onClick={skipToProduct} className="whitespace-nowrap py-2 text-[13.5px] font-medium text-text-soft hover:text-text">
                <span className="sm:hidden">Plus tard</span><span className="hidden sm:inline">Terminer plus tard</span>
              </button>
            )}
          </div>

          {step < STEPS.length - 1 ? (
            <Button onClick={next} loading={saving} disabled={!stepReady()}>
              Continuer
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
            </Button>
          ) : (
            <Button onClick={finish} loading={saving}>
              Entrer dans le Centre de contrôle
              {!saving && <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6" /></svg>}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function RecapRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-3.5">
      <span className="text-[13px] text-text-faint">{label}</span>
      <span className="text-right text-[13.5px] font-semibold text-text">{value}</span>
    </div>
  );
}
