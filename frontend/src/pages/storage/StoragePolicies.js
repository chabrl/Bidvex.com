import React from 'react';

import { useTranslation } from 'react-i18next';
import { Card } from '../../components/ui/card';
import { ArrowLeft } from 'lucide-react';
import StorageFooterBanner from './StorageFooterBanner';
import { LangLink } from '../../components/LangLink';

// Generic bilingual section — renders only the active language based on i18n.
const Section = ({ title_en, title_fr, body_en, body_fr, isFr }) => (
  <div className="mb-6">
    <h3 className="font-bold text-lg mb-3">{isFr ? title_fr : title_en}</h3>
    <div className="space-y-3 text-sm leading-relaxed">
      <p>{isFr ? body_fr : body_en}</p>
    </div>
  </div>
);

const PageHeader = ({ titleEn, titleFr, isFr }) => (
  <h1 className="text-3xl font-bold mb-6">{isFr ? titleFr : titleEn}</h1>
);

const BackLink = ({ isFr }) => (
  <LangLink to="/storage-auctions/browse" className="inline-flex items-center text-sm text-blue-600 hover:underline mb-3">
    <ArrowLeft className="h-3.5 w-3.5 mr-1" /> {isFr ? 'Retour aux enchères' : 'Back to auctions'}
  </LangLink>
);


export const HowItWorks = () => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="storage-how-it-works">
      <div className="max-w-3xl mx-auto px-4">
        <BackLink isFr={isFr} />
        <PageHeader
          titleEn="How Storage Unit Auctions Work on BidVex"
          titleFr="Comment fonctionnent les enchères d'unités d'entreposage sur BidVex"
          isFr={isFr}
        />
        <Card className="p-6">
          <Section isFr={isFr}
            title_en="1. What is a storage unit auction?"
            title_fr="1. Qu'est-ce qu'une enchère d'unité d'entreposage ?"
            body_en="Storage unit auctions occur when a tenant stops paying rent on their storage unit and cannot be reached by the facility. After following the required legal notification process, the facility lists the unit's contents for public auction. You bid on the contents of the unit without being able to enter it — based on photos and video only. Note: BidVex charges its platform fee to the facility, not to you as the buyer."
            body_fr="Les enchères d'unités d'entreposage ont lieu lorsqu'un locataire cesse de payer son loyer et ne peut pas être contacté par l'établissement. Après avoir suivi le processus légal de notification requis, l'établissement liste le contenu de l'unité aux enchères publiques. Vous enchérissez sur le contenu de l'unité sans pouvoir y entrer — en vous basant uniquement sur des photos et vidéos. Note : BidVex facture ses frais de plateforme à l'établissement, et non à vous en tant qu'acheteur."
          />
          <Section isFr={isFr}
            title_en="2. Proxy Bidding Explained"
            title_fr="2. Enchères par procuration expliquées"
            body_en="Every bid you place is a maximum bid. The system automatically bids on your behalf up to your maximum, increasing by $10 increments only as needed. You only ever pay the minimum amount required to win. If another bidder's maximum exceeds yours, you will be immediately notified by email."
            body_fr="Chaque offre que vous placez est une offre maximale. Le système enchérit automatiquement en votre nom jusqu'à votre maximum, en augmentant par tranches de 10 $ seulement au besoin. Vous ne payez jamais que le montant minimum requis pour gagner. Si le maximum d'un autre enchérisseur dépasse le vôtre, vous serez immédiatement notifié par courriel."
          />
          <Section isFr={isFr}
            title_en="3. Soft Close"
            title_fr="3. Fermeture progressive (soft close)"
            body_en="To ensure fairness, any bid placed in the final 2 minutes of an auction extends the auction by 2 minutes. This prevents last-second sniping and gives every bidder a fair opportunity to respond."
            body_fr="Pour assurer l'équité, toute offre placée dans les 2 dernières minutes d'une enchère prolonge l'enchère de 2 minutes. Cela empêche les offres de dernière seconde et donne à chaque enchérisseur une chance équitable de répondre."
          />
          <Section isFr={isFr}
            title_en="4. Platform Fees & Payment Methods"
            title_fr="4. Frais de plateforme et modes de paiement"
            body_en="BidVex charges a 5% platform commission to the storage facility — not to the buyer. Buyers always pay only the winning bid price. How the commission is collected depends on the payment method selected by the facility. Cash / Interac e-Transfer auctions: after winning, you pay the winning bid amount directly to the facility (cash at the facility or Interac e-Transfer to their registered email). BidVex separately charges the facility a 5% commission on the winning bid, plus applicable GST/QST. No BidVex fees are charged to buyers. Stripe payment auctions: after winning, you pay the winning bid amount via Stripe (credit or debit card). BidVex deducts its 5% commission plus applicable GST/QST from the facility's payout. You pay only the winning bid amount — no extra fees. In all cases, the buyer pays the winning bid price only. The 5% BidVex platform commission is always paid by the storage facility, never by the buyer."
            body_fr="BidVex perçoit une commission de plateforme de 5 % auprès de l'établissement de stockage — et non auprès de l'acheteur. Les acheteurs paient toujours uniquement le montant de l'enchère gagnante. La façon dont la commission est perçue dépend du mode de paiement choisi par l'établissement. Enchères en espèces ou virement Interac : après avoir remporté l'enchère, vous payez le montant directement à l'établissement (en espèces sur place ou par virement Interac à leur adresse courriel enregistrée). BidVex facture séparément à l'établissement une commission de 5 % sur l'enchère gagnante, plus la TPS/TVQ applicable. Aucun frais BidVex n'est facturé aux acheteurs. Enchères par paiement Stripe : après avoir remporté l'enchère, vous payez le montant via Stripe (carte de crédit ou de débit). BidVex déduit sa commission de 5 % plus la TPS/TVQ applicable du versement de l'établissement. Vous payez uniquement le montant de l'enchère — aucun frais supplémentaire. Dans tous les cas, l'acheteur paie uniquement le montant de l'enchère gagnante. La commission de plateforme de 5 % est toujours à la charge de l'établissement de stockage, jamais de l'acheteur."
          />
          <Section isFr={isFr}
            title_en="5. Payment Methods"
            title_fr="5. Modes de paiement"
            body_en="Accepted payment methods are set by each facility: Stripe (credit/debit card), cash paid directly at the facility, or Interac e-Transfer to the facility's registered email. Buyers pay only the winning bid. The facility is responsible for all BidVex platform fees. Payment must be completed within the timeline specified by the facility."
            body_fr="Les modes de paiement acceptés sont définis par chaque établissement : Stripe (carte de crédit ou de débit), espèces directement à l'établissement, ou virement Interac à l'adresse courriel enregistrée. Les acheteurs paient uniquement le montant de l'enchère gagnante. L'établissement est responsable de tous les frais de plateforme BidVex. Le paiement doit être complété dans le délai spécifié par l'établissement."
          />
          <Section isFr={isFr}
            title_en="6. Cleanup Rules"
            title_fr="6. Règles de nettoyage"
            body_en="Winners are responsible for completely emptying the storage unit by the deadline specified in the listing. Failure to empty the unit by the deadline forfeits your cleaning deposit and may result in account suspension. You must coordinate pickup directly with the facility manager. Treat facility staff with respect."
            body_fr="Les gagnants sont responsables de vider complètement l'unité d'entreposage avant la date limite spécifiée dans l'annonce. Le non-respect de cette date limite entraîne la perte de votre dépôt de nettoyage et peut entraîner la suspension de votre compte. Vous devez coordonner le ramassage directement avec le gestionnaire de la facilité. Traitez le personnel de la facilité avec respect."
          />
        </Card>
      </div>
      <StorageFooterBanner />
    </div>
  );
};

export const StorageTerms = () => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="storage-terms">
      <div className="max-w-3xl mx-auto px-4">
        <BackLink isFr={isFr} />
        <PageHeader
          titleEn="Storage Unit Auction Terms & Conditions"
          titleFr="Conditions générales des enchères d'unités d'entreposage"
          isFr={isFr}
        />
        <Card className="p-6">
          <Section isFr={isFr}
            title_en="Article 1 — Platform Role"
            title_fr="Article 1 — Rôle de la plateforme"
            body_en="BidVex is a technology platform and disclosed agent for storage facilities. BidVex is NOT an auctioneer. The actual auction and sale are conducted by the storage facility at their location. BidVex simply provides the online bidding platform. All bids placed on BidVex are final and cannot be revoked under any circumstances."
            body_fr="BidVex est une plateforme technologique et agent divulgué pour les facilités d'entreposage. BidVex N'EST PAS un encanteur. La vente aux enchères réelle est conduite par la facilité d'entreposage à son emplacement. BidVex fournit simplement la plateforme d'enchères en ligne. Toutes les offres placées sur BidVex sont finales et ne peuvent être révoquées en aucune circonstance."
          />
          <Section isFr={isFr}
            title_en="Article 2 — Lien Units"
            title_fr="Article 2 — Unités sous droit de rétention"
            body_en="Storage facilities are solely responsible for compliance with all provincial lien laws, tenant notification requirements, and legal auction procedures applicable in their province. BidVex accepts no liability for any claim arising from the sale of lien units."
            body_fr="Les facilités d'entreposage sont seules responsables du respect de toutes les lois provinciales sur les droits de rétention, des exigences de notification des locataires et des procédures légales d'enchères applicables dans leur province. BidVex n'accepte aucune responsabilité pour toute réclamation découlant de la vente d'unités sous droit de rétention."
          />
          <Section isFr={isFr}
            title_en="Article 3 — Buyer Obligations"
            title_fr="Article 3 — Obligations de l'acheteur"
            body_en="By placing a bid, you agree to: (a) complete payment within the facility's specified deadline; (b) empty the unit completely by the cleanup deadline; (c) coordinate pickup directly with the facility; (d) pay any applicable cleaning deposit; (e) accept the unit contents as-is with no returns or refunds; (f) comply with all applicable provincial laws."
            body_fr="En plaçant une offre, vous acceptez de : (a) compléter le paiement dans le délai spécifié par la facilité ; (b) vider complètement l'unité avant la date limite de nettoyage ; (c) coordonner le ramassage directement avec la facilité ; (d) payer tout dépôt de nettoyage applicable ; (e) accepter le contenu de l'unité tel quel, sans retours ni remboursements ; (f) respecter toutes les lois provinciales applicables."
          />
          <Section isFr={isFr}
            title_en="Article 4 — Platform Fees & Payment Methods"
            title_fr="Article 4 — Frais de plateforme et modes de paiement"
            body_en="BidVex charges a 5% platform commission to the storage facility — not to the buyer. Buyers always pay only the winning bid price. How the commission is collected depends on the payment method selected by the facility. Cash / Interac e-Transfer auctions: after winning, you pay the winning bid amount directly to the facility (cash at the facility or Interac e-Transfer to their registered email). BidVex separately charges the facility a 5% commission on the winning bid, plus applicable GST/QST. No BidVex fees are charged to buyers. Stripe payment auctions: after winning, you pay the winning bid amount via Stripe (credit or debit card). BidVex deducts its 5% commission plus applicable GST/QST from the facility's payout. You pay only the winning bid amount — no extra fees. In all cases, the buyer pays the winning bid price only. The 5% BidVex platform commission is always paid by the storage facility, never by the buyer."
            body_fr="BidVex perçoit une commission de plateforme de 5 % auprès de l'établissement de stockage — et non auprès de l'acheteur. Les acheteurs paient toujours uniquement le montant de l'enchère gagnante. La façon dont la commission est perçue dépend du mode de paiement choisi par l'établissement. Enchères en espèces ou virement Interac : après avoir remporté l'enchère, vous payez le montant directement à l'établissement (en espèces sur place ou par virement Interac à leur adresse courriel enregistrée). BidVex facture séparément à l'établissement une commission de 5 % sur l'enchère gagnante, plus la TPS/TVQ applicable. Aucun frais BidVex n'est facturé aux acheteurs. Enchères par paiement Stripe : après avoir remporté l'enchère, vous payez le montant via Stripe (carte de crédit ou de débit). BidVex déduit sa commission de 5 % plus la TPS/TVQ applicable du versement de l'établissement. Vous payez uniquement le montant de l'enchère — aucun frais supplémentaire. Dans tous les cas, l'acheteur paie uniquement le montant de l'enchère gagnante. La commission de plateforme de 5 % est toujours à la charge de l'établissement de stockage, jamais de l'acheteur."
          />
          <Section isFr={isFr}
            title_en="Article 5 — No Guarantees"
            title_fr="Article 5 — Aucune garantie"
            body_en="BidVex does not guarantee the contents, value, or condition of any storage unit. All sales are final. BidVex is not liable for any losses incurred during pickup, for the condition of items, or for any discrepancies between photos and actual contents."
            body_fr="BidVex ne garantit pas le contenu, la valeur ou l'état de toute unité d'entreposage. Toutes les ventes sont finales. BidVex n'est pas responsable des pertes subies lors du ramassage, de l'état des articles ou des écarts entre les photos et le contenu réel."
          />
          <Section isFr={isFr}
            title_en="Article 6 — Account Suspension"
            title_fr="Article 6 — Suspension du compte"
            body_en="The following actions will result in immediate account suspension: (a) failing to complete payment after winning; (b) failing to empty a unit by the cleanup deadline; (c) abusive behaviour toward facility staff; (d) attempting to revoke a placed bid; (e) providing false information during registration."
            body_fr="Les actions suivantes entraîneront une suspension immédiate du compte : (a) ne pas compléter le paiement après avoir gagné ; (b) ne pas vider une unité avant la date limite de nettoyage ; (c) comportement abusif envers le personnel de la facilité ; (d) tentative de révoquer une offre placée ; (e) fourniture de fausses informations lors de l'inscription."
          />
        </Card>
      </div>
      <StorageFooterBanner />
    </div>
  );
};

export const StorageForFacilities = () => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="storage-for-facilities">
      <div className="max-w-3xl mx-auto px-4">
        <BackLink isFr={isFr} />
        <PageHeader
          titleEn="List Your Storage Units on BidVex — Facility Guide"
          titleFr="Listez vos unités d'entreposage sur BidVex — Guide pour facilités"
          isFr={isFr}
        />
        <Card className="p-6">
          <Section isFr={isFr}
            title_en="1. Why BidVex?"
            title_fr="1. Pourquoi BidVex ?"
            body_en="BidVex is Canada's bilingual auction platform built for professional sellers. As a storage facility, you get: 5% commission only — we charge nothing to buyers; bilingual listings — reach French and English buyers across Canada; real-time bidding — proxy bidding drives higher final prices; soft-close protection — prevents sniping; photo and video support — showcase unit contents professionally; automated outbid notifications; secure payment options — Stripe, Cash, or E-Transfer."
            body_fr="BidVex est la plateforme d'enchères bilingue du Canada construite pour les vendeurs professionnels. En tant que facilité d'entreposage, vous obtenez : commission de 5 % seulement — nous ne facturons rien aux acheteurs ; annonces bilingues — rejoignez les acheteurs francophones et anglophones à travers le Canada ; enchères en temps réel — les enchères par procuration génèrent des prix finaux plus élevés ; protection soft-close ; support photos et vidéos ; notifications automatiques de surenchère ; options de paiement sécurisées — Stripe, comptant ou virement électronique."
          />
          <Section isFr={isFr}
            title_en="2. Commission Structure"
            title_fr="2. Structure des commissions"
            body_en="BidVex charges a flat 5% seller commission on the winning bid price plus applicable GST/QST — paid by the facility, never by the buyer. This is the only fee you pay. There is no monthly subscription fee to list storage units. How the commission is collected depends on your chosen payment method: cash / e-Transfer auctions are billed to your card on file after each sale; Stripe-payment auctions deduct the commission directly from your Stripe payout."
            body_fr="BidVex facture une commission vendeur fixe de 5 % sur le prix de l'enchère gagnante plus la TPS/TVQ applicable — à la charge de l'établissement, jamais de l'acheteur. C'est le seul frais que vous payez. Aucun abonnement mensuel n'est requis pour lister des unités d'entreposage. Le mode de perception dépend du mode de paiement choisi : les enchères en espèces ou virement Interac sont facturées à votre carte enregistrée après chaque vente ; les enchères Stripe déduisent la commission directement de votre versement Stripe."
          />
          <Section isFr={isFr}
            title_en="3. Your Responsibilities"
            title_fr="3. Vos responsabilités"
            body_en="As a listing facility, you are responsible for: (a) complying with all provincial lien laws and tenant notification requirements before listing; (b) accurately classifying each unit as lien or non-lien; (c) providing clear photos and video of unit contents; (d) setting a reasonable cleanup deadline for winners; (e) coordinating pickup with winning bidders; (f) collecting payment from winners on cash / e-Transfer auctions (BidVex does not collect on your behalf for these). On Stripe-payment auctions BidVex collects the hammer from the buyer and pays you out the net (after deducting the 5% commission + GST/QST); (g) collecting applicable provincial sales tax from buyers (BidVex only collects tax on its 5% commission)."
            body_fr="En tant qu'établissement listant, vous êtes responsable de : (a) respecter toutes les lois provinciales sur les droits de rétention et les exigences de notification des locataires avant de lister ; (b) classifier précisément chaque unité comme sous droit de rétention ou non ; (c) fournir des photos et vidéos claires du contenu de l'unité ; (d) fixer un délai de nettoyage raisonnable pour les gagnants ; (e) coordonner le ramassage avec les enchérisseurs gagnants ; (f) percevoir le paiement des gagnants sur les enchères en espèces ou virement Interac (BidVex ne perçoit pas en votre nom pour ces enchères). Sur les enchères payées par Stripe, BidVex perçoit l'enchère de l'acheteur et vous verse le net (après déduction de la commission de 5 % + TPS/TVQ) ; (g) percevoir la taxe de vente provinciale applicable des acheteurs (BidVex perçoit uniquement la taxe sur sa commission de 5 %)."
          />
        </Card>
      </div>
      <StorageFooterBanner />
    </div>
  );
};
