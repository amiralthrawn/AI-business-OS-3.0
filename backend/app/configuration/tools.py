"""Catalogue of the tools a company can run on (V3 configuration).

Every tool belongs to a category. The category fixes what data the tool holds,
how the AI brings it in, and what the AI does with it. A company ticks the
tools it uses; the integration plan then tells it, per tool, the exact way to
bring its data into AI Business OS.

Honesty rule: a way of connecting is listed as `available` only when the
product really does it today. Today that is the file import (CSV, Excel, FEC),
which works for every tool that can export, i.e. all of them. Direct
connections (OAuth, API key, open banking, read-only database access) need
credentials or an authorisation from the company or the provider; they are
listed as what they are, never shown as connected.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    data: tuple[str, ...]          # what the tool holds
    ai_use: str                    # what the AI does with it
    direct: tuple[str, ...]        # direct ways to connect
    export: str                    # how to export a file from it
    import_kinds: tuple[str, ...]  # file imports that fit this category


CATEGORIES: dict[str, Category] = {c.key: c for c in [
    Category("erp", "ERP / gestion intégrée",
             ("clients", "fournisseurs", "articles et prix", "commandes et factures", "stocks", "écritures comptables"),
             "Reconstruit le référentiel (clients, fournisseurs, articles) et l'historique de transactions, puis calcule marges, délais et dépendances.",
             ("API / OData / base de données en lecture seule", "export planifié"),
             "Menu d'export du module ventes, achats et stock (CSV ou Excel), plus le FEC depuis la comptabilité.",
             ("customers", "suppliers", "products", "fec")),
    Category("crm", "CRM / relation client",
             ("clients et prospects", "contacts", "opportunités", "pipeline", "historique d'échanges"),
             "Alimente les clients, le pipeline commercial et la prévision des ventes ; repère les relances oubliées.",
             ("OAuth ou clé API", "export planifié"),
             "Export des comptes (clients) et des opportunités en CSV depuis la liste de vos clients.",
             ("customers",)),
    Category("accounting", "Comptabilité",
             ("écritures comptables", "tiers clients et fournisseurs", "TVA", "bilan et compte de résultat"),
             "Lit le FEC pour reconstituer chiffre d'affaires, charges, tiers et créances ; base de toute analyse financière.",
             ("OAuth ou clé API", "export FEC"),
             "Export du FEC (Fichier des Écritures Comptables) : généralement dans Fichier / Export / FEC. Obligatoire en France, tous les logiciels le produisent.",
             ("fec", "customers", "suppliers")),
    Category("invoicing", "Facturation et devis",
             ("factures", "devis", "clients", "paiements reçus"),
             "Suit le chiffre d'affaires facturé, les retards de paiement et les devis non transformés.",
             ("OAuth ou clé API", "export planifié"),
             "Export de la liste des clients et des factures en CSV ou Excel.",
             ("customers", "products")),
    Category("bank", "Banque (compte entreprise)",
             ("soldes", "mouvements bancaires", "prélèvements et virements", "encaissements clients"),
             "Donne la trésorerie réelle, les flux à venir et le rapprochement avec les factures.",
             ("agrégation bancaire (DSP2) via un prestataire agréé", "export de relevés"),
             "Télécharger les relevés dans l'espace bancaire en ligne (CSV, OFX, CAMT.053 ou MT940).",
             ()),
    Category("payment", "Paiement en ligne",
             ("paiements", "remboursements", "litiges", "commissions"),
             "Mesure les encaissements, les commissions et les remboursements.",
             ("clé API", "OAuth"),
             "Export des transactions du tableau de bord en CSV.",
             ()),
    Category("procurement", "Achats et fournisseurs",
             ("fournisseurs", "demandes d'achat", "commandes d'achat", "prix et conditions"),
             "Compare les prix, les délais et la fiabilité des fournisseurs ; signale la dépendance.",
             ("OAuth ou clé API", "export planifié"),
             "Export de la liste fournisseurs et des commandes d'achat en CSV ou Excel.",
             ("suppliers", "products")),
    Category("ecommerce", "E-commerce et marketplace",
             ("commandes web", "clients", "catalogue", "stocks", "retours"),
             "Suit les ventes en ligne, le catalogue, les retours et les marges par canal.",
             ("clé API ou OAuth",),
             "Export des commandes, clients et produits depuis l'administration de la boutique (CSV).",
             ("customers", "products")),
    Category("stock", "Stock, entrepôt et logistique",
             ("niveaux de stock", "mouvements", "expéditions", "transporteurs"),
             "Détecte ruptures, surstocks, retards de livraison et immobilisation.",
             ("OAuth ou clé API", "export planifié"),
             "Export de l'état des stocks et des mouvements en CSV ou Excel.",
             ("products",)),
    Category("production", "Production, qualité et maintenance",
             ("ordres de fabrication", "rendements", "pannes", "contrôles qualité"),
             "Relie les coûts de production, les délais et la qualité à la marge.",
             ("base de données en lecture seule", "export planifié"),
             "Export des ordres de fabrication et des indicateurs en CSV ou Excel.",
             ("products",)),
    Category("hr", "RH, paie et temps",
             ("salariés", "contrats", "congés et absences", "paie", "temps passé"),
             "Suit les effectifs, la masse salariale et la charge des équipes (accès restreint aux profils autorisés).",
             ("OAuth ou clé API", "export planifié"),
             "Export de la liste du personnel et de la masse salariale en CSV (sans données sensibles inutiles).",
             ()),
    Category("expenses", "Notes de frais et cartes",
             ("dépenses", "justificatifs", "cartes"),
             "Catégorise les dépenses et repère les écarts.",
             ("OAuth ou clé API",),
             "Export des dépenses en CSV.",
             ()),
    Category("marketing", "Marketing, site web et réseaux",
             ("visites", "campagnes", "leads", "coûts d'acquisition"),
             "Relie les dépenses marketing aux demandes et aux ventes obtenues.",
             ("OAuth",),
             "Export des campagnes et des leads en CSV.",
             ()),
    Category("support", "Support et service client",
             ("tickets", "réclamations", "satisfaction"),
             "Repère les clients mécontents et les causes récurrentes de problèmes.",
             ("OAuth ou clé API",),
             "Export des tickets en CSV.",
             ()),
    Category("bi", "BI, tableaux de bord et reporting",
             ("indicateurs existants", "modèles de données", "rapports"),
             "Reprend vos indicateurs actuels comme référence de ce qui compte pour vous.",
             ("OAuth / service principal",),
             "Exporter les tables ou rapports utilisés (Excel ou CSV), ou nous indiquer les indicateurs suivis.",
             ("customers", "suppliers", "products")),
    Category("spreadsheet", "Tableurs et fichiers",
             ("tableaux de suivi", "listes de prix", "devis", "historiques manuels"),
             "C'est souvent le vrai système de la PME : l'IA lit les colonnes, comprend leur sens et les rattache au référentiel.",
             ("OAuth (Drive, SharePoint, OneDrive)",),
             "Enregistrer le fichier en .xlsx ou .csv et le déposer ici, une feuille par fichier.",
             ("customers", "suppliers", "products")),
    Category("database", "Base de données et cloud",
             ("tables métier", "entrepôt de données"),
             "Se connecte en lecture seule à votre base et cartographie ses tables vers clients, fournisseurs, articles et transactions.",
             ("identifiants en lecture seule", "service principal"),
             "Exporter les tables principales en CSV si l'accès direct n'est pas possible.",
             ("customers", "suppliers", "products")),
    Category("messaging", "Messagerie, agenda et collaboration",
             ("emails", "rendez-vous", "conversations", "documents partagés"),
             "Retrouve les échanges avec clients et fournisseurs et les engagements pris.",
             ("OAuth",),
             "Pas d'export de fichier nécessaire : la connexion se fait avec l'autorisation de la messagerie.",
             ()),
    Category("projects", "Gestion de projet et tâches",
             ("projets", "tâches", "délais"),
             "Suit l'avancement et les retards des projets.",
             ("OAuth ou clé API",),
             "Export des projets et tâches en CSV.",
             ()),
    Category("legal", "Juridique, signature et conformité",
             ("contrats", "signatures", "échéances"),
             "Suit les échéances de contrats et les obligations de conformité.",
             ("OAuth ou clé API",),
             "Export de la liste des contrats en CSV.",
             ()),
]}

# (key, label, category) -- the ones a company may name. "other" is free text.
TOOLS: list[tuple[str, str, str]] = [
    # ERP
    ("sap_s4hana", "SAP S/4HANA", "erp"), ("sap_business_one", "SAP Business One", "erp"), ("sap_bydesign", "SAP Business ByDesign", "erp"),
    ("oracle_netsuite", "Oracle NetSuite", "erp"), ("oracle_fusion", "Oracle Fusion Cloud ERP", "erp"), ("oracle_ebs", "Oracle E-Business Suite", "erp"),
    ("ms_dynamics_365", "Microsoft Dynamics 365", "erp"), ("ms_dynamics_nav", "Dynamics NAV / Business Central", "erp"),
    ("odoo", "Odoo", "erp"), ("sage_x3", "Sage X3", "erp"), ("sage_100", "Sage 100", "erp"), ("sage_50", "Sage 50", "erp"),
    ("cegid", "Cegid", "erp"), ("divalto", "Divalto", "erp"), ("ebp_erp", "EBP Gestion", "erp"), ("infor", "Infor", "erp"),
    ("epicor", "Epicor", "erp"), ("acumatica", "Acumatica", "erp"), ("dolibarr", "Dolibarr", "erp"), ("axonaut", "Axonaut", "erp"),
    ("sellsy", "Sellsy", "erp"), ("zoho_books", "Zoho One / Zoho Inventory", "erp"), ("prestashop_erp", "Gestion interne sur mesure (maison)", "erp"),
    # CRM
    ("salesforce", "Salesforce", "crm"), ("hubspot", "HubSpot", "crm"), ("pipedrive", "Pipedrive", "crm"), ("zoho_crm", "Zoho CRM", "crm"),
    ("ms_dynamics_crm", "Dynamics 365 Sales", "crm"), ("sugarcrm", "SugarCRM", "crm"), ("freshsales", "Freshsales", "crm"),
    ("monday_crm", "monday CRM", "crm"), ("noCRM", "noCRM.io", "crm"), ("axonaut_crm", "Axonaut CRM", "crm"), ("copper", "Copper", "crm"),
    # Accounting
    ("pennylane", "Pennylane", "accounting"), ("quickbooks", "QuickBooks", "accounting"), ("xero", "Xero", "accounting"),
    ("sage_compta", "Sage Comptabilité", "accounting"), ("cegid_compta", "Cegid Quadra / Loop", "accounting"), ("ebp_compta", "EBP Compta", "accounting"),
    ("ciel", "Ciel", "accounting"), ("tiime", "Tiime", "accounting"), ("indy", "Indy", "accounting"), ("dext", "Dext", "accounting"),
    ("cabinet_expert", "Cabinet d'expertise comptable (fichiers envoyés par mon comptable)", "accounting"),
    ("myunisoft", "MyUnisoft", "accounting"), ("inqom", "Inqom", "accounting"), ("freshbooks", "FreshBooks", "accounting"), ("wave", "Wave", "accounting"),
    # Invoicing
    ("facture_net", "Facture.net", "invoicing"), ("henrri", "Henrri", "invoicing"), ("zervant", "Zervant", "invoicing"),
    ("billit", "Billit", "invoicing"), ("stripe_billing", "Stripe Billing", "invoicing"), ("chargebee", "Chargebee", "invoicing"),
    ("quickbooks_invoice", "Factures sur Word / Excel", "invoicing"),
    # Banks (Europe + Maghreb + neobanks)
    ("bnp_paribas", "BNP Paribas", "bank"), ("societe_generale", "Société Générale", "bank"), ("credit_agricole", "Crédit Agricole", "bank"),
    ("lcl", "LCL", "bank"), ("credit_mutuel", "Crédit Mutuel", "bank"), ("cic", "CIC", "bank"), ("banque_populaire", "Banque Populaire", "bank"),
    ("caisse_epargne", "Caisse d'Epargne", "bank"), ("la_banque_postale", "La Banque Postale", "bank"), ("hsbc", "HSBC", "bank"),
    ("boursorama_pro", "Boursorama Pro", "bank"), ("qonto", "Qonto", "bank"), ("shine", "Shine", "bank"), ("revolut_business", "Revolut Business", "bank"),
    ("wise_business", "Wise Business", "bank"), ("n26_business", "N26 Business", "bank"), ("memo_bank", "Memo Bank", "bank"),
    ("ing", "ING", "bank"), ("deutsche_bank", "Deutsche Bank", "bank"), ("commerzbank", "Commerzbank", "bank"), ("santander", "Santander", "bank"),
    ("bbva", "BBVA", "bank"), ("barclays", "Barclays", "bank"), ("ubs", "UBS", "bank"), ("bnp_fortis", "BNP Paribas Fortis / KBC / Belfius", "bank"),
    ("attijariwafa", "Attijariwafa Bank", "bank"), ("bank_of_africa", "Bank of Africa (BMCE)", "bank"), ("cih_bank", "CIH Bank", "bank"),
    ("banque_populaire_maroc", "Banque Populaire du Maroc", "bank"), ("sgmb", "Société Générale Maroc", "bank"), ("bmci", "BMCI", "bank"),
    ("emirates_nbd", "Emirates NBD / banque du Golfe", "bank"), ("autre_banque", "Autre banque", "bank"),
    # Payment
    ("stripe", "Stripe", "payment"), ("paypal", "PayPal", "payment"), ("adyen", "Adyen", "payment"), ("mollie", "Mollie", "payment"),
    ("sumup", "SumUp", "payment"), ("alma", "Alma", "payment"), ("gocardless", "GoCardless", "payment"), ("lemonway", "Lemonway", "payment"),
    ("payzone_cmi", "CMI / Payzone (Maroc)", "payment"), ("checkout", "Checkout.com", "payment"),
    # Procurement
    ("coupa", "Coupa", "procurement"), ("ariba", "SAP Ariba", "procurement"), ("jaggaer", "Jaggaer", "procurement"), ("ivalua", "Ivalua", "procurement"),
    ("kiwibuy", "Kiwibuy / Zycus / Basware", "procurement"), ("achats_excel", "Achats gérés par Excel / emails", "procurement"),
    # E-commerce
    ("shopify", "Shopify", "ecommerce"), ("woocommerce", "WooCommerce", "ecommerce"), ("prestashop", "PrestaShop", "ecommerce"),
    ("magento", "Magento / Adobe Commerce", "ecommerce"), ("amazon_seller", "Amazon Seller Central", "ecommerce"), ("ebay", "eBay", "ecommerce"),
    ("cdiscount", "Cdiscount Marketplace", "ecommerce"), ("alibaba", "Alibaba / AliExpress", "ecommerce"), ("octopart", "Octopart / DigiKey / Mouser (composants)", "ecommerce"),
    ("bigcommerce", "BigCommerce", "ecommerce"), ("wix_squarespace", "Wix / Squarespace", "ecommerce"),
    # Stock / logistics
    ("sage_wms", "Sage / Cegid WMS", "stock"), ("manhattan", "Manhattan / Blue Yonder WMS", "stock"), ("sendcloud", "Sendcloud", "stock"),
    ("boxtal", "Boxtal", "stock"), ("dhl", "DHL / UPS / FedEx", "stock"), ("colissimo", "Colissimo / Chronopost", "stock"),
    ("zoho_inventory", "Zoho Inventory", "stock"), ("sortly", "Sortly / inFlow", "stock"), ("stock_excel", "Stock suivi sous Excel", "stock"),
    # Production
    ("mes", "MES (suivi de production)", "production"), ("gmao", "GMAO / maintenance", "production"), ("plm", "PLM / Solidworks PDM", "production"),
    ("quality_qms", "Logiciel qualité (QMS)", "production"),
    # HR
    ("payfit", "PayFit", "hr"), ("lucca", "Lucca", "hr"), ("silae", "Silae", "hr"), ("sage_paie", "Sage Paie", "hr"), ("ceridian_dayforce", "Dayforce / Workday", "hr"),
    ("factorial", "Factorial", "hr"), ("personio", "Personio", "hr"), ("bamboohr", "BambooHR", "hr"), ("ADP", "ADP", "hr"),
    ("cegid_rh", "Cegid RH", "hr"), ("welcome_jungle", "Welcome to the Jungle / ATS", "hr"), ("toggl", "Toggl / Clockify", "hr"),
    # Expenses
    ("spendesk", "Spendesk", "expenses"), ("expensya", "Expensya", "expenses"), ("mooncard", "Mooncard", "expenses"),
    ("swile", "Swile", "expenses"), ("notion_frais", "Notes de frais manuelles", "expenses"), ("airwallex", "Airwallex", "expenses"),
    # Marketing
    ("google_analytics", "Google Analytics", "marketing"), ("google_ads", "Google Ads", "marketing"), ("meta_ads", "Meta Ads (Facebook / Instagram)", "marketing"),
    ("linkedin_ads", "LinkedIn Ads / Sales Navigator", "marketing"), ("mailchimp", "Mailchimp", "marketing"), ("brevo", "Brevo", "marketing"),
    ("wordpress", "Site WordPress", "marketing"), ("semrush", "Semrush / SEO", "marketing"),
    # Support
    ("zendesk", "Zendesk", "support"), ("freshdesk", "Freshdesk", "support"), ("intercom", "Intercom", "support"), ("crisp", "Crisp", "support"), ("helpscout", "Help Scout", "support"),
    # BI
    ("power_bi", "Power BI", "bi"), ("tableau", "Tableau", "bi"), ("looker", "Looker / Looker Studio", "bi"), ("metabase", "Metabase", "bi"),
    ("qlik", "Qlik", "bi"), ("sap_analytics", "SAP Analytics Cloud", "bi"), ("domo", "Domo", "bi"), ("grafana", "Grafana", "bi"),
    # Spreadsheets
    ("excel", "Microsoft Excel", "spreadsheet"), ("google_sheets", "Google Sheets", "spreadsheet"), ("airtable", "Airtable", "spreadsheet"),
    ("notion", "Notion", "spreadsheet"), ("sharepoint", "SharePoint / OneDrive", "spreadsheet"), ("google_drive", "Google Drive", "spreadsheet"),
    ("dropbox", "Dropbox / Box", "spreadsheet"), ("smartsheet", "Smartsheet", "spreadsheet"), ("access", "Microsoft Access", "spreadsheet"),
    ("papier", "Dossiers papier / documents scannés", "spreadsheet"),
    # Database / cloud
    ("azure", "Microsoft Azure (SQL, Synapse, Fabric)", "database"), ("aws", "Amazon Web Services (RDS, Redshift)", "database"),
    ("gcp_bigquery", "Google Cloud (BigQuery, Cloud SQL)", "database"), ("oracle_db", "Oracle Database", "database"),
    ("sql_server", "Microsoft SQL Server", "database"), ("postgresql", "PostgreSQL", "database"), ("mysql", "MySQL / MariaDB", "database"),
    ("snowflake", "Snowflake", "database"), ("databricks", "Databricks", "database"), ("mongodb", "MongoDB", "database"), ("sap_hana", "SAP HANA", "database"),
    # Messaging
    ("gmail", "Gmail / Google Workspace", "messaging"), ("outlook", "Outlook / Microsoft 365", "messaging"), ("imap", "Autre messagerie (IMAP)", "messaging"),
    ("slack", "Slack", "messaging"), ("teams", "Microsoft Teams", "messaging"), ("whatsapp_business", "WhatsApp Business", "messaging"),
    ("google_calendar", "Google Agenda", "messaging"), ("outlook_calendar", "Agenda Outlook", "messaging"), ("zoom", "Zoom / Meet", "messaging"),
    # Projects
    ("asana", "Asana", "projects"), ("trello", "Trello", "projects"), ("jira", "Jira", "projects"), ("monday", "monday.com", "projects"),
    ("clickup", "ClickUp", "projects"), ("basecamp", "Basecamp", "projects"),
    # Legal
    ("docusign", "DocuSign", "legal"), ("yousign", "Yousign", "legal"), ("legalstart", "Legalstart / Captain Contrat", "legal"), ("ironclad", "Ironclad / contrats", "legal"),
]

_TOOL_BY_KEY = {key: (label, category) for key, label, category in TOOLS}

# Specific export paths the AI knows by heart, beyond the category default.
KNOWN_EXPORTS: dict[str, str] = {
    "pennylane": "Pennylane : Paramètres → Exports → « Export FEC », puis « Clients » et « Fournisseurs » en CSV.",
    "sage_100": "Sage 100 : Fichier → Exportation → Écritures comptables au format FEC.",
    "sage_compta": "Sage : Fichier → Exporter → FEC (Fichier des Écritures Comptables).",
    "quickbooks": "QuickBooks : Rapports → Clients et Fournisseurs → Exporter vers Excel ; le FEC se génère via votre comptable.",
    "odoo": "Odoo : sur la liste Clients ou Produits, cocher tout → Action → Exporter ; la comptabilité française propose aussi l'export FEC.",
    "salesforce": "Salesforce : Rapports → créer un rapport « Comptes » → Exporter → CSV.",
    "hubspot": "HubSpot : Contacts / Sociétés → Exporter → CSV.",
    "excel": "Excel : Fichier → Enregistrer sous → .xlsx. Une feuille par fichier (clients, fournisseurs, produits).",
    "sap_s4hana": "SAP : transaction de rapport (ex. XD03 / MM60) → exporter la liste en tableur ; ou extraction de tables via votre équipe IT.",
    "sap_business_one": "SAP Business One : Gestion des données → Exporter vers Excel depuis la liste partenaires et articles.",
    "oracle_netsuite": "NetSuite : Listes → Clients / Fournisseurs / Articles → Exporter en CSV.",
    "power_bi": "Power BI : dans le rapport, ··· → Exporter les données ; ou nous lister les mesures et tables suivies.",
    "shopify": "Shopify : Clients / Produits → Exporter → CSV.",
    "qonto": "Qonto : Transactions → Exporter (CSV) ; connexion directe possible via agrégation bancaire.",
}


def get_category(category_key: str) -> Category:
    return CATEGORIES[category_key]


def tool_info(tool_key: str) -> tuple[str, Category] | None:
    entry = _TOOL_BY_KEY.get(tool_key)
    if entry is None:
        return None
    label, category = entry
    return label, CATEGORIES[category]


def is_known_tool(tool_key: str) -> bool:
    return tool_key in _TOOL_BY_KEY


# The tools are asked over four pages, each with the reason it is asked, so
# the person sees why the AI needs it rather than a long questionnaire.
TOOL_PAGES: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("business", "Votre gestion au quotidien",
     "Vos clients, vos ventes, vos factures et vos achats vivent déjà quelque part. En sachant où, l'IA les retrouve toute seule : vous n'avez rien à ressaisir.",
     ("erp", "crm", "accounting", "invoicing", "procurement", "ecommerce")),
    ("money", "Votre argent",
     "Pour vous montrer votre vraie trésorerie et repérer les paiements en retard, l'IA doit savoir par où passe votre argent. Rien n'est connecté sans votre accord.",
     ("bank", "payment", "expenses")),
    ("operations", "Votre activité et vos équipes",
     "Stock, production, équipes, messages : c'est ce qui explique vos résultats. Indiquer vos outils permet à l'IA de relier ce qui se passe sur le terrain à votre marge.",
     ("stock", "production", "hr", "messaging", "projects", "support", "marketing", "legal")),
    ("files", "Vos tableaux et vos fichiers",
     "Souvent, le vrai système d'une entreprise tient dans quelques tableurs et rapports. L'IA s'en sert pour reprendre vos propres chiffres et vos propres indicateurs.",
     ("spreadsheet", "bi", "database")),
]
