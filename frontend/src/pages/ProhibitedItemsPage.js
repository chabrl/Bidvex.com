/**
 * ProhibitedItemsPage — iter214 P5
 *
 * Public, bilingual EN+FR page listing categories of items that may NOT be
 * sold on BidVex. Linked from:
 *   - Footer
 *   - Listing-creation page (guidelines section)
 *   - All listing-rejection emails
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldAlert, Ban } from 'lucide-react';

const CATEGORIES = [
  {
    id: 1, key: 'drugs',
    title_en: 'Controlled Substances & Drugs',
    title_fr: 'Substances contrôlées et drogues',
    items_en: [
      'Illegal drugs: cannabis (outside licensed channels), cocaine, heroin, methamphetamine, fentanyl, MDMA, psilocybin, LSD, ketamine, opioids, crack cocaine',
      'Drug paraphernalia: pipes, bongs, syringes (non-medical), rolling papers marketed for drugs',
      'Prescription medications (Rx): OxyContin, Adderall, Xanax, Percocet, Ritalin, Ozempic — anything requiring a prescription under Canada\'s Controlled Drugs and Substances Act',
      'Over-the-counter medication in suspicious bulk quantities',
      'Dietary supplements making medical / drug claims',
      'Kratom, khat, synthetic cannabinoids, bath salts',
    ],
    items_fr: [
      'Drogues illégales : cannabis (hors canaux autorisés), cocaïne, héroïne, méthamphétamine, fentanyl, MDMA, psilocybine, LSD, kétamine, opioïdes, crack',
      "Accessoires liés aux drogues : pipes, bongs, seringues (non médicales), papiers à rouler vendus pour la drogue",
      "Médicaments sur ordonnance : OxyContin, Adderall, Xanax, Percocet, Ritalin, Ozempic — tout médicament nécessitant une ordonnance selon la Loi réglementant certaines drogues et autres substances",
      'Médicaments en vente libre en quantités suspectes',
      'Compléments alimentaires aux allégations médicales / pharmaceutiques',
      'Kratom, khat, cannabinoïdes synthétiques, sels de bain',
    ],
  },
  {
    id: 2, key: 'weapons',
    title_en: 'Weapons & Dangerous Items',
    title_fr: 'Armes et objets dangereux',
    items_en: [
      'Firearms (handguns, rifles, shotguns, assault, prohibited under Canada Firearms Act)',
      'Firearm parts: barrels, suppressors, illegal capacity magazines, ghost-gun components',
      'Ammunition: bullets, cartridges, explosive charges',
      'Illegal edged weapons: switchblades, gravity / butterfly knives, brass knuckles, push daggers',
      'Explosive devices: grenades, IEDs, commercial fireworks',
      'Prohibited weapons under Criminal Code s.84: nunchucks, morning stars, metal-knuckle rings',
      'Tasers, stun guns (restricted in most provinces)',
      'Crossbows (restricted — verify provincial law)',
      'Pepper spray / bear spray when marketed as a weapon',
    ],
    items_fr: [
      "Armes à feu (pistolets, fusils, fusils de chasse, armes d'assaut, armes prohibées en vertu de la Loi sur les armes à feu)",
      "Pièces d'armes à feu : canons, silencieux, chargeurs à capacité illégale, composants d'armes fantômes",
      'Munitions : balles, cartouches, charges explosives',
      "Armes blanches illégales : couteaux à cran d'arrêt, couteaux à gravité ou papillon, poings américains",
      'Engins explosifs : grenades, EEI, feux d\'artifice commerciaux',
      "Armes prohibées en vertu de l'article 84 du Code criminel : nunchakus, fléau d'armes, bagues à pointes métalliques",
      'Pistolets paralysants (interdits dans la plupart des provinces)',
      'Arbalètes (sous réserve de la loi provinciale)',
      "Gaz poivré / vaporisateur d'ours s'il est commercialisé comme arme",
    ],
  },
  {
    id: 3, key: 'vehicles_wrong',
    title_en: 'Motor Vehicles (Wrong Section)',
    title_fr: 'Véhicules motorisés (mauvaise section)',
    items_en: [
      'Cars, trucks, SUVs, motorcycles, ATVs, snowmobiles, boats, RVs, trailers, heavy equipment listed anywhere other than the Vehicle Auctions section',
      'Vehicle VINs or titles listed independently',
    ],
    items_fr: [
      "Voitures, camions, VUS, motos, VTT, motoneiges, bateaux, VR, remorques, équipement lourd listés en dehors de la section Enchères de véhicules",
      "NIV ou titres de véhicule listés séparément",
    ],
  },
  {
    id: 4, key: 'financial_fraud',
    title_en: 'Financial Fraud & Schemes',
    title_fr: "Fraude financière et stratagèmes",
    items_en: [
      'Counterfeit currency, fake banknotes, coin forgeries',
      'Fake identification: passports, driver\'s licences, SIN cards, health cards, immigration documents',
      'Fraudulent investment schemes, Ponzi materials',
      'Unauthorized gift cards or card numbers',
      'Stolen financial instruments: cheques, credit cards',
      'Credit-card skimmers, point-of-sale fraud devices',
      'Academic fraud: essays, exams, credentials for sale',
    ],
    items_fr: [
      "Monnaie contrefaite, faux billets, fausses pièces",
      "Fausses pièces d'identité : passeports, permis de conduire, cartes NAS, cartes santé, documents d'immigration",
      "Stratagèmes d'investissement frauduleux, matériel Ponzi",
      'Cartes-cadeaux ou numéros de carte non autorisés',
      'Instruments financiers volés : chèques, cartes de crédit',
      'Skimmers de cartes, dispositifs de fraude au point de vente',
      "Fraude académique : essais, examens, diplômes en vente",
    ],
  },
  {
    id: 5, key: 'stolen',
    title_en: 'Stolen & Illegal Goods',
    title_fr: 'Biens volés et illégaux',
    items_en: [
      'Goods with removed serial numbers (presumed stolen)',
      'Catalytic converters (major theft item in Canada)',
      'Stolen electronics (no proof of ownership)',
      'Goods obtained via break-and-enter',
      'Any listing implying the item was illegally obtained',
    ],
    items_fr: [
      "Articles dont le numéro de série a été retiré (présumés volés)",
      "Convertisseurs catalytiques (article fréquemment volé au Canada)",
      "Électronique volée (sans preuve de propriété)",
      'Biens obtenus par effraction',
      "Toute annonce laissant entendre que l'article a été obtenu illégalement",
    ],
  },
  {
    id: 6, key: 'human_animal',
    title_en: 'Human & Animal Exploitation',
    title_fr: 'Exploitation humaine et animale',
    items_en: [
      'Human remains, organs, tissue, blood products',
      'Human-trafficking materials or services',
      'Any child-exploitation material — zero tolerance',
      'Endangered species products: ivory, rhino horn, tiger parts, shark fin, CITES-listed specimens',
      'Live animals from illegal breeding operations',
      'Animal-fighting equipment (cockfighting, dogfighting)',
    ],
    items_fr: [
      "Restes humains, organes, tissus, produits sanguins",
      "Matériel ou services de traite des personnes",
      "Tout matériel d'exploitation d'enfants — tolérance zéro",
      "Produits d'espèces menacées : ivoire, corne de rhinocéros, parties de tigre, aileron de requin, spécimens CITES",
      "Animaux vivants issus d'élevages illégaux",
      "Équipement de combats d'animaux (coqs, chiens)",
    ],
  },
  {
    id: 7, key: 'cyber',
    title_en: 'Digital & Cyber Threats',
    title_fr: 'Menaces numériques et cybernétiques',
    items_en: [
      'Malware, ransomware, spyware, keyloggers',
      'Hacking tools, credential stealers, phishing kits',
      'Stolen personal data: databases, login credentials',
      'Fake social-media followers, bots, engagement fraud',
      'Cheating software for games or platforms',
      'Unauthorized software license keys',
      'Deepfake creation tools marketed for fraud',
    ],
    items_fr: [
      "Maliciels, rançongiciels, logiciels espions, enregistreurs de frappe",
      "Outils de piratage, voleurs d'identifiants, kits de hameçonnage",
      "Données personnelles volées : bases de données, identifiants",
      "Faux abonnés, robots, fraude d'engagement",
      "Logiciels de tricherie pour jeux ou plateformes",
      'Clés de licence logicielle non autorisées',
      "Outils de création de hypertrucages utilisés pour la fraude",
    ],
  },
  {
    id: 8, key: 'platform_bypass',
    title_en: 'Platform Bypass & Off-Site Payment Requests',
    title_fr: "Contournement de la plateforme et paiements hors site",
    items_en: [
      'Requests for off-platform e-transfers to personal accounts outside BidVex',
      'Cryptocurrency payments aimed at bypassing tracking',
      'Western Union / MoneyGram in a suspicious context',
      'Any attempt to conduct the transaction off-platform',
      'Fake "BidVex"-branded materials issued by non-BidVex parties',
    ],
    items_fr: [
      "Virements Interac vers des comptes personnels hors BidVex",
      "Paiements en cryptomonnaie destinés à contourner la traçabilité",
      "Western Union / MoneyGram dans un contexte suspect",
      "Toute tentative de conclure la transaction hors plateforme",
      "Faux documents arborant la marque « BidVex » émis par des tiers",
    ],
  },
  {
    id: 9, key: 'regulated',
    title_en: 'Regulated Products',
    title_fr: 'Produits réglementés',
    items_en: [
      'Tobacco products targeting minors or sold without licence',
      'Vaping products not from a licensed retailer',
      'Alcohol sold outside LCBO / SAQ rules',
      'Cannabis outside federal/provincial licensed channels',
      'Health-Canada-regulated medical devices without permit',
      'Pesticides not registered under Canada\'s PCPA',
    ],
    items_fr: [
      "Produits du tabac ciblant les mineurs ou vendus sans permis",
      "Produits de vapotage hors détaillant autorisé",
      "Alcool vendu hors des règles de la LCBO / SAQ",
      "Cannabis hors des canaux fédéraux / provinciaux",
      "Dispositifs médicaux réglementés par Santé Canada sans permis",
      "Pesticides non enregistrés en vertu de la LPA",
    ],
  },
  {
    id: 10, key: 'adult',
    title_en: 'Adult & Explicit Content',
    title_fr: 'Contenu adulte et explicite',
    items_en: [
      'Pornographic material of any kind',
      'Sexual services or escort listings',
      'Adult toys with explicit images or descriptions (legal/discreet listings may be allowed in the proper category)',
    ],
    items_fr: [
      "Matériel pornographique en tout genre",
      'Services sexuels ou annonces d\'escorte',
      "Jouets pour adultes avec images / descriptions explicites (annonces légales / discrètes acceptables dans la bonne catégorie)",
    ],
  },
];

const ProhibitedItemsPage = () => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-8" data-testid="prohibited-items-page">
      <div className="max-w-4xl mx-auto px-4 sm:px-6">
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-rose-100 dark:bg-rose-950/40 mb-3">
            <Ban className="h-7 w-7 text-rose-600" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-black tracking-tight">
            {isFr ? 'Articles interdits' : 'Prohibited Items'}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground max-w-2xl mx-auto">
            {isFr
              ? "Pour la sécurité de notre communauté et la conformité aux lois canadiennes, les catégories suivantes ne peuvent PAS être vendues sur BidVex. Les annonces enfreignant ces règles seront automatiquement retirées et les comptes pourront être suspendus."
              : 'For the safety of our community and compliance with Canadian law, the following categories may NOT be sold on BidVex. Listings violating these rules will be automatically removed and accounts may be suspended.'}
          </p>
        </div>

        <div className="space-y-4">
          {CATEGORIES.map((cat) => (
            <div
              key={cat.id}
              className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5"
              data-testid={`prohibited-category-${cat.key}`}
            >
              <h2 className="font-bold text-lg flex items-center gap-2 mb-1">
                <span className="inline-flex items-center justify-center h-7 w-7 rounded-full bg-rose-100 text-rose-700 text-xs font-bold">
                  {cat.id}
                </span>
                {isFr ? cat.title_fr : cat.title_en}
              </h2>
              <p className="text-xs text-muted-foreground mb-3 italic">
                {isFr ? cat.title_en : cat.title_fr}
              </p>
              <ul className="space-y-1.5 text-sm">
                {(isFr ? cat.items_fr : cat.items_en).map((item, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-rose-500 flex-shrink-0 mt-0.5">●</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-10 p-4 rounded-2xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 flex items-start gap-3">
          <ShieldAlert className="h-5 w-5 text-amber-700 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-900 dark:text-amber-200">
            {isFr
              ? "Cette liste n'est pas exhaustive. BidVex se réserve le droit de retirer toute annonce jugée inappropriée, illégale ou dangereuse, à sa seule discrétion. Toute violation peut entraîner la suspension ou la suppression définitive de votre compte."
              : 'This list is not exhaustive. BidVex reserves the right to remove any listing deemed inappropriate, illegal, or dangerous at its sole discretion. Violations may result in suspension or permanent removal of your account.'}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ProhibitedItemsPage;
