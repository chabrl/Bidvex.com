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
            body_en="Storage unit auctions occur when a tenant stops paying rent on their storage unit and cannot be reached by the facility. After following the required legal notification process, the facility lists the unit's contents for public auction. You bid on the contents of the unit without being able to enter it — based on photos and video only. Note: BidVex charges the winning buyer a 5% buyer's premium on top of the hammer price. The facility is never charged."
            body_fr="Les enchères d'unités d'entreposage ont lieu lorsqu'un locataire cesse de payer son loyer et ne peut pas être contacté par l'établissement. Après avoir suivi le processus légal de notification requis, l'établissement liste le contenu de l'unité aux enchères publiques. Vous enchérissez sur le contenu de l'unité sans pouvoir y entrer — en vous basant uniquement sur des photos et vidéos. Note : BidVex facture à l'acheteur gagnant une prime acheteur de 5 % en plus du prix marteau. La facilité n'est jamais facturée."
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
            body_en="BidVex charges the WINNING BUYER a flat 5% buyer's premium on the hammer price — plus Stripe processing and applicable GST/QST on that premium. The storage facility is never charged by BidVex. Stripe-payment auctions: your card is charged for hammer + 5% buyer's premium + processing + tax at close. The facility receives the full hammer via Stripe payout. Cash / Interac e-Transfer auctions: you pay the hammer directly to the facility (cash at the facility or Interac e-Transfer to their registered email). BidVex separately charges your card on file for the 5% buyer's premium + processing + tax. Your bid deposit (if any) credits toward the buyer's-premium charge. In every case, the facility receives the full hammer price and is never invoiced by BidVex."
            body_fr="BidVex facture à l'ACHETEUR GAGNANT une prime acheteur fixe de 5 % sur le prix marteau — plus les frais de traitement Stripe et la TPS/TVQ applicable sur cette prime. L'établissement d'entreposage n'est jamais facturé par BidVex. Enchères par Stripe : votre carte est débitée du prix marteau + prime acheteur 5 % + traitement + taxes à la clôture. L'établissement reçoit le prix marteau complet via Stripe. Enchères en espèces ou par virement Interac : vous payez le prix marteau directement à l'établissement (en espèces sur place ou par virement Interac à leur adresse courriel enregistrée). BidVex facture séparément votre carte enregistrée pour la prime acheteur de 5 % + traitement + taxes. Votre dépôt d'enchère (le cas échéant) s'applique en crédit sur la prime acheteur. Dans tous les cas, l'établissement reçoit le prix marteau complet et n'est jamais facturé par BidVex."
          />
          <Section isFr={isFr}
            title_en="5. Payment Methods"
            title_fr="5. Modes de paiement"
            body_en="Accepted payment methods are set by each facility: Stripe (credit/debit card), cash paid directly at the facility, or Interac e-Transfer to the facility's registered email. Buyers always pay hammer + 5% buyer's premium + processing + tax. The facility is never charged BidVex fees. Payment must be completed within the timeline specified by the facility."
            body_fr="Les modes de paiement acceptés sont définis par chaque établissement : Stripe (carte de crédit ou de débit), espèces directement à l'établissement, ou virement Interac à l'adresse courriel enregistrée. Les acheteurs paient toujours le prix marteau + prime acheteur de 5 % + traitement + taxes. La facilité n'est jamais facturée par BidVex. Le paiement doit être complété dans le délai spécifié par l'établissement."
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
            body_en="BidVex charges the WINNING BUYER a flat 5% buyer's premium on the hammer price — plus Stripe processing and applicable GST/QST on that premium. The storage facility is never charged by BidVex. Stripe-payment auctions: the buyer's card is charged for hammer + 5% buyer's premium + processing + tax at close. The facility receives the full hammer via Stripe payout. Cash / Interac e-Transfer auctions: the buyer pays the hammer directly to the facility (cash at the facility or Interac e-Transfer to their registered email). BidVex separately charges the buyer's card on file for the 5% buyer's premium + processing + tax. In every case, the facility receives the full hammer price and is never invoiced by BidVex. The buyer's premium is always paid by the winning bidder, never by the facility."
            body_fr="BidVex facture à l'ACHETEUR GAGNANT une prime acheteur fixe de 5 % sur le prix marteau — plus les frais de traitement Stripe et la TPS/TVQ applicable sur cette prime. L'établissement d'entreposage n'est jamais facturé par BidVex. Enchères par Stripe : la carte de l'acheteur est débitée du prix marteau + prime acheteur 5 % + traitement + taxes à la clôture. L'établissement reçoit le prix marteau complet via Stripe. Enchères en espèces ou virement Interac : l'acheteur paie le prix marteau directement à l'établissement (en espèces sur place ou par virement Interac à leur adresse courriel enregistrée). BidVex facture séparément la carte enregistrée de l'acheteur pour la prime acheteur de 5 % + traitement + taxes. Dans tous les cas, l'établissement reçoit le prix marteau complet et n'est jamais facturé par BidVex. La prime acheteur est toujours à la charge de l'enchérisseur gagnant, jamais de la facilité."
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
            body_en="BidVex is Canada's bilingual auction platform built for professional sellers. As a storage facility, you get: zero platform fees — BidVex charges the winning buyer a 5% buyer's premium; the facility is never invoiced; keep the full hammer on every sale (paid via Stripe on Stripe-mode auctions, or directly from the buyer on cash / e-Transfer auctions); bilingual listings — reach French and English buyers across Canada; real-time bidding — proxy bidding drives higher final prices; soft-close protection — prevents sniping; photo and video support — showcase unit contents professionally; automated outbid notifications; secure payment options — Stripe, Cash, or E-Transfer."
            body_fr="BidVex est la plateforme d'enchères bilingue du Canada construite pour les vendeurs professionnels. En tant que facilité d'entreposage, vous obtenez : aucun frais de plateforme — BidVex facture à l'acheteur gagnant une prime acheteur de 5 % ; la facilité n'est jamais facturée ; conservez le prix marteau complet sur chaque vente (versé via Stripe pour les enchères Stripe, ou directement par l'acheteur pour les enchères en espèces ou virement Interac) ; annonces bilingues — rejoignez les acheteurs francophones et anglophones à travers le Canada ; enchères en temps réel — les enchères par procuration génèrent des prix finaux plus élevés ; protection soft-close ; support photos et vidéos ; notifications automatiques de surenchère ; options de paiement sécurisées — Stripe, comptant ou virement électronique."
          />
          <Section isFr={isFr}
            title_en="2. Fee Structure"
            title_fr="2. Structure des frais"
            body_en="You pay nothing to BidVex — ever. BidVex charges the WINNING BUYER a flat 5% buyer's premium on the hammer price (plus Stripe processing and applicable GST/QST on the premium). There is no seller commission, no listing fee, and no monthly subscription. On Stripe-mode auctions BidVex collects hammer + 5% buyer's premium from the buyer and remits the full hammer to your Stripe payout. On cash / e-Transfer auctions the buyer pays the hammer to you directly (offline) and BidVex separately charges the buyer's card for the 5% buyer's premium. You are never invoiced under any payment method."
            body_fr="Vous ne payez rien à BidVex — jamais. BidVex facture à l'ACHETEUR GAGNANT une prime acheteur fixe de 5 % sur le prix marteau (plus les frais de traitement Stripe et la TPS/TVQ applicable sur la prime). Aucune commission vendeur, aucun frais d'inscription, aucun abonnement mensuel. Pour les enchères Stripe, BidVex perçoit auprès de l'acheteur le prix marteau + prime acheteur 5 % et vous verse le prix marteau complet via Stripe. Pour les enchères en espèces ou virement Interac, l'acheteur vous paie le prix marteau directement (hors ligne) et BidVex facture séparément la carte de l'acheteur pour la prime acheteur de 5 %. Vous n'êtes jamais facturé, quel que soit le mode de paiement."
          />
          <Section isFr={isFr}
            title_en="3. Your Responsibilities"
            title_fr="3. Vos responsabilités"
            body_en="As a listing facility, you are responsible for: (a) complying with all provincial lien laws and tenant notification requirements before listing; (b) accurately classifying each unit as lien or non-lien; (c) providing clear photos and video of unit contents; (d) setting a reasonable cleanup deadline for winners; (e) coordinating pickup with winning bidders; (f) collecting the hammer directly from the winner on cash / e-Transfer auctions (BidVex handles only the buyer's 5% premium — you handle the hammer offline). On Stripe-mode auctions BidVex collects hammer + 5% buyer's premium from the buyer and remits you the full hammer via Stripe payout; (g) collecting applicable provincial sales tax from buyers on the goods themselves (BidVex only collects tax on its own 5% buyer's premium)."
            body_fr="En tant qu'établissement listant, vous êtes responsable de : (a) respecter toutes les lois provinciales sur les droits de rétention et les exigences de notification des locataires avant de lister ; (b) classifier précisément chaque unité comme sous droit de rétention ou non ; (c) fournir des photos et vidéos claires du contenu de l'unité ; (d) fixer un délai de nettoyage raisonnable pour les gagnants ; (e) coordonner le ramassage avec les enchérisseurs gagnants ; (f) percevoir le prix marteau directement du gagnant sur les enchères en espèces ou virement Interac (BidVex ne gère que la prime acheteur de 5 % — vous gérez le prix marteau hors ligne). Sur les enchères Stripe, BidVex perçoit auprès de l'acheteur le prix marteau + prime acheteur 5 % et vous verse le prix marteau complet via Stripe ; (g) percevoir la taxe de vente provinciale applicable auprès des acheteurs sur les biens eux-mêmes (BidVex ne perçoit que la taxe sur sa propre prime acheteur de 5 %)."
          />
        </Card>
      </div>
      <StorageFooterBanner />
    </div>
  );
};
