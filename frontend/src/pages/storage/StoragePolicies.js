import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Card } from '../../components/ui/card';
import { ArrowLeft } from 'lucide-react';

const Section = ({ title_en, title_fr, body_en, body_fr }) => (
  <div className="mb-6">
    <h3 className="font-bold text-lg mb-1">{title_en}</h3>
    <h4 className="font-semibold text-sm text-blue-600 mb-3">{title_fr}</h4>
    <div className="space-y-3 text-sm leading-relaxed">
      <p><strong>EN:</strong> {body_en}</p>
      <p className="text-muted-foreground"><strong>FR:</strong> {body_fr}</p>
    </div>
  </div>
);

export const HowItWorks = () => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="storage-how-it-works">
      <div className="max-w-3xl mx-auto px-4">
        <Link to="/storage-auctions/browse" className="inline-flex items-center text-sm text-blue-600 hover:underline mb-3">
          <ArrowLeft className="h-3.5 w-3.5 mr-1" /> {isFr ? "Retour aux enchères" : 'Back to auctions'}
        </Link>
        <h1 className="text-3xl font-bold mb-1">How Storage Unit Auctions Work on BidVex</h1>
        <h2 className="text-lg text-blue-600 mb-6">Comment fonctionnent les enchères d'unités d'entreposage sur BidVex</h2>
        <Card className="p-6">
          <Section
            title_en="1. What is a storage unit auction?"
            title_fr="1. Qu'est-ce qu'une enchère d'unité d'entreposage ?"
            body_en="Storage unit auctions occur when a tenant stops paying rent on their storage unit and cannot be reached by the facility. After following the required legal notification process, the facility lists the unit's contents for public auction. You bid on the contents of the unit without being able to enter it — based on photos and video only."
            body_fr="Les enchères d'unités d'entreposage ont lieu lorsqu'un locataire cesse de payer son loyer et ne peut pas être contacté par la facilité. Après avoir suivi le processus légal de notification requis, la facilité liste le contenu de l'unité aux enchères publiques. Vous enchérissez sur le contenu de l'unité sans pouvoir y entrer — en vous basant uniquement sur des photos et vidéos."
          />
          <Section
            title_en="2. Proxy Bidding Explained"
            title_fr="2. Enchères par procuration expliquées"
            body_en="Every bid you place is a maximum bid. The system automatically bids on your behalf up to your maximum, increasing by $10 increments only as needed. You only ever pay the minimum amount required to win. If another bidder's maximum exceeds yours, you will be immediately notified by email."
            body_fr="Chaque offre que vous placez est une offre maximale. Le système enchérit automatiquement en votre nom jusqu'à votre maximum, en augmentant par tranches de 10 $ seulement au besoin. Vous ne payez jamais que le montant minimum requis pour gagner. Si le maximum d'un autre enchérisseur dépasse le vôtre, vous serez immédiatement notifié par courriel."
          />
          <Section
            title_en="3. Soft Close"
            title_fr="3. Fermeture progressive (soft close)"
            body_en="To ensure fairness, any bid placed in the final 10 minutes of an auction extends the auction by 10 minutes. This prevents last-second sniping and gives every bidder a fair opportunity to respond."
            body_fr="Pour assurer l'équité, toute offre placée dans les 10 dernières minutes d'une enchère prolonge l'enchère de 10 minutes. Cela empêche les offres de dernière seconde et donne à chaque enchérisseur une chance équitable de répondre."
          />
          <Section
            title_en="4. No Buyer Fees"
            title_fr="4. Aucuns frais acheteur"
            body_en="BidVex charges ZERO buyer fees on all storage unit auctions. You pay only the winning bid amount directly to the storage facility. BidVex's commission is paid by the facility, not by you."
            body_fr="BidVex ne facture AUCUNS frais acheteur pour les enchères d'unités d'entreposage. Vous payez uniquement le montant de l'offre gagnante directement à la facilité d'entreposage. La commission de BidVex est payée par la facilité, pas par vous."
          />
          <Section
            title_en="5. Payment Methods"
            title_fr="5. Modes de paiement"
            body_en="After winning, you must arrange payment with the storage facility directly. Accepted methods are set by each facility: Stripe (credit/debit card with processing fees), cash paid directly at the facility, or Interac e-Transfer to the facility's registered email. Payment must be completed within the timeline specified by the facility."
            body_fr="Après avoir gagné, vous devez organiser le paiement avec la facilité d'entreposage directement. Les méthodes acceptées sont définies par chaque facilité : Stripe (carte de crédit/débit avec frais de traitement), comptant à la facilité, ou virement Interac au courriel enregistré. Le paiement doit être complété dans le délai spécifié."
          />
          <Section
            title_en="6. Cleanup Rules"
            title_fr="6. Règles de nettoyage"
            body_en="Winners are responsible for completely emptying the storage unit by the deadline specified in the listing. Failure to empty the unit by the deadline forfeits your cleaning deposit and may result in account suspension. You must coordinate pickup directly with the facility manager. Treat facility staff with respect."
            body_fr="Les gagnants sont responsables de vider complètement l'unité d'entreposage avant la date limite spécifiée dans l'annonce. Le non-respect de cette date limite entraîne la perte de votre dépôt de nettoyage et peut entraîner la suspension de votre compte. Vous devez coordonner le ramassage directement avec le gestionnaire de la facilité. Traitez le personnel de la facilité avec respect."
          />
        </Card>
      </div>
    </div>
  );
};

export const StorageTerms = () => {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="storage-terms">
      <div className="max-w-3xl mx-auto px-4">
        <Link to="/storage-auctions/browse" className="inline-flex items-center text-sm text-blue-600 hover:underline mb-3">
          <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back to auctions
        </Link>
        <h1 className="text-3xl font-bold mb-1">Storage Unit Auction Terms & Conditions</h1>
        <h2 className="text-lg text-blue-600 mb-6">Conditions générales des enchères d'unités d'entreposage</h2>
        <Card className="p-6">
          <Section
            title_en="Article 1 — Platform Role"
            title_fr="Article 1 — Rôle de la plateforme"
            body_en="BidVex is a technology platform and disclosed agent for storage facilities. BidVex is NOT an auctioneer. The actual auction and sale are conducted by the storage facility at their location. BidVex simply provides the online bidding platform. All bids placed on BidVex are final and cannot be revoked under any circumstances."
            body_fr="BidVex est une plateforme technologique et agent divulgué pour les facilités d'entreposage. BidVex N'EST PAS un encanteur. La vente aux enchères réelle est conduite par la facilité d'entreposage à son emplacement. BidVex fournit simplement la plateforme d'enchères en ligne. Toutes les offres placées sur BidVex sont finales et ne peuvent être révoquées en aucune circonstance."
          />
          <Section
            title_en="Article 2 — Lien Units"
            title_fr="Article 2 — Unités sous droit de rétention"
            body_en="Storage facilities are solely responsible for compliance with all provincial lien laws, tenant notification requirements, and legal auction procedures applicable in their province. BidVex accepts no liability for any claim arising from the sale of lien units."
            body_fr="Les facilités d'entreposage sont seules responsables du respect de toutes les lois provinciales sur les droits de rétention, des exigences de notification des locataires et des procédures légales d'enchères applicables dans leur province. BidVex n'accepte aucune responsabilité pour toute réclamation découlant de la vente d'unités sous droit de rétention."
          />
          <Section
            title_en="Article 3 — Buyer Obligations"
            title_fr="Article 3 — Obligations de l'acheteur"
            body_en="By placing a bid, you agree to: (a) complete payment within the facility's specified deadline; (b) empty the unit completely by the cleanup deadline; (c) coordinate pickup directly with the facility; (d) pay any applicable cleaning deposit; (e) accept the unit contents as-is with no returns or refunds; (f) comply with all applicable provincial laws."
            body_fr="En plaçant une offre, vous acceptez de : (a) compléter le paiement dans le délai spécifié par la facilité ; (b) vider complètement l'unité avant la date limite de nettoyage ; (c) coordonner le ramassage directement avec la facilité ; (d) payer tout dépôt de nettoyage applicable ; (e) accepter le contenu de l'unité tel quel, sans retours ni remboursements ; (f) respecter toutes les lois provinciales applicables."
          />
          <Section
            title_en="Article 4 — BidVex Commission"
            title_fr="Article 4 — Commission BidVex"
            body_en="BidVex charges storage facilities a 5% seller commission on the winning bid price. Buyers pay zero BidVex fees. The 5% commission plus applicable taxes and Stripe processing fees are invoiced directly to the facility after each successful auction."
            body_fr="BidVex facture aux facilités d'entreposage une commission vendeur de 5 % sur le prix de l'offre gagnante. Les acheteurs ne paient aucuns frais BidVex. La commission de 5 % plus les taxes applicables et les frais de traitement Stripe sont facturés directement à la facilité après chaque enchère réussie."
          />
          <Section
            title_en="Article 5 — No Guarantees"
            title_fr="Article 5 — Aucune garantie"
            body_en="BidVex does not guarantee the contents, value, or condition of any storage unit. All sales are final. BidVex is not liable for any losses incurred during pickup, for the condition of items, or for any discrepancies between photos and actual contents."
            body_fr="BidVex ne garantit pas le contenu, la valeur ou l'état de toute unité d'entreposage. Toutes les ventes sont finales. BidVex n'est pas responsable des pertes subies lors du ramassage, de l'état des articles ou des écarts entre les photos et le contenu réel."
          />
          <Section
            title_en="Article 6 — Account Suspension"
            title_fr="Article 6 — Suspension du compte"
            body_en="The following actions will result in immediate account suspension: (a) failing to complete payment after winning; (b) failing to empty a unit by the cleanup deadline; (c) abusive behaviour toward facility staff; (d) attempting to revoke a placed bid; (e) providing false information during registration."
            body_fr="Les actions suivantes entraîneront une suspension immédiate du compte : (a) ne pas compléter le paiement après avoir gagné ; (b) ne pas vider une unité avant la date limite de nettoyage ; (c) comportement abusif envers le personnel de la facilité ; (d) tentative de révoquer une offre placée ; (e) fourniture de fausses informations lors de l'inscription."
          />
        </Card>
      </div>
    </div>
  );
};

export const StorageForFacilities = () => {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="storage-for-facilities">
      <div className="max-w-3xl mx-auto px-4">
        <Link to="/storage-auctions/browse" className="inline-flex items-center text-sm text-blue-600 hover:underline mb-3">
          <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back to auctions
        </Link>
        <h1 className="text-3xl font-bold mb-1">List Your Storage Units on BidVex — Facility Guide</h1>
        <h2 className="text-lg text-blue-600 mb-6">Listez vos unités d'entreposage sur BidVex — Guide pour facilités</h2>
        <Card className="p-6">
          <Section
            title_en="1. Why BidVex?"
            title_fr="1. Pourquoi BidVex ?"
            body_en="BidVex is Canada's bilingual auction platform built for professional sellers. As a storage facility, you get: 5% commission only — we charge nothing to buyers; bilingual listings — reach French and English buyers across Canada; real-time bidding — proxy bidding drives higher final prices; soft-close protection — prevents sniping; photo and video support — showcase unit contents professionally; automated outbid notifications; secure payment options — Stripe, Cash, or E-Transfer."
            body_fr="BidVex est la plateforme d'enchères bilingue du Canada construite pour les vendeurs professionnels. En tant que facilité d'entreposage, vous obtenez : commission de 5 % seulement — nous ne facturons rien aux acheteurs ; annonces bilingues — rejoignez les acheteurs francophones et anglophones à travers le Canada ; enchères en temps réel — les enchères par procuration génèrent des prix finaux plus élevés ; protection soft-close ; support photos et vidéos ; notifications automatiques de surenchère ; options de paiement sécurisées — Stripe, comptant ou virement électronique."
          />
          <Section
            title_en="2. Commission Structure"
            title_fr="2. Structure des commissions"
            body_en="BidVex charges a flat 5% seller commission on the winning bid price. This is the only fee you pay. There is no monthly subscription fee to list storage units. You are invoiced after each successful sale."
            body_fr="BidVex facture une commission vendeur fixe de 5 % sur le prix de l'offre gagnante. C'est le seul frais que vous payez. Il n'y a pas de frais d'abonnement mensuel pour lister des unités d'entreposage. Vous êtes facturé après chaque vente réussie."
          />
          <Section
            title_en="3. Your Responsibilities"
            title_fr="3. Vos responsabilités"
            body_en="As a listing facility, you are responsible for: (a) complying with all provincial lien laws and tenant notification requirements before listing; (b) accurately classifying each unit as lien or non-lien; (c) providing clear photos and video of unit contents; (d) setting a reasonable cleanup deadline for winners; (e) coordinating pickup with winning bidders; (f) collecting payment from winners (BidVex does not collect the winning bid price on your behalf); (g) collecting applicable provincial sales tax from buyers (BidVex only collects tax on its 5% commission)."
            body_fr="En tant que facilité listante, vous êtes responsable de : (a) respecter toutes les lois provinciales sur les droits de rétention et les exigences de notification des locataires avant de lister ; (b) classifier précisément chaque unité comme sous droit de rétention ou non ; (c) fournir des photos et vidéos claires du contenu de l'unité ; (d) fixer un délai de nettoyage raisonnable pour les gagnants ; (e) coordonner le ramassage avec les enchérisseurs gagnants ; (f) percevoir le paiement des gagnants (BidVex ne perçoit pas le prix de l'offre gagnante en votre nom) ; (g) percevoir la taxe de vente provinciale applicable des acheteurs (BidVex perçoit uniquement la taxe sur sa commission de 5 %)."
          />
        </Card>
      </div>
    </div>
  );
};
