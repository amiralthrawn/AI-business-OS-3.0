"use client";

import { useEffect, useState } from "react";
import DataImport from "@/components/configuration/DataImport";
import SectorPicker from "@/components/configuration/SectorPicker";
import ToolsPicker from "@/components/configuration/ToolsPicker";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { getConfigCatalog, getConfiguration, saveConfiguration } from "@/lib/api";
import type { ConfigCatalog } from "@/lib/types-config";

// Settings: the sector, the tools and the data brought in from them. The same
// pieces as the onboarding, editable at any time by whoever manages settings.
export default function ConfigurationPanel({ canEdit }: { canEdit: boolean }) {
  const [catalog, setCatalog] = useState<ConfigCatalog | null>(null);
  const [sectorKey, setSectorKey] = useState("");
  const [sectorCustom, setSectorCustom] = useState("");
  const [toolKeys, setToolKeys] = useState<string[]>([]);
  const [customTools, setCustomTools] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    getConfigCatalog().then(setCatalog).catch((err) => setMessage(err instanceof Error ? err.message : "Catalogue indisponible."));
    getConfiguration()
      .then((c) => {
        setSectorKey(c.configuration.sector_key ?? "");
        setSectorCustom(c.configuration.sector_custom ?? "");
        setToolKeys(Object.keys(c.configuration.tools ?? {}));
        setCustomTools(c.configuration.custom_tools ?? []);
      })
      .catch(() => undefined);
  }, []);

  async function save() {
    setStatus("saving");
    setMessage(null);
    try {
      await saveConfiguration({ sector_key: sectorKey || undefined, sector_custom: sectorCustom, tools: toolKeys, custom_tools: customTools });
      setStatus("saved");
      setRefresh((n) => n + 1);
      setTimeout(() => setStatus("idle"), 2200);
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Enregistrement impossible.");
    }
  }

  return (
    <>
      <Card className="p-7">
        <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Secteur d&rsquo;activité</span>
        <p className="mt-2 text-[12.5px] text-text-faint">L&rsquo;IA adapte son vocabulaire, ses indicateurs et ses questions à votre secteur.</p>
        <div className="mt-4">
          {catalog ? (
            <SectorPicker sectors={catalog.sectors} sectorKey={sectorKey} custom={sectorCustom} onChange={(k, c) => { setSectorKey(k); setSectorCustom(c); }} />
          ) : (
            <p className="text-[13px] text-text-faint">{message ?? "Chargement…"}</p>
          )}
        </div>
      </Card>

      <Card className="p-7">
        <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Outils utilisés par l&rsquo;entreprise</span>
        <p className="mt-2 text-[12.5px] text-text-faint">ERP, CRM, comptabilité, banque, BI, tableurs, bases de données… L&rsquo;IA s&rsquo;appuie sur cette liste pour savoir où trouver vos données.</p>
        <div className="mt-4">
          {catalog && <ToolsPicker tools={catalog.tools} categories={catalog.categories} selected={toolKeys} customTools={customTools} onChange={setToolKeys} onCustomChange={setCustomTools} />}
        </div>
        {message && catalog && <p className="mt-3 text-[12.5px] text-danger">{message}</p>}
        <div className="mt-6 flex items-center justify-end gap-3">
          {status === "saved" && <span className="text-[12px] font-semibold text-success">Enregistré</span>}
          <Button onClick={save} loading={status === "saving"} disabled={!canEdit || !sectorKey}>
            Enregistrer
          </Button>
        </div>
      </Card>

      <Card className="p-7">
        <span className="text-[11.5px] font-bold tracking-wide text-text-faint uppercase">Données de vos outils</span>
        <p className="mt-2 mb-5 text-[12.5px] text-text-faint">Déposez les exports de vos outils : ils sont lus pour de vrai et alimentent clients, fournisseurs, articles et finances.</p>
        {canEdit ? <DataImport refreshKey={refresh} /> : <p className="text-[13px] text-text-faint">Seuls les profils qui gèrent la configuration peuvent importer des données.</p>}
      </Card>
    </>
  );
}
