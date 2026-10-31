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


# Multiple-choice answers the AI starts from (V3 configuration). The company
# ticks what applies; free text is only an optional precision. Choices are
# specific to the kind of business: every company already knows we help it
# earn more and save time, so the questions go to what is particular to it.
QCM_TITLES = {
    "goals": ("Ce que vous voulez améliorer", "Cochez tout ce qui compte pour vous."),
    "problems": ("Ce qui vous freine aujourd'hui", "Cochez ce que vous reconnaissez, même si vous n'êtes pas sûr de l'ampleur."),
    "externals": ("Ce qui, hors de l'entreprise, influence votre résultat", "Cochez ce qui pèse sur votre activité."),
}

QCM: dict[str, dict[str, tuple[str, ...]]] = {
    "trading": {
        "goals": ("Augmenter ma marge sur chaque vente", "Savoir quelles références et quels clients me rapportent vraiment", "Mieux négocier avec mes fournisseurs", "Réduire le stock qui dort", "Encaisser mes clients plus vite", "Trouver de nouveaux clients ou débouchés", "Anticiper les hausses de prix avant d'acheter"),
        "problems": ("Mes marges baissent sans que je comprenne pourquoi", "Je dépends de quelques fournisseurs ou clients", "Du stock dort ou je suis en rupture", "Des clients paient en retard ou pas du tout", "Je n'ai pas de vue claire de ma trésorerie", "Je ressaisis des données entre mes outils", "Mes prix d'achat changent plus vite que mes prix de vente"),
        "externals": ("Les prix des produits que j'achète", "Les taux de change", "Les droits de douane et la réglementation import-export", "Les pénuries et délais des fabricants", "Les saisons et cycles d'achat de mes clients", "Les salons et événements du secteur", "La concurrence et les prix du marché"),
    },
    "retail": {
        "goals": ("Faire dépenser plus à chaque client", "Savoir quels produits font ma marge", "Réduire invendus et ruptures", "Fidéliser mes clients", "Payer moins cher pour attirer un client", "Gagner du temps sur la gestion quotidienne"),
        "problems": ("Je vends mais je ne sais pas ce que je gagne vraiment", "Trop de retours ou d'invendus", "Je dépends d'une plateforme ou de la publicité", "Mes stocks ne sont pas à jour", "Mes ventes sont très irrégulières", "Je gère plusieurs canaux sans vue d'ensemble"),
        "externals": ("Les soldes et les fêtes", "Le coût de la publicité en ligne", "Les concurrents en ligne", "Le pouvoir d'achat et les tendances", "La météo", "Les délais de livraison de mes fournisseurs"),
    },
    "manufacturing": {
        "goals": ("Réduire mon coût de revient", "Livrer plus vite et à l'heure", "Réduire rebuts et non-qualité", "Mieux utiliser mes machines", "Sécuriser mes approvisionnements", "Gagner de nouveaux clients ou donneurs d'ordre"),
        "problems": ("Pannes ou arrêts de production", "Matières premières qui montent", "Retards de mes fournisseurs", "Qualité irrégulière ou retours clients", "Je ne connais pas mon vrai coût par produit", "Je dépends d'un gros client"),
        "externals": ("Le prix des matières premières et de l'énergie", "Les normes et la réglementation", "Les délais de mes fournisseurs", "Les cycles de la demande de mes clients", "Les taux de change", "La pénurie de main-d'œuvre qualifiée"),
    },
    "construction": {
        "goals": ("Suivre la rentabilité de chaque chantier ou projet", "Encaisser plus vite", "Remplir mon carnet de commandes", "Réduire les dérives de coûts", "Mieux choisir mes sous-traitants", "Gagner du temps sur l'administratif"),
        "problems": ("Des chantiers dépassent leur budget", "Retards et pénalités", "Paiements tardifs ou retenues de garantie", "Difficile de planifier la charge", "Hausse du prix des matériaux", "Dossiers et documents dispersés"),
        "externals": ("Le prix des matériaux", "Les taux d'intérêt et le crédit", "La réglementation et les normes", "La météo et la saison", "Les appels d'offres et marchés publics", "La disponibilité des artisans et sous-traitants"),
    },
    "services": {
        "goals": ("Mieux occuper mes équipes", "Augmenter mon taux journalier", "Savoir quelles missions sont rentables", "Facturer et encaisser plus vite", "Développer le revenu récurrent", "Moins dépendre de quelques clients"),
        "problems": ("Le temps passé dépasse ce que je facture", "Quelques clients font l'essentiel de mon chiffre d'affaires", "Mon équipe est sous ou sur-occupée", "Mes factures sont payées en retard", "Je prévois mal les mois à venir", "Recruter ou garder les talents est difficile"),
        "externals": ("La conjoncture de mes clients", "La concurrence", "La pénurie de talents", "Les évolutions réglementaires", "Les budgets de mes clients (début et fin d'année)", "L'IA et les nouveaux outils qui changent le métier"),
    },
    "tech": {
        "goals": ("Faire croître le revenu récurrent", "Réduire le départ de clients (churn)", "Baisser le coût pour gagner un client", "Maîtriser les coûts cloud", "Mieux occuper mes équipes", "Préparer un financement ou une levée"),
        "problems": ("Des clients partent trop vite", "Je dépends d'un gros client", "Mes coûts cloud explosent", "La dette technique ralentit le produit", "Je manque de visibilité sur ma trésorerie", "Recruter est difficile"),
        "externals": ("La concurrence", "Le coût de l'infrastructure", "Le RGPD et la réglementation des données", "Le marché du financement", "Les cycles budgétaires de mes clients", "L'évolution rapide de la technologie (IA)"),
    },
    "hospitality": {
        "goals": ("Remplir davantage aux périodes creuses", "Augmenter mon prix moyen", "Réduire les annulations", "Moins dépendre des plateformes de réservation", "Mieux anticiper la saison", "Fidéliser mes clients"),
        "problems": ("Forte saisonnalité", "Annulations de dernière minute", "Commissions des plateformes", "Coûts fixes élevés", "Manque de personnel", "Prix d'achat qui montent chez mes fournisseurs"),
        "externals": ("La saison et la météo", "Les événements et congrès de ma destination", "Les taux de change", "La situation géopolitique ou sanitaire", "Le prix des transports et du carburant", "Les avis en ligne"),
    },
    "health": {
        "goals": ("Mieux remplir mon agenda ou mes capacités", "Réduire les délais de paiement et de remboursement", "Suivre ma rentabilité par activité", "Gagner du temps sur l'administratif", "Sécuriser mes approvisionnements", "Mieux gérer mes équipes"),
        "problems": ("Retards de remboursement", "Charge administrative lourde", "Ruptures d'approvisionnement", "Absentéisme ou manque de personnel", "Des règles qui changent souvent", "Peu de visibilité sur ma rentabilité"),
        "externals": ("Les tarifs et la réglementation", "Les épidémies et la saisonnalité", "Les pénuries de produits", "Les évolutions des remboursements", "La démographie locale", "La concurrence locale"),
    },
    "logistics": {
        "goals": ("Mieux remplir mes véhicules ou entrepôts", "Réduire mon coût par trajet", "Livrer à l'heure", "Encaisser plus vite", "Gagner de nouveaux chargeurs", "Moins dépendre d'un gros client"),
        "problems": ("Le carburant qui monte", "Des véhicules immobilisés", "Retards et litiges", "Trop de retours à vide", "Des impayés", "Des sous-traitants peu fiables"),
        "externals": ("Le prix du carburant et des péages", "La réglementation du transport", "La météo et le trafic", "Les taux de fret", "Les grèves et événements", "La saisonnalité de mes clients"),
    },
    "agri": {
        "goals": ("Mieux vendre ma production", "Réduire mes coûts de production", "Améliorer mes rendements", "Sécuriser ma trésorerie entre deux récoltes", "Profiter des aides disponibles", "Diversifier mes débouchés"),
        "problems": ("Aléas climatiques", "Prix de vente trop bas", "Coût des intrants qui monte", "Maladies et nuisibles", "Trésorerie irrégulière", "Démarches administratives lourdes"),
        "externals": ("La météo et le climat", "Les cours mondiaux", "Les subventions et la réglementation", "Le prix des engrais et de l'énergie", "La demande des acheteurs", "La concurrence étrangère"),
    },
    "finance": {
        "goals": ("Accroître mes encours ou ma collecte", "Réduire le risque", "Rester conforme à la réglementation", "Améliorer mon rendement", "Fidéliser mes clients", "Traiter les dossiers plus vite"),
        "problems": ("Des dossiers lents à traiter", "Risque de crédit ou d'impayés", "Exigences réglementaires lourdes", "Fraude", "Des données dispersées", "Des marges qui se réduisent"),
        "externals": ("Les taux d'intérêt", "La réglementation", "Les marchés financiers", "La concurrence des fintech", "La conjoncture économique", "Les évolutions fiscales"),
    },
    "public": {
        "goals": ("Sécuriser mes financements", "Toucher plus de bénéficiaires ou d'adhérents", "Mieux suivre mon budget", "Gagner du temps sur l'administratif", "Mieux prouver mon impact", "Diversifier mes ressources"),
        "problems": ("Je dépends de peu de financeurs", "Trésorerie tendue", "Suivi administratif lourd", "Difficulté à recruter bénévoles ou équipe", "Peu de visibilité sur les résultats", "Appels à projets difficiles à suivre"),
        "externals": ("Les subventions et appels d'offres", "Le calendrier scolaire ou électoral", "L'audience et les réseaux", "La réglementation", "La conjoncture", "Les partenariats"),
    },
    "generic": {
        "goals": ("Augmenter mon chiffre d'affaires", "Améliorer ma marge", "Mieux maîtriser ma trésorerie", "Encaisser plus vite", "Réduire mes coûts", "Gagner du temps sur l'administratif", "Mieux connaître mes clients"),
        "problems": ("Je ne sais pas ce qui me rapporte vraiment", "Des clients paient en retard", "Ma trésorerie est difficile à prévoir", "Je dépends d'un client ou d'un fournisseur", "Trop de temps perdu en tâches manuelles", "Mes données sont éparpillées dans plusieurs outils"),
        "externals": ("La conjoncture", "La concurrence", "La réglementation", "La saison", "Les prix de mes fournisseurs", "Les taux de change"),
    },
}


def qcm_for(group_key: str) -> dict[str, tuple[str, ...]]:
    return QCM.get(group_key, QCM["generic"])
