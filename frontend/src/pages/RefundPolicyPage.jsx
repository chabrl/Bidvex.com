/**
 * BidVex — Refund & Return Policy.
 *
 * Tailored for an ONLINE AUCTION model under Canadian provincial consumer-
 * protection law. Bilingual EN/FR. Designed to satisfy Google Merchant
 * Center's "Misrepresentation" reinstatement requirements by clearly
 * disclosing the as-is/where-is, binding-bid, final-sale nature of the
 * marketplace.
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../components/ui/card';
import { Gavel, ShieldAlert, FileText, AlertTriangle, Mail, Phone } from 'lucide-react';

export default function RefundPolicyPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const t = COPY[lang];

  return (
    <div className="container mx-auto max-w-3xl py-10 px-4" data-testid="refund-policy-page">
      <header className="mb-8 border-b border-slate-200 dark:border-slate-700 pb-4">
        <h1 className="text-3xl font-bold flex items-center gap-2" data-testid="refund-policy-title">
          <Gavel className="w-7 h-7 text-blue-600" />
          {t.title}
        </h1>
        <p className="text-sm text-slate-500 mt-1">{t.effective}</p>
      </header>

      {t.sections.map((s, idx) => (
        <Card key={idx} className="mb-4" data-testid={`refund-section-${idx}`}>
          <CardContent className="p-5">
            <h2 className="text-lg font-semibold flex items-center gap-2 mb-2">
              <s.icon className="w-4 h-4 text-amber-600" />
              {s.heading}
            </h2>
            <div className="prose prose-sm dark:prose-invert max-w-none text-slate-700 dark:text-slate-200">
              {s.body}
            </div>
          </CardContent>
        </Card>
      ))}

      <Card className="bg-slate-50 dark:bg-slate-800/40 border-slate-200">
        <CardContent className="p-5">
          <h3 className="font-semibold mb-2 flex items-center gap-2">
            <Mail className="w-4 h-4" />
            {t.contact_title}
          </h3>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {t.contact_body}{' '}
            <a href="mailto:service@bidvex.com?subject=Dispute%20Resolution" className="text-blue-600 hover:underline">service@bidvex.com</a>
            {' · '}
            <a href="tel:+14506343099" className="text-blue-600 hover:underline">+1 (450) 634-3099</a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

const COPY = {
  en: {
    title:        'Refund, Return & Dispute Resolution Policy',
    effective:    'Effective: 24 February 2026 · BidVex Inc. · Sherbrooke, QC, Canada',
    contact_title: 'Dispute Resolution Contact',
    contact_body: 'For all post-sale disputes, contact the BidVex Resolutions Team within seventy-two (72) hours of the auction close at',
    sections: [
      {
        icon: ShieldAlert,
        heading: '1. Auction Nature — All Sales Final, "As-Is, Where-Is"',
        body: (
          <>
            <p>BidVex Inc. operates an online auction marketplace. All listings — including but not limited to vehicles, storage lockers, multi-item lots, equipment, and consumer goods — are offered for sale on a strict <strong>"as-is, where-is"</strong> basis. By placing a bid on any listing, the bidder represents that they have personally examined or had a reasonable opportunity to examine the lot and accept its condition in its entirety.</p>
            <p>BidVex makes <strong>no warranties of merchantability, fitness for purpose, completeness, accuracy of description, or absence of defect</strong>, whether express or implied, beyond those mandatorily imposed by Canadian provincial consumer-protection legislation.</p>
          </>
        ),
      },
      {
        icon: Gavel,
        heading: '2. Bids Are Legally Binding Contracts',
        body: (
          <>
            <p>Every bid placed on BidVex constitutes a <strong>binding, irrevocable offer to purchase</strong> the listed lot at the bid amount tendered. Once the auction closes and the winning bid is confirmed, a legally enforceable purchase contract is formed between the buyer (or the buyer's Legal Bidder of Record under the Broker mandate in §1 of the Vehicle Auction Annex) and the seller.</p>
            <p>Bids may <strong>not</strong> be retracted, lowered, or transferred after submission, save for a manifest typographical error reported to BidVex Resolutions in writing within fifteen (15) minutes of submission and prior to the auction's close.</p>
          </>
        ),
      },
      {
        icon: AlertTriangle,
        heading: '3. No Refund of Hammer Price; Limited Exceptions',
        body: (
          <>
            <p>Hammer prices, broker commissions, and platform service fees are <strong>final and non-refundable</strong>. BidVex shall not issue a refund of any such amount except in the following narrow circumstances:</p>
            <ul>
              <li><strong>(a) Material misrepresentation by seller</strong> — the lot delivered differs in a material respect (e.g., wrong VIN, undisclosed lien, fundamentally different item) from its listing description, as determined by BidVex Resolutions in good faith;</li>
              <li><strong>(b) Failure to deliver title</strong> — for vehicle auctions, the broker or seller fails to deliver a clean transferable title within thirty (30) days of payment;</li>
              <li><strong>(c) Unauthorized administrative cancellation</strong> — BidVex cancels the auction post-hammer due to fraud, sanctions screening, or regulatory order.</li>
            </ul>
            <p>Buyer's remorse, change of mind, financing fall-through, failed inspection, and discovery of pre-existing condition disclosed in the listing are <strong>not</strong> grounds for refund.</p>
          </>
        ),
      },
      {
        icon: FileText,
        heading: '4. $500 Refundable Security Deposit',
        body: (
          <>
            <p>The $500 CAD security deposit pre-authorized by every buyer prior to bidding on a vehicle is held by Stripe, Inc. and refunded automatically when (i) the broker partnership is terminated with no outstanding bid or invoice obligation, or (ii) the buyer settles in full within seventy-two (72) hours of a winning bid (in which case the deposit is applied as a down-payment, not refunded).</p>
            <p>The deposit is <strong>forfeited as liquidated damages</strong> if the buyer fails to settle within the 72-hour window, in accordance with §1.3 of the Vehicle Auction Annex of our Terms of Service.</p>
          </>
        ),
      },
      {
        icon: ShieldAlert,
        heading: '5. Dispute Resolution Procedure',
        body: (
          <>
            <p>A buyer wishing to claim a refund under §3(a)-(c) must:</p>
            <ol>
              <li>Submit a written claim to <strong>service@bidvex.com</strong> within seventy-two (72) hours of the auction close (vehicles) or forty-eight (48) hours of pickup (storage / multi-lot);</li>
              <li>Include the lot URL, photographs of the discrepancy, copies of correspondence with the seller or broker, and the buyer's BidVex user ID;</li>
              <li>Cooperate with BidVex Resolutions' investigation, including providing a sworn statement if requested.</li>
            </ol>
            <p>BidVex Resolutions will render a written decision within fifteen (15) business days. The decision is binding pending the parties' right to pursue binding mediation at the *Centre de règlement de différends* in Sherbrooke, QC, in accordance with §B of our Terms of Service.</p>
          </>
        ),
      },
      {
        icon: FileText,
        heading: '6. Title Transfer, Pickup & Vehicle Release',
        body: (
          <>
            <p>For vehicle auctions: title passes through the broker as Legal Bidder of Record under the double-transfer mechanic described in §2.2 of the Vehicle Auction Annex (Seller → Broker → Buyer). Pickup is at the seller's location, on the date communicated by the broker, against presentation of government ID and the BidVex-issued pickup code. Failure to pick up within seven (7) days of notice authorizes the seller to charge reasonable storage fees, which shall be the buyer's responsibility.</p>
            <p>For storage and multi-lot auctions: pickup terms are listing-specific and disclosed on the lot page. As-is/where-is rules apply.</p>
          </>
        ),
      },
    ],
  },

  fr: {
    title:        'Politique de remboursement, retour et règlement des différends',
    effective:    'En vigueur le : 24 février 2026 · BidVex Inc. · Sherbrooke, QC, Canada',
    contact_title: 'Contact — Règlement des différends',
    contact_body: 'Pour tout différend post-vente, contactez l\'équipe Résolutions de BidVex dans les soixante-douze (72) heures suivant la clôture de l\'encan à',
    sections: [
      {
        icon: ShieldAlert,
        heading: '1. Nature des encans — Ventes finales, « tel quel, où il se trouve »',
        body: (
          <>
            <p>BidVex Inc. exploite une plateforme d'encans en ligne. Toutes les fiches — y compris, sans s'y limiter, véhicules, casiers d'entreposage, lots multiples, équipement et biens de consommation — sont offertes à la vente sur une base stricte de <strong>« tel quel, où il se trouve »</strong>. En plaçant une mise sur une fiche, l'enchérisseur déclare avoir personnellement examiné ou avoir eu une occasion raisonnable d'examiner le lot et accepter son état dans sa totalité.</p>
            <p>BidVex ne fait <strong>aucune garantie de qualité marchande, d'adéquation à un usage, d'exhaustivité, d'exactitude de description ou d'absence de vice</strong>, qu'elle soit expresse ou implicite, au-delà de celles obligatoirement imposées par la législation provinciale canadienne de protection du consommateur.</p>
          </>
        ),
      },
      {
        icon: Gavel,
        heading: '2. Les mises sont des contrats légalement contraignants',
        body: (
          <>
            <p>Chaque mise placée sur BidVex constitue une <strong>offre d'achat contraignante et irrévocable</strong> du lot inscrit au montant de la mise soumise. À la clôture de l'encan et confirmation de la mise gagnante, un contrat d'achat juridiquement opposable se forme entre l'acheteur (ou son Enchérisseur légal de référence en vertu du mandat de courtier au §1 de l'Annexe Encans de véhicules) et le vendeur.</p>
            <p>Les mises ne peuvent <strong>pas</strong> être rétractées, abaissées ou transférées après soumission, sauf en cas d'erreur typographique manifeste signalée par écrit à BidVex Résolutions dans les quinze (15) minutes suivant la soumission et avant la clôture de l'encan.</p>
          </>
        ),
      },
      {
        icon: AlertTriangle,
        heading: '3. Aucun remboursement du prix marteau ; exceptions limitées',
        body: (
          <>
            <p>Les prix marteau, commissions de courtier et frais de service de la plateforme sont <strong>finaux et non remboursables</strong>. BidVex n'émettra aucun remboursement de ces montants sauf dans les circonstances limitées suivantes :</p>
            <ul>
              <li><strong>(a) Fausse déclaration matérielle du vendeur</strong> — le lot livré diffère de manière significative (p. ex., NIV erroné, privilège non divulgué, article fondamentalement différent) de la description de la fiche, selon BidVex Résolutions agissant de bonne foi ;</li>
              <li><strong>(b) Défaut de livrer le titre</strong> — pour les encans de véhicules, si le courtier ou le vendeur omet de livrer un titre clair et transférable dans les trente (30) jours du paiement ;</li>
              <li><strong>(c) Annulation administrative non autorisée</strong> — BidVex annule l'encan post-marteau en raison de fraude, sanctions, ou ordre réglementaire.</li>
            </ul>
            <p>Le remords de l'acheteur, le changement d'avis, l'échec de financement, l'échec d'inspection et la découverte d'un état préexistant divulgué dans la fiche ne sont <strong>pas</strong> des motifs de remboursement.</p>
          </>
        ),
      },
      {
        icon: FileText,
        heading: '4. Dépôt de garantie remboursable de 500 $',
        body: (
          <>
            <p>Le dépôt de garantie de 500 $ CAD pré-autorisé par chaque acheteur avant d'enchérir sur un véhicule est détenu par Stripe, Inc. et remboursé automatiquement lorsque (i) le partenariat de courtage est résilié sans obligation en cours sur les mises ou les factures, ou (ii) l'acheteur règle intégralement dans les soixante-douze (72) heures suivant une mise gagnante (auquel cas le dépôt est imputé à titre d'acompte, non remboursé).</p>
            <p>Le dépôt est <strong>perdu à titre de dommages-intérêts liquidés</strong> si l'acheteur omet de régler dans la fenêtre de 72 heures, conformément au §1.3 de l'Annexe Encans de véhicules.</p>
          </>
        ),
      },
      {
        icon: ShieldAlert,
        heading: '5. Procédure de règlement des différends',
        body: (
          <>
            <p>Un acheteur souhaitant réclamer un remboursement aux termes du §3 (a)-(c) doit :</p>
            <ol>
              <li>Soumettre une réclamation écrite à <strong>service@bidvex.com</strong> dans les soixante-douze (72) heures de la clôture de l'encan (véhicules) ou quarante-huit (48) heures de la collecte (entreposage / lots multiples) ;</li>
              <li>Inclure l'URL du lot, des photographies de l'écart, des copies de la correspondance avec le vendeur ou le courtier, et l'identifiant utilisateur BidVex ;</li>
              <li>Coopérer avec l'enquête de BidVex Résolutions, y compris fournir une déclaration sous serment sur demande.</li>
            </ol>
            <p>BidVex Résolutions rendra une décision écrite dans les quinze (15) jours ouvrables. La décision est exécutoire sous réserve du droit des parties de poursuivre une médiation exécutoire au *Centre de règlement de différends* à Sherbrooke, QC, conformément au §B des Conditions générales.</p>
          </>
        ),
      },
      {
        icon: FileText,
        heading: '6. Transfert de titre, collecte et remise des véhicules',
        body: (
          <>
            <p>Pour les encans de véhicules : le titre passe par le courtier en qualité d'Enchérisseur légal de référence selon la mécanique de double transfert décrite au §2.2 de l'Annexe Encans de véhicules (Vendeur → Courtier → Acheteur). La collecte se fait au lieu du vendeur, à la date communiquée par le courtier, sur présentation d'une pièce d'identité gouvernementale et du code de collecte émis par BidVex. À défaut de collecte dans les sept (7) jours de l'avis, le vendeur est autorisé à facturer des frais d'entreposage raisonnables, à la charge de l'acheteur.</p>
            <p>Pour les encans d'entreposage et de lots multiples : les modalités de collecte sont propres à chaque fiche et divulguées sur la page du lot. Les règles « tel quel, où il se trouve » s'appliquent.</p>
          </>
        ),
      },
    ],
  },
};
