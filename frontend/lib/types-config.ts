// V3 configuration phase (backend app/configuration).

export type CatalogSector = { key: string; label: string; group: string; group_label: string };
export type CatalogGroup = { key: string; label: string; business_models: string[]; questions: string[] };
export type CatalogFunction = { key: string; label: string; description: string };
export type CatalogCategory = { key: string; label: string; data: string[]; ai_use: string };
export type CatalogTool = { key: string; label: string; category: string };

export type ConfigCatalog = {
  sectors: CatalogSector[];
  groups: CatalogGroup[];
  functions: CatalogFunction[];
  categories: CatalogCategory[];
  tools: CatalogTool[];
};

export type ConfigurationData = {
  sector_key?: string;
  sector_custom?: string;
  tools?: Record<string, { data?: string; last_import_at?: string }>;
  custom_tools?: string[];
  problems?: string;
  external_factors?: string;
  completed_at?: string;
};

export type AIProfile = {
  sector_key: string | null;
  sector_label: string | null;
  group: string;
  group_label: string;
  key_metrics: string[];
  typical_risks: string[];
  external_factors: string[];
  next_questions: string[];
  tools: { key: string; label: string; category: string; data: string }[];
};

export type ConfigurationRead = { configuration: ConfigurationData; ai_profile: AIProfile; configured: boolean };

export type ConfigurationUpdate = {
  sector_key?: string;
  sector_custom?: string;
  functions?: string[];
  tools?: string[];
  custom_tools?: string[];
  problems?: string;
  external_factors?: string;
  company_size?: string;
  country?: string;
  business_model?: string;
  objectives?: string;
};

export type ImportKind = "customers" | "suppliers" | "products" | "fec";

export type IntegrationItem = {
  key: string;
  label: string;
  category: string;
  category_label: string;
  data: string[];
  ai_use: string;
  export_help: string;
  import_kinds: ImportKind[];
  direct_methods: string[];
  status: "imported" | "to_connect";
  last_import_at: string | null;
};

export type ImportEntry = { kind: ImportKind; file: string; created: number; updated: number; skipped: number; tool: string | null; at: string };

export type IntegrationPlan = {
  tools: IntegrationItem[];
  custom_tools: string[];
  imports: ImportEntry[];
  fec_summary: { customers_found: number; suppliers_found: number; revenue: number; purchases: number; entries: number; from: string | null; to: string | null } | null;
};

export type ImportResultRead = {
  kind: ImportKind;
  rows: number;
  created: number;
  updated: number;
  skipped: number;
  problems: string[];
  recognised_columns: Record<string, string>;
  summary: IntegrationPlan["fec_summary"];
};
