import React from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../components/ui/card';
import { ArrowLeft, ShieldCheck, ShoppingBag, Users, Gavel, MessageCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

const Section = ({ icon, title, children }) => (
  <Card className="mb-6">
    <CardContent className="pt-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">{icon}</div>
        <h2 className="text-xl font-bold">{title}</h2>
      </div>
      <div className="prose prose-sm dark:prose-invert max-w-none space-y-3">{children}</div>
    </CardContent>
  </Card>
);

export default function PlatformPoliciesPage() {
  const { i18n } = useTranslation();
  const fr = i18n.language?.startsWith('fr');

  return (
    <div className="min-h-screen bg-background py-12 px-4" data-testid="policies-page">
      <div className="max-w-4xl mx-auto">
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary mb-6">
          <ArrowLeft className="h-4 w-4" /> {fr ? 'Retour' : 'Back'}
        </Link>
        <h1 className="text-3xl font-bold mb-2">{fr ? 'Politiques de la plateforme' : 'Platform Policies'}</h1>
        <p className="text-muted-foreground mb-8">{fr ? 'Dernière mise à jour : 15 avril 2026' : 'Last Updated: April 15, 2026'}</p>

        {/* Seller Policy */}
        <Section icon={<Gavel className="h-5 w-5 text-blue-600" />} title={fr ? 'Politique du vendeur' : 'Seller Policy'}>
          <h3>{fr ? 'Obligations de livraison' : 'Delivery Obligations'}</h3>
          <p>{fr
            ? "Les vendeurs doivent livrer les articles tels que décrits dans l'annonce. La non-livraison après la clôture d'une enchère avec un gagnant entraîne une pénalité de 50,00 $ CAD prélevée automatiquement sur votre carte enregistrée."
            : "Sellers must deliver items as described in the listing. Non-delivery after auction close with a winning bid triggers a $50.00 CAD penalty automatically charged to your card on file."}</p>
          <h3>{fr ? 'Validation du code de retrait' : 'Pickup Code Validation'}</h3>
          <p>{fr
            ? "Pour les articles non véhiculaires, vous devez entrer le code de retrait à 6 caractères fourni par l'acheteur pour confirmer la remise et libérer les fonds. Si le code n'est pas entré dans les 48 heures, les fonds sont automatiquement libérés sur votre compte."
            : "For non-vehicle items, you must enter the 6-character pickup code provided by the buyer to confirm handoff and release funds. If the code is not entered within 48 hours, funds are automatically released to your account."}</p>
          <h3>{fr ? 'Pénalités' : 'Penalty Rules'}</h3>
          <ul>
            <li>{fr ? 'Annulation après vente : 50,00 $ CAD' : 'Cancellation after sale: $50.00 CAD'}</li>
            <li>{fr ? 'Carte refusée lors de la pénalité : suspension du compte' : 'Card declined on penalty: account suspension'}</li>
            <li>{fr ? '5 tentatives échouées de code : signalé pour fraude' : '5 failed code attempts: flagged for fraud'}</li>
          </ul>
          <h3>{fr ? 'Licence véhicule' : 'Vehicle Seller Licensing'}</h3>
          <p>{fr
            ? "Seuls les vendeurs avec un permis OPC vérifié peuvent lister des véhicules routiers. Les vendeurs individuels sont interdits de lister des véhicules."
            : "Only sellers with a verified OPC permit may list road vehicles. Individual sellers are prohibited from listing vehicles."}</p>
          <h3>{fr ? 'Visibilité multi-lots' : 'Multi-lot Visibility'}</h3>
          <p>{fr
            ? "Les enchères multi-lots apparaissent sur le marché avec des badges individuels par lot. Chaque lot est enchéri séparément."
            : "Multi-lot auctions appear on the marketplace with individual lot badges. Each lot is bid on separately."}</p>
        </Section>

        {/* Buyer Policy */}
        <Section icon={<ShoppingBag className="h-5 w-5 text-green-600" />} title={fr ? "Politique de l'acheteur" : 'Buyer Policy'}>
          <h3>{fr ? 'Responsabilité du code de retrait' : 'Pickup Code Responsibility'}</h3>
          <p>{fr
            ? "Lors du gain d'une enchère non véhiculaire, vous recevrez un code de retrait unique par courriel. Vous devez présenter ce code au vendeur lors du retrait. Ne partagez ce code qu'avec le vendeur au moment de la remise."
            : "Upon winning a non-vehicle auction, you will receive a unique pickup code via email. You must present this code to the seller at pickup. Only share this code with the seller at the time of handoff."}</p>
          <h3>{fr ? 'Litiges' : 'Dispute Rules'}</h3>
          <p>{fr
            ? "Si vous avez un problème avec un article reçu (non conforme à la description, endommagé, etc.), vous pouvez ouvrir un litige dans la fenêtre de dépôt de 48 heures. Les fonds seront retenus en attendant la résolution."
            : "If you have an issue with a received item (not as described, damaged, etc.), you may open a dispute within the 48-hour escrow window. Funds will be held pending resolution."}</p>
          <h3>{fr ? 'Remboursements' : 'Refund Rules'}</h3>
          <p>{fr
            ? "Les remboursements sont traités uniquement en cas de litige résolu en faveur de l'acheteur. Une fois les fonds libérés (manuellement ou automatiquement), les remboursements ne sont plus possibles via le système de dépôt."
            : "Refunds are processed only for disputes resolved in the buyer's favor. Once funds are released (manually or automatically), refunds are no longer possible through the escrow system."}</p>
          <h3>{fr ? 'Délais' : 'Escrow Timelines'}</h3>
          <ul>
            <li>{fr ? 'Paiement capturé → dépôt créé : immédiat' : 'Payment captured → escrow created: immediate'}</li>
            <li>{fr ? 'Code de retrait valide : 48 heures' : 'Pickup code valid: 48 hours'}</li>
            <li>{fr ? 'Libération automatique : 48 heures après création' : 'Auto-release: 48 hours after creation'}</li>
          </ul>
        </Section>

        {/* Partner Policy */}
        <Section icon={<Users className="h-5 w-5 text-purple-600" />} title={fr ? 'Politique du partenaire' : 'Partner Policy'}>
          <h3>{fr ? 'Privilèges' : 'Privileges'}</h3>
          <p>{fr
            ? "Les partenaires bénéficient de frais réduits, de la possibilité de définir des primes acheteur personnalisées, et de créer des enchères multi-lots."
            : "Partners benefit from reduced fees, the ability to set custom buyer premiums, and create multi-lot auctions."}</p>
          <h3>{fr ? 'Restrictions véhicules' : 'Vehicle Restrictions'}</h3>
          <p>{fr
            ? "Les partenaires doivent avoir un permis OPC vérifié pour lister des véhicules. Les partenaires sans permis OPC ne peuvent lister que des articles non véhiculaires."
            : "Partners must have a verified OPC permit to list vehicles. Partners without OPC permits may only list non-vehicle items."}</p>
          <h3>{fr ? 'Commission' : 'Commission Rules'}</h3>
          <p>{fr
            ? "Les partenaires paient un frais de plateforme fixe au lieu d'une commission variable. Les taux exacts sont définis dans le contrat partenaire."
            : "Partners pay a fixed platform fee instead of a variable commission. Exact rates are defined in the partner agreement."}</p>
          <h3>{fr ? 'Conformité' : 'Compliance Expectations'}</h3>
          <p>{fr
            ? "Les partenaires doivent maintenir des informations commerciales à jour, respecter les politiques de la plateforme, et répondre aux demandes d'administration dans les 48 heures."
            : "Partners must maintain current business information, comply with platform policies, and respond to administrative requests within 48 hours."}</p>
        </Section>

        {/* Community Q&A Policy */}
        <Section icon={<MessageCircle className="h-5 w-5 text-cyan-600" />} title={fr ? 'Politique Q&R communautaire' : 'Community Q&A Policy'}>
          <h3>{fr ? 'Contenu permis' : 'Allowed Content'}</h3>
          <ul>
            <li>{fr ? 'Questions sur les enchères et le processus' : 'Questions about auctions and the process'}</li>
            <li>{fr ? 'Conseils de vente et achat' : 'Buying and selling tips'}</li>
            <li>{fr ? 'Discussions sur les catégories' : 'Category discussions'}</li>
          </ul>
          <h3>{fr ? 'Contenu interdit' : 'Prohibited Content'}</h3>
          <ul>
            <li>{fr ? 'Spam et sollicitations commerciales' : 'Spam and commercial solicitations'}</li>
            <li>{fr ? 'Contenu offensant, haineux ou discriminatoire' : 'Offensive, hateful, or discriminatory content'}</li>
            <li>{fr ? 'Informations personnelles d\'autrui' : "Others' personal information"}</li>
            <li>{fr ? 'Liens vers des sites concurrents' : 'Links to competing platforms'}</li>
            <li>{fr ? 'Fausses informations' : 'Misinformation'}</li>
          </ul>
          <h3>{fr ? 'Modération' : 'Moderation Rules'}</h3>
          <p>{fr
            ? "BidVex se réserve le droit de supprimer tout contenu violant ces politiques. Les violations répétées entraîneront des restrictions de compte. Le signalement de contenu inapproprié est encouragé."
            : "BidVex reserves the right to remove any content violating these policies. Repeated violations will result in account restrictions. Reporting inappropriate content is encouraged."}</p>
        </Section>

        <p className="text-center text-sm text-muted-foreground mt-8">
          {fr ? 'Pour toute question, contactez ' : 'For questions, contact '}
          <strong>legal@bidvex.com</strong>
        </p>
      </div>
    </div>
  );
}
