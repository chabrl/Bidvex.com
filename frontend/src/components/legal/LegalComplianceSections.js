import React from 'react';
import { AlertTriangle, Shield, Globe, Car, Cpu, Truck } from 'lucide-react';

/**
 * Bilingual Legal Compliance Sections
 * All sections render EN and FR simultaneously per Bill 96 / Loi 101.
 * Used by PrivacyEN/FR, TermsEN/FR, and DynamicLegalPage.
 */

const Divider = () => (
  <hr className="my-4 border-slate-200 dark:border-slate-700" />
);

// ─── Section 1.4: Vehicle Auctions — Privacy & Terms ──────────────────

export const VehicleAuctionLegalSection = () => (
  <section id="vehicle-auctions-opc" className="space-y-4 border-l-4 border-amber-400 pl-4">
    <h2 className="text-xl font-semibold flex items-center gap-2">
      <Car className="h-5 w-5 text-amber-600" />
      Vehicle Auctions — Platform Role &amp; OPC Compliance
    </h2>
    <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-300 space-y-3">
      <p>
        BidVex is a technology platform and auction facilitator only. BidVex is not a vendor, dealer, or commerçant de véhicules routiers. BidVex does not purchase, resell, take title to, or take physical or constructive possession of any vehicle listed on the platform. All vehicle sale contracts are formed exclusively and directly between the OPC-licensed seller and the winning buyer. BidVex's only financial relationship with the buyer is the collection of a platform facilitation fee of 2.5% of the hammer price. The vehicle purchase price is settled directly between buyer and seller outside of BidVex. Sellers listing vehicles on BidVex represent and warrant that they hold a valid, current OPC permit (permis de commerçant de véhicules routiers) issued by the Office de la protection du consommateur du Québec, and that they will comply with all obligations imposed by the Consumer Protection Act (L.R.Q. c. P-40.1) including but not limited to written contracts of sale, legal warranties, and disclosure of permit number to buyers.
      </p>
    </div>
    <Divider />
    <h2 className="text-xl font-semibold flex items-center gap-2">
      <Car className="h-5 w-5 text-amber-600" />
      Enchères de véhicules — Rôle de la plateforme et conformité OPC
    </h2>
    <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-300 space-y-3">
      <p>
        BidVex est une plateforme technologique et un facilitateur d'enchères uniquement. BidVex n'est pas un vendeur, un concessionnaire, ni un commerçant de véhicules routiers. BidVex n'achète pas, ne revend pas, ne détient pas le titre de propriété ni ne prend possession physique ou constructive d'aucun véhicule listé sur la plateforme. Tous les contrats de vente de véhicules sont formés exclusivement et directement entre le vendeur licencié OPC et l'acheteur gagnant. La seule relation financière de BidVex avec l'acheteur est la perception de frais de facilitation de plateforme de 2,5 % du prix d'adjudication. Le prix d'achat du véhicule est réglé directement entre l'acheteur et le vendeur en dehors de BidVex. Les vendeurs listant des véhicules sur BidVex déclarent et garantissent qu'ils détiennent un permis OPC valide et en vigueur (permis de commerçant de véhicules routiers) délivré par l'Office de la protection du consommateur du Québec, et qu'ils se conformeront à toutes les obligations imposées par la Loi sur la protection du consommateur (L.R.Q. c. P-40.1), notamment les contrats de vente écrits, les garanties légales et la divulgation de leur numéro de permis aux acheteurs.
      </p>
    </div>
  </section>
);


// ─── Section 2.2: AI Disclosure — Privacy Policy ─────────────────────

export const AIDisclosureLegalSection = () => (
  <section id="ai-disclosure" className="space-y-4 border-l-4 border-purple-400 pl-4">
    <h2 className="text-xl font-semibold flex items-center gap-2">
      <Cpu className="h-5 w-5 text-purple-600" />
      Automated Decision-Making and AI Processing
    </h2>
    <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-300 space-y-3">
      <p>
        BidVex uses artificial intelligence and automated processing systems for the following purposes: (1) customer support responses via AI concierge; (2) listing categorization and fraud signal detection; (3) bid anomaly detection. No automated system makes final binding decisions about account suspension or listing removal without human review. Users have the right to request human review of any automated decision that affects them by contacting <a href="mailto:privacy@bidvex.com" className="text-blue-600 hover:underline">privacy@bidvex.com</a>. This disclosure is made pursuant to Quebec Law 25 (Loi 25) and the Act to modernize legislative provisions as regards the protection of personal information.
      </p>
    </div>
    <Divider />
    <h2 className="text-xl font-semibold flex items-center gap-2">
      <Cpu className="h-5 w-5 text-purple-600" />
      Traitement automatisé et intelligence artificielle
    </h2>
    <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-300 space-y-3">
      <p>
        BidVex utilise des systèmes d'intelligence artificielle et de traitement automatisé aux fins suivantes : (1) réponses au support client via le concierge IA ; (2) catégorisation des annonces et détection des signaux de fraude ; (3) détection d'anomalies dans les enchères. Aucun système automatisé ne prend de décisions finales contraignantes concernant la suspension de compte ou le retrait d'annonce sans révision humaine. Les utilisateurs ont le droit de demander une révision humaine de toute décision automatisée les concernant en contactant <a href="mailto:privacy@bidvex.com" className="text-blue-600 hover:underline">privacy@bidvex.com</a>. Cette divulgation est faite conformément à la Loi 25 du Québec et à la Loi modernisant des dispositions législatives en matière de protection des renseignements personnels.
      </p>
    </div>
  </section>
);


// ─── Section 3: Cross-Border Compliance ──────────────────────────────

export const CrossBorderLegalSection = () => (
  <section id="cross-border-compliance" className="space-y-4 border-l-4 border-blue-400 pl-4">
    <h2 className="text-xl font-semibold flex items-center gap-2">
      <Globe className="h-5 w-5 text-blue-600" />
      Cross-Border Transactions — Buyer &amp; Seller Responsibility
    </h2>
    <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-300 space-y-3">
      <p>Import and export compliance is 100% the sole responsibility of the buyer and the seller. BidVex bears no responsibility whatsoever for customs clearance, duties, taxes, regulatory compliance, or the admissibility of any vehicle or equipment at any international border.</p>
      <p>For vehicles and equipment crossing the Canada–US border, buyers and sellers must independently ensure compliance with all of the following:</p>
      <ul className="list-disc pl-6 space-y-2">
        <li><strong>Canada Border Services Agency (CBSA):</strong> All vehicles must meet CBSA requirements. Commercial buyers must file Form B3; personal buyers must file Form B15. Applicable duties, GST/HST, and excise taxes are payable upon import.</li>
        <li><strong>Transport Canada / Registrar of Imported Vehicles (RIV):</strong> Road vehicles under 15 years of age must be registered with the RIV program and brought into compliance with Canadian Motor Vehicle Safety Standards. RIV fee: approximately $195–$325 CAD + applicable taxes.</li>
        <li><strong>Canadian Food Inspection Agency (CFIA):</strong> All used vehicles, farm equipment, tractors, excavators, and machinery must be free of soil, sand, plant matter, manure, and organic debris before crossing the border. Equipment that does not meet biosecurity standards will be refused entry.</li>
        <li><strong>US Customs and Border Protection (CBP):</strong> US-based sellers exporting to Canada must provide notice to CBP at least 72 hours prior to border crossing and file an Automated Export System (AES) declaration with the US Census Bureau.</li>
        <li><strong>Environment and Climate Change Canada:</strong> Imported vehicles must meet Canadian emissions standards. Vehicles that fail to comply may be denied entry.</li>
        <li><strong>Natural Resources Canada:</strong> Certain industrial and energy-using equipment must meet energy efficiency reporting requirements.</li>
        <li><strong>SAAQ (Quebec buyers):</strong> All road vehicles must be registered with the Société de l'assurance automobile du Québec and QST must be paid prior to use on Quebec roads.</li>
        <li><strong>RDPRM:</strong> Buyers are solely responsible for verifying that no prior security interests, unpaid loans, or registered rights exist against any vehicle or equipment prior to purchase via the Registre des droits personnels et réels mobiliers.</li>
      </ul>
      <p><strong>BidVex strongly recommends that all cross-border buyers engage a licensed customs broker prior to bidding. BidVex accepts no liability for refused entry, penalties, duties, or losses arising from failure to comply with any border or import/export requirement.</strong></p>
    </div>
    <Divider />
    <h2 className="text-xl font-semibold flex items-center gap-2">
      <Globe className="h-5 w-5 text-blue-600" />
      Transactions transfrontalières — Responsabilité de l'acheteur et du vendeur
    </h2>
    <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-300 space-y-3">
      <p>La conformité aux exigences d'importation et d'exportation est entièrement et exclusivement la responsabilité de l'acheteur et du vendeur. BidVex n'assume aucune responsabilité pour le dédouanement, les droits, les taxes, la conformité réglementaire ou l'admissibilité de tout véhicule ou équipement à tout poste frontière international.</p>
      <p>Pour les véhicules et équipements traversant la frontière Canada–États-Unis, les acheteurs et vendeurs doivent assurer indépendamment leur conformité avec tous les éléments suivants :</p>
      <ul className="list-disc pl-6 space-y-2">
        <li><strong>Agence des services frontaliers du Canada (ASFC) :</strong> Tous les véhicules doivent satisfaire aux exigences de l'ASFC. Les acheteurs commerciaux doivent soumettre le formulaire B3 ; les acheteurs personnels doivent soumettre le formulaire B15. Les droits applicables, la TPS/TVH et les taxes d'accise sont payables à l'importation.</li>
        <li><strong>Transports Canada / Registraire des véhicules importés (RVI) :</strong> Les véhicules routiers de moins de 15 ans doivent être enregistrés au programme RVI et mis en conformité avec les normes canadiennes de sécurité des véhicules automobiles. Frais RVI : environ 195 $ à 325 $ CAD + taxes applicables.</li>
        <li><strong>Agence canadienne d'inspection des aliments (ACIA) :</strong> Tous les véhicules usagés, équipements agricoles, tracteurs, excavatrices et machineries doivent être exempts de terre, de sable, de matières végétales, de fumier et de débris organiques avant de traverser la frontière. Tout équipement ne répondant pas aux normes de biosécurité sera refusé.</li>
        <li><strong>Bureau des douanes et de la protection des frontières des États-Unis (CBP) :</strong> Les vendeurs américains exportant vers le Canada doivent aviser le CBP au moins 72 heures avant le passage frontalier et soumettre une déclaration AES (Automated Export System) au Bureau du recensement des États-Unis.</li>
        <li><strong>Environnement et Changement climatique Canada :</strong> Les véhicules importés doivent respecter les normes canadiennes d'émissions. Les véhicules non conformes peuvent se voir refuser l'entrée.</li>
        <li><strong>Ressources naturelles Canada :</strong> Certains équipements industriels et énergétiques doivent satisfaire aux exigences de déclaration d'efficacité énergétique.</li>
        <li><strong>SAAQ (acheteurs québécois) :</strong> Tous les véhicules routiers doivent être immatriculés auprès de la Société de l'assurance automobile du Québec et la TVQ doit être payée avant utilisation sur les routes québécoises.</li>
        <li><strong>RDPRM :</strong> Les acheteurs sont seuls responsables de vérifier l'absence de sûretés antérieures, de prêts impayés ou de droits enregistrés contre tout véhicule ou équipement avant l'achat, via le Registre des droits personnels et réels mobiliers.</li>
      </ul>
      <p><strong>BidVex recommande vivement à tous les acheteurs transfrontaliers de faire appel à un courtier en douane licencié avant d'enchérir. BidVex n'accepte aucune responsabilité pour les refus d'entrée, les pénalités, les droits ou les pertes résultant du non-respect de toute exigence frontalière ou d'importation/exportation.</strong></p>
    </div>
  </section>
);


// ─── Section 4: CFIA Soil Rule Banner ────────────────────────────────

export const CFIASoilBanner = () => (
  <div className="border-2 border-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-5 space-y-3" data-testid="cfia-soil-banner">
    <div className="flex items-start gap-3">
      <AlertTriangle className="h-6 w-6 text-yellow-600 flex-shrink-0 mt-0.5" />
      <div className="space-y-3">
        <p className="font-bold text-yellow-800 dark:text-yellow-200">CFIA BIOSECURITY REQUIREMENT — SELLER ACTION REQUIRED</p>
        <p className="text-sm text-yellow-700 dark:text-yellow-300">
          If this equipment may be purchased by a cross-border buyer (Canada or US), you are legally required to ensure it is completely free of soil, sand, plant residue, manure, and organic material before transport.
        </p>
        <p className="text-sm text-yellow-700 dark:text-yellow-300">
          The Canadian Food Inspection Agency (CFIA) and Canada Border Services Agency (CBSA) will physically reject any machinery arriving at the border with visible soil or dirt. Rejection results in the buyer being responsible for cleaning costs, storage fees, and potential return shipping.
        </p>
        <p className="text-sm text-green-700 dark:text-green-300 font-medium">
          Seller Tip: Pressure-wash all equipment thoroughly before listing. Document the cleaning with photos and include them in your listing. This protects you from buyer disputes and border refusals.
        </p>
        <p className="text-xs text-yellow-600 dark:text-yellow-400 italic">This notice does not constitute legal advice. Consult a licensed customs broker for cross-border shipments.</p>
      </div>
    </div>
    <Divider />
    <div className="flex items-start gap-3">
      <AlertTriangle className="h-6 w-6 text-yellow-600 flex-shrink-0 mt-0.5" />
      <div className="space-y-3">
        <p className="font-bold text-yellow-800 dark:text-yellow-200">EXIGENCE DE BIOSÉCURITÉ DE L'ACIA — ACTION REQUISE DU VENDEUR</p>
        <p className="text-sm text-yellow-700 dark:text-yellow-300">
          Si cet équipement peut être acheté par un acheteur transfrontalier (Canada ou États-Unis), vous êtes légalement tenu de vous assurer qu'il est complètement exempt de terre, de sable, de résidus végétaux, de fumier et de matières organiques avant le transport.
        </p>
        <p className="text-sm text-yellow-700 dark:text-yellow-300">
          L'Agence canadienne d'inspection des aliments (ACIA) et l'Agence des services frontaliers du Canada (ASFC) refuseront physiquement toute machinerie arrivant à la frontière avec de la terre ou de la saleté visible. Un refus entraîne la responsabilité de l'acheteur pour les coûts de nettoyage, les frais d'entreposage et le retour potentiel de l'équipement.
        </p>
        <p className="text-sm text-green-700 dark:text-green-300 font-medium">
          Conseil au vendeur : Lavez tout l'équipement à pression avant de le lister. Documentez le nettoyage avec des photos et incluez-les dans votre annonce. Cela vous protège contre les litiges d'acheteurs et les refus frontaliers.
        </p>
        <p className="text-xs text-yellow-600 dark:text-yellow-400 italic">Cet avis ne constitue pas un conseil juridique. Consultez un courtier en douane licencié pour les expéditions transfrontalières.</p>
      </div>
    </div>
  </div>
);

// CFIA Soil Declaration Checkbox (bilingual)
export const CFIASoilCheckbox = ({ checked, onChange }) => (
  <label className="flex items-start gap-3 p-3 border-2 border-yellow-300 rounded-lg bg-yellow-50/50 dark:bg-yellow-900/10 cursor-pointer" data-testid="cfia-soil-checkbox">
    <input type="checkbox" checked={checked} onChange={onChange} className="mt-1 rounded border-yellow-400 text-yellow-600 focus:ring-yellow-500 h-4 w-4 flex-shrink-0" />
    <div className="text-sm space-y-1">
      <p className="text-slate-700 dark:text-slate-300">I confirm this equipment has been cleaned and is free of soil, organic material, and biological debris, or I will ensure this prior to transport.</p>
      <Divider />
      <p className="text-slate-700 dark:text-slate-300">Je confirme que cet équipement a été nettoyé et est exempt de terre, de matières organiques et de débris biologiques, ou je m'assurerai de ce fait avant le transport.</p>
    </div>
  </label>
);


// ─── Section 5: Cross-Border Advisory Panel ──────────────────────────

export const CrossBorderAdvisoryPanel = () => (
  <div className="border-2 border-blue-400 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-5 space-y-3" data-testid="cross-border-advisory">
    <div className="space-y-3">
      <p className="font-bold text-blue-800 dark:text-blue-200 flex items-center gap-2">
        <Globe className="h-5 w-5" /> CROSS-BORDER LISTING — IMPORTANT COMPLIANCE NOTICE
      </p>
      <p className="text-sm text-blue-700 dark:text-blue-300">This item is located outside Canada. Before bidding, you must understand and accept full responsibility for all import requirements.</p>
      <p className="text-sm font-medium text-blue-700 dark:text-blue-300">Required steps for Canadian buyers importing from the US:</p>
      <ul className="list-disc pl-6 text-sm text-blue-700 dark:text-blue-300 space-y-1">
        <li>CBSA clearance + Form B3 (commercial) or B15 (personal)</li>
        <li>RIV registration for road vehicles under 15 years old (~$195–325 CAD + tax)</li>
        <li>CFIA biosecurity inspection (equipment must be soil-free)</li>
        <li>GST/HST + applicable provincial taxes payable at border</li>
        <li>US seller must file AES declaration + 72-hr CBP notice</li>
      </ul>
      <p className="text-sm text-blue-700 dark:text-blue-300">BidVex does not arrange transport or customs clearance.<br/>Recommended: Hire a licensed Canadian customs broker before bidding.</p>
      <p className="text-xs font-semibold text-blue-800 dark:text-blue-200">By placing a bid on this listing, you confirm you have read and accept full responsibility for all import, customs, and compliance obligations.</p>
    </div>
    <Divider />
    <div className="space-y-3">
      <p className="font-bold text-blue-800 dark:text-blue-200 flex items-center gap-2">
        <Globe className="h-5 w-5" /> ANNONCE TRANSFRONTALIÈRE — AVIS DE CONFORMITÉ IMPORTANT
      </p>
      <p className="text-sm text-blue-700 dark:text-blue-300">Cet article est situé hors du Canada. Avant d'enchérir, vous devez comprendre et accepter l'entière responsabilité de toutes les exigences d'importation.</p>
      <p className="text-sm font-medium text-blue-700 dark:text-blue-300">Étapes requises pour les acheteurs canadiens important des États-Unis :</p>
      <ul className="list-disc pl-6 text-sm text-blue-700 dark:text-blue-300 space-y-1">
        <li>Dédouanement ASFC + formulaire B3 (commercial) ou B15 (personnel)</li>
        <li>Enregistrement RVI pour les véhicules routiers de moins de 15 ans (~195 $ à 325 $ CAD + taxes)</li>
        <li>Inspection de biosécurité de l'ACIA (l'équipement doit être exempt de terre)</li>
        <li>TPS/TVH + taxes provinciales applicables payables à la frontière</li>
        <li>Le vendeur américain doit soumettre une déclaration AES + avis CBP 72h</li>
      </ul>
      <p className="text-sm text-blue-700 dark:text-blue-300">BidVex n'organise pas le transport ni le dédouanement.<br/>Recommandé : Faites appel à un courtier en douane canadien licencié avant d'enchérir.</p>
      <p className="text-xs font-semibold text-blue-800 dark:text-blue-200">En plaçant une enchère sur cette annonce, vous confirmez avoir lu et accepter l'entière responsabilité de toutes les obligations d'importation, de douane et de conformité.</p>
    </div>
  </div>
);


// ─── Section 5: Cross-Border First-Bid Modal ─────────────────────────

export const CrossBorderBidModal = ({ isOpen, onAccept, onCancel }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm" data-testid="cross-border-bid-modal">
      <div className="bg-white dark:bg-slate-900 rounded-xl max-w-lg w-full mx-4 p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
        <CrossBorderAdvisoryPanel />
        <div className="mt-5 flex flex-col gap-3">
          <button
            onClick={onAccept}
            className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm transition-colors"
            data-testid="cross-border-accept-btn"
          >
            I Understand — Continue to Bid / Je comprends — Continuer à enchérir
          </button>
          <button
            onClick={onCancel}
            className="w-full py-3 px-4 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 rounded-lg font-medium text-sm transition-colors"
            data-testid="cross-border-cancel-btn"
          >
            Cancel / Annuler
          </button>
        </div>
      </div>
    </div>
  );
};
