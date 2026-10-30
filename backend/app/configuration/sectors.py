"""Sector knowledge the AI starts from (V3 configuration).

A company declares its sector in the configuration phase. The sector maps to a
SectorGroup: the vocabulary, the metrics that matter, the usual risks, the
external factors and the questions the AI asks next. This is what lets the AI
understand a business "whatever the business is" before any data arrives, and
read the imported data with the right frame afterwards (a negociant's margin
per reference is not a hotel's occupancy rate).

The sector list is open: "Autre" accepts free text and falls back to the
generic group, so no company is ever blocked.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SectorGroup:
    key: str
    label: str
    business_models: tuple[str, ...]
    key_metrics: tuple[str, ...]
    typical_risks: tuple[str, ...]
    external_factors: tuple[str, ...]
    vocabulary: dict[str, str]
    questions: tuple[str, ...]


GROUPS: dict[str, SectorGroup] = {g.key: g for g in [
    SectorGroup(
        "trading", "Négoce et distribution",
        ("Négoce pur (achat-revente)", "Distribution avec stock", "Import-export", "Courtage / broker", "Grossiste"),
        ("marge par référence", "rotation du stock", "délai de paiement clients et fournisseurs", "dépendance fournisseur", "valeur du stock immobilisé"),
        ("variation des prix d'achat", "rupture ou surstock", "impayés clients", "dépendance à un fournisseur ou à un client", "change et droits de douane", "contrefaçon / traçabilité"),
        ("cours des matières et composants", "taux de change", "droits de douane et réglementation import", "pénuries et délais de production fournisseurs", "saison et cycles d'achat des clients"),
        {"customer": "client acheteur", "supplier": "fournisseur / fabricant", "product": "référence", "order": "commande"},
        ("Quelles familles de produits vendez-vous et lesquelles font votre marge ?", "Achetez-vous au comptant, à crédit ou sur commande ferme ?", "Quels pays vendent et achètent chez vous, dans quelles devises ?", "Quels fournisseurs ou clients sont critiques ?"),
    ),
    SectorGroup(
        "retail", "Commerce de détail et e-commerce",
        ("Magasin physique", "E-commerce", "Marketplace", "Omnicanal", "Abonnement / récurrent"),
        ("panier moyen", "taux de transformation", "marge brute par catégorie", "rotation du stock", "coût d'acquisition client"),
        ("rupture de stock", "invendus et démarque", "retours", "dépendance à une plateforme publicitaire ou à une marketplace", "saisonnalité"),
        ("saisonnalité (soldes, fêtes)", "coût de la publicité", "concurrence en ligne", "pouvoir d'achat"),
        {"customer": "client", "supplier": "fournisseur", "product": "article", "order": "commande"},
        ("Vendez-vous en boutique, en ligne ou les deux ?", "Quelles plateformes (site, marketplaces) apportent votre chiffre d'affaires ?", "Quel est votre taux de retours ?"),
    ),
    SectorGroup(
        "manufacturing", "Industrie et production",
        ("Production sur stock", "Production sur commande", "Sous-traitance", "Assemblage"),
        ("coût de revient", "taux de rendement / rebuts", "taux d'utilisation des machines", "délai de production", "stock matières et en-cours"),
        ("rupture d'approvisionnement", "panne machine", "hausse des matières premières", "non-qualité et rappels", "dépendance à un gros donneur d'ordre"),
        ("prix des matières premières et de l'énergie", "réglementation et normes", "délais fournisseurs", "cycles de la demande"),
        {"customer": "client / donneur d'ordre", "supplier": "fournisseur de matières", "product": "produit fini", "order": "ordre de fabrication / commande"},
        ("Que fabriquez-vous et à partir de quelles matières ?", "Quel est votre goulot de production ?", "Fabriquez-vous sur stock ou sur commande ?"),
    ),
    SectorGroup(
        "construction", "Bâtiment, immobilier et ingénierie",
        ("Chantiers (BTP)", "Promotion", "Gestion locative / syndic", "Transaction", "Bureau d'études"),
        ("marge par chantier ou projet", "avancement et facturation", "encours clients", "carnet de commandes", "taux d'occupation / vacance"),
        ("dérive des coûts de chantier", "retards et pénalités", "impayés et retenues de garantie", "sous-traitance", "hausse des matériaux"),
        ("prix des matériaux", "taux d'intérêt et crédit immobilier", "réglementation et normes", "météo et saisonnalité"),
        {"customer": "maître d'ouvrage / client", "supplier": "sous-traitant / fournisseur", "product": "lot / prestation", "order": "marché / devis"},
        ("Travaillez-vous par chantier ou par projet ? Comment suivez-vous leur rentabilité ?", "Qui sont vos principaux sous-traitants ?", "Quel est votre carnet de commandes ?"),
    ),
    SectorGroup(
        "services", "Services aux entreprises et conseil",
        ("Régie / temps passé", "Forfait projet", "Abonnement / récurrent", "Honoraires"),
        ("taux d'occupation", "taux journalier moyen", "marge par mission", "récurrent (MRR/ARR)", "délai d'encaissement"),
        ("dépendance à quelques clients", "sous-utilisation des équipes", "dérive du temps passé", "impayés", "départ de personnes clés"),
        ("conjoncture des clients", "concurrence", "pénurie de talents", "évolutions réglementaires"),
        {"customer": "client", "supplier": "sous-traitant / prestataire", "product": "prestation", "order": "mission / contrat"},
        ("Facturez-vous au temps passé, au forfait ou à l'abonnement ?", "Combien de personnes produisent, et à quel taux d'occupation ?", "Quels clients représentent plus de 20 % de votre chiffre d'affaires ?"),
    ),
    SectorGroup(
        "tech", "Logiciel, informatique et télécoms",
        ("SaaS / abonnement", "Licence", "ESN / prestation", "Infogérance", "Opérateur"),
        ("MRR / ARR", "churn", "coût d'acquisition client", "marge brute", "taux d'occupation des équipes"),
        ("churn élevé", "dépendance à un gros client", "dette technique", "coûts cloud", "recrutement"),
        ("concurrence", "coûts d'infrastructure cloud", "réglementation des données (RGPD)", "levées de fonds et financement"),
        {"customer": "client / compte", "supplier": "fournisseur / éditeur", "product": "offre / licence", "order": "abonnement / contrat"},
        ("Quel est votre modèle de revenu (abonnement, licence, prestation) ?", "Quel est votre churn mensuel ?", "Quels sont vos principaux coûts d'infrastructure ?"),
    ),
    SectorGroup(
        "hospitality", "Tourisme, hôtellerie et restauration",
        ("Agence / voyagiste", "Hébergement", "Restauration", "Événementiel", "Loisirs"),
        ("taux d'occupation / remplissage", "prix moyen", "marge par dossier ou par couvert", "saisonnalité", "taux d'annulation"),
        ("saisonnalité", "annulations", "dépendance aux plateformes de réservation", "coûts fixes élevés", "pénurie de personnel"),
        ("saison et météo", "événements et calendrier local", "taux de change", "situation géopolitique et sanitaire", "prix des transports"),
        {"customer": "voyageur / client", "supplier": "hôtel, transporteur, prestataire", "product": "séjour / prestation", "order": "réservation / dossier"},
        ("Quels sont vos mois forts et faibles ?", "Passez-vous par des plateformes de réservation ? Quelle commission ?", "Quels événements ou destinations influencent votre activité ?"),
    ),
    SectorGroup(
        "health", "Santé, social et services à la personne",
        ("Cabinet / clinique", "Pharmacie", "Services à domicile", "Établissement médico-social"),
        ("taux d'occupation / remplissage", "activité par acte", "délai de remboursement", "marge officine", "absentéisme"),
        ("retards de remboursement", "ruptures d'approvisionnement", "réglementation", "pénurie de personnel"),
        ("réglementation et tarifs de remboursement", "épidémies et saisonnalité", "pénurie de médicaments"),
        {"customer": "patient / bénéficiaire", "supplier": "fournisseur / laboratoire", "product": "acte / produit", "order": "prise en charge"},
        ("Quels organismes payent vos actes (assurance, mutuelle, patients) ?", "Quelle part de votre activité est réglementée ?"),
    ),
    SectorGroup(
        "logistics", "Transport et logistique",
        ("Transport routier", "Entreposage", "Transitaire / fret", "Messagerie"),
        ("coût au kilomètre / à la palette", "taux de remplissage", "ponctualité", "marge par transport", "délai d'encaissement"),
        ("hausse du carburant", "immobilisation de véhicules", "impayés", "retards et litiges", "dépendance à un gros chargeur"),
        ("prix du carburant et péages", "réglementation transport", "congestion et événements", "taux de fret"),
        {"customer": "chargeur / client", "supplier": "sous-traitant / transporteur", "product": "prestation de transport", "order": "ordre de transport"},
        ("Possédez-vous vos véhicules ou sous-traitez-vous ?", "Quelles lignes ou zones représentent votre activité ?"),
    ),
    SectorGroup(
        "agri", "Agriculture, pêche et ressources",
        ("Exploitation", "Coopérative", "Transformation", "Négoce de produits agricoles"),
        ("rendement", "coût de production", "prix de vente au cours", "stock", "subventions"),
        ("aléas climatiques", "volatilité des cours", "maladies et nuisibles", "dépendance aux intrants"),
        ("météo et climat", "cours mondiaux", "subventions et réglementation", "prix des engrais et de l'énergie"),
        {"customer": "acheteur", "supplier": "fournisseur d'intrants", "product": "récolte / produit", "order": "contrat de vente"},
        ("Quelles cultures ou productions ?", "À qui vendez-vous (coopérative, négoce, direct) et à quel prix ?"),
    ),
    SectorGroup(
        "finance", "Finance, assurance et holding",
        ("Banque / crédit", "Assurance / courtage", "Gestion d'actifs", "Holding", "Fintech"),
        ("encours", "rendement / marge d'intérêt", "sinistralité", "coût du risque", "fonds propres"),
        ("risque de crédit", "conformité réglementaire", "risque de marché", "fraude"),
        ("taux d'intérêt", "réglementation prudentielle", "marchés financiers"),
        {"customer": "client / assuré", "supplier": "partenaire", "product": "produit financier", "order": "dossier"},
        ("Quel type d'actifs ou de contrats gérez-vous ?", "Quelles réglementations vous encadrent ?"),
    ),
    SectorGroup(
        "public", "Association, éducation, public et médias",
        ("Association", "Établissement d'enseignement", "Collectivité", "Média / édition"),
        ("budget et subventions", "adhérents / bénéficiaires", "audience", "coût par action"),
        ("dépendance aux financements", "trésorerie tendue", "conformité", "recrutement de bénévoles"),
        ("subventions et appels d'offres", "calendrier scolaire / électoral", "audience et plateformes"),
        {"customer": "bénéficiaire / adhérent", "supplier": "fournisseur", "product": "programme / publication", "order": "convention / commande"},
        ("Quelles sont vos sources de financement ?", "Quels sont vos indicateurs de réussite ?"),
    ),
    SectorGroup(
        "generic", "Autre activité",
        ("Vente de produits", "Vente de services", "Mixte"),
        ("chiffre d'affaires", "marge", "trésorerie", "délai de paiement clients", "charges fixes"),
        ("impayés", "dépendance à un client ou fournisseur", "trésorerie tendue", "baisse de la marge"),
        ("conjoncture", "concurrence", "réglementation du secteur"),
        {"customer": "client", "supplier": "fournisseur", "product": "produit ou service", "order": "commande"},
        ("Décrivez en quelques phrases ce que vous vendez et à qui.", "Qu'est-ce qui fait gagner ou perdre de l'argent dans votre activité ?"),
    ),
]}

# (key, label, group)
SECTORS: list[tuple[str, str, str]] = [
    ("negoce_b2b", "Négoce / distribution B2B", "trading"),
    ("negoce_electronique", "Négoce de composants et matériel électronique", "trading"),
    ("negoce_matieres", "Négoce de matières premières", "trading"),
    ("import_export", "Import-export", "trading"),
    ("grossiste_alimentaire", "Grossiste alimentaire", "trading"),
    ("distribution_technique", "Distribution technique et fournitures industrielles", "trading"),
    ("courtage_commodites", "Courtage / broker (commodités, équipements)", "trading"),
    ("commerce_detail", "Commerce de détail (magasin)", "retail"),
    ("ecommerce", "E-commerce / vente en ligne", "retail"),
    ("marketplace", "Marketplace / plateforme", "retail"),
    ("mode_luxe", "Mode, habillement et luxe", "retail"),
    ("industrie_generale", "Industrie manufacturière", "manufacturing"),
    ("electronique_electrique", "Électronique et électrique (fabrication)", "manufacturing"),
    ("agroalimentaire", "Agroalimentaire", "manufacturing"),
    ("chimie_plasturgie", "Chimie, plasturgie, matériaux", "manufacturing"),
    ("metallurgie_mecanique", "Métallurgie et mécanique", "manufacturing"),
    ("automobile", "Automobile et équipementiers", "manufacturing"),
    ("aeronautique_defense", "Aéronautique et défense", "manufacturing"),
    ("energie", "Énergie et services collectifs", "manufacturing"),
    ("pharma_industrie", "Pharmaceutique et dispositifs médicaux", "manufacturing"),
    ("textile_fabrication", "Textile et ameublement (fabrication)", "manufacturing"),
    ("btp", "BTP / construction", "construction"),
    ("promotion_immobiliere", "Promotion immobilière", "construction"),
    ("agence_immobiliere", "Agence immobilière, gestion locative, syndic", "construction"),
    ("architecture_ingenierie", "Architecture, ingénierie, bureau d'études", "construction"),
    ("conseil", "Conseil et services aux entreprises", "services"),
    ("marketing_communication", "Agence marketing et communication", "services"),
    ("cabinet_comptable_juridique", "Cabinet comptable, juridique, audit", "services"),
    ("recrutement_interim", "Recrutement et intérim", "services"),
    ("formation", "Formation professionnelle", "services"),
    ("saas", "Éditeur de logiciel / SaaS", "tech"),
    ("esn", "ESN / services informatiques", "tech"),
    ("telecom", "Télécoms et réseaux", "tech"),
    ("agence_voyage", "Agence de voyage / voyagiste", "hospitality"),
    ("hotellerie", "Hôtellerie et hébergement", "hospitality"),
    ("restauration", "Restauration et traiteur", "hospitality"),
    ("evenementiel", "Événementiel et congrès", "hospitality"),
    ("sport_loisirs", "Sport et loisirs", "hospitality"),
    ("sante_cabinet", "Cabinet médical, clinique, laboratoire", "health"),
    ("pharmacie", "Pharmacie", "health"),
    ("services_personne", "Services à la personne et social", "health"),
    ("transport_routier", "Transport routier et messagerie", "logistics"),
    ("logistique_entreposage", "Logistique et entreposage", "logistics"),
    ("transitaire_maritime", "Transitaire, fret maritime et aérien", "logistics"),
    ("agriculture", "Agriculture et élevage", "agri"),
    ("peche_aquaculture", "Pêche et aquaculture", "agri"),
    ("banque_assurance", "Banque, assurance, courtage", "finance"),
    ("holding_investissement", "Holding et investissement", "finance"),
    ("fintech", "Fintech et paiement", "finance"),
    ("association", "Association / ONG", "public"),
    ("education", "Éducation et enseignement", "public"),
    ("secteur_public", "Collectivité et secteur public", "public"),
    ("medias_edition", "Médias et édition", "public"),
    ("autre", "Autre (je le décris)", "generic"),
]

_SECTOR_BY_KEY = {key: (label, group) for key, label, group in SECTORS}

# Every business function a company can have watched. The AI always has all
# of them available; the company picks the ones that matter to it.
FUNCTIONS: list[tuple[str, str, str]] = [
    ("finance", "Finance et trésorerie", "Trésorerie, marge, rentabilité, financement"),
    ("accounting", "Comptabilité et fiscalité", "Écritures, TVA, clôtures, conformité comptable"),
    ("sales", "Ventes et clients", "Devis, commandes, clients, relances"),
    ("procurement", "Achats et fournisseurs", "Commandes d'achat, fournisseurs, prix d'achat"),
    ("supply_chain", "Stock et supply chain", "Stock, réceptions, livraisons, approvisionnement"),
    ("operations", "Production et opérations", "Production, qualité, maintenance, chantiers"),
    ("hr", "Ressources humaines et paie", "Équipe, absences, recrutement, paie"),
    ("marketing", "Marketing et acquisition", "Campagnes, site web, réseaux, leads"),
    ("customer_service", "Service client et support", "Réclamations, SAV, satisfaction"),
    ("legal", "Juridique et conformité", "Contrats, litiges, réglementation, RGPD"),
    ("it", "Informatique et données", "Outils, sécurité, accès, données"),
    ("strategy", "Direction et stratégie", "Objectifs, pilotage, croissance, risques"),
]


def sector_group(sector_key: str | None) -> SectorGroup:
    if sector_key and sector_key in _SECTOR_BY_KEY:
        return GROUPS[_SECTOR_BY_KEY[sector_key][1]]
    return GROUPS["generic"]


def sector_label(sector_key: str | None) -> str | None:
    return _SECTOR_BY_KEY[sector_key][0] if sector_key in _SECTOR_BY_KEY else None


def is_known_sector(sector_key: str) -> bool:
    return sector_key in _SECTOR_BY_KEY
