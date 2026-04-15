import React from 'react';

export const TermsFR = () => (
  <div className="min-h-screen bg-background py-12 px-4">
    <div className="max-w-4xl mx-auto prose prose-sm dark:prose-invert">
      <h1>BidVex Inc. — Conditions d'utilisation</h1>
      <p className="text-muted-foreground">Dernière mise à jour : 15 avril 2026 | Date d'entrée en vigueur : 15 avril 2026</p>

      <h2>1. Introduction et acceptation</h2>
      <p>Bienvenue sur BidVex. Les présentes conditions d'utilisation (« Conditions ») constituent un accord juridiquement contraignant entre vous (« Utilisateur ») et BidVex Inc. (« BidVex », « nous »). En vous inscrivant, en naviguant ou en participant à une enchère, vous acceptez ces Conditions et notre Politique de confidentialité.</p>

      <h2>2. Définitions</h2>
      <ul>
        <li><strong>Plateforme</strong> : Le site Web BidVex et tous les services associés.</li>
        <li><strong>Vendeur</strong> : Un Utilisateur qui met des articles aux enchères.</li>
        <li><strong>Acheteur</strong> : Un Utilisateur qui place des enchères ou achète des articles.</li>
        <li><strong>Partenaire</strong> : Un compte entreprise vérifié avec des privilèges de mise en vente améliorés.</li>
        <li><strong>Prix marteau</strong> : Le montant de l'enchère gagnante à la clôture.</li>
        <li><strong>Prime acheteur</strong> : Des frais supplémentaires facturés à l'Acheteur en plus du prix marteau.</li>
        <li><strong>Dépôt fiduciaire (Escrow)</strong> : La détention des fonds de l'Acheteur par BidVex jusqu'à confirmation du retrait.</li>
        <li><strong>Code de retrait</strong> : Un code alphanumérique de 6 caractères envoyé à l'Acheteur pour confirmer la remise.</li>
        <li><strong>Carte obligatoire (Sticky Card)</strong> : L'obligation pour les Vendeurs de maintenir un moyen de paiement valide pendant que des annonces sont actives.</li>
      </ul>

      <h2>3. Inscription</h2>
      <p>Vous devez avoir au moins 18 ans et résider au Canada pour créer un compte. Vous vous engagez à fournir des informations exactes et complètes. Vous êtes responsable de toute activité sous votre compte.</p>

      <h2>4. Moyen de paiement obligatoire (Politique Sticky Card)</h2>
      <h3>4.1 Exigence</h3>
      <p>Pour créer une annonce, chaque Vendeur doit avoir un moyen de paiement valide (carte de crédit ou débit) enregistré, rattaché à son profil Stripe.</p>
      <h3>4.2 Conservation de la carte</h3>
      <p>Les Vendeurs <strong>ne peuvent pas supprimer</strong> leur moyen de paiement tant que l'une de leurs annonces est active. Le système bloque toute tentative de suppression.</p>
      <h3>4.3 Vérification</h3>
      <p>BidVex vérifie que le moyen de paiement est valide et non expiré avant de permettre la création d'annonces.</p>
      <h3>4.4 Conservation du jeton Stripe</h3>
      <p>BidVex conserve un jeton de méthode de paiement Stripe (jamais les données brutes de carte). Ce jeton peut être utilisé pour traiter des frais autorisés, y compris les pénalités d'annulation.</p>

      <h2>5. Pénalité d'annulation</h2>
      <h3>5.1 Déclencheur</h3>
      <p>Une pénalité est déclenchée lorsqu'un Vendeur signale l'impossibilité de livrer après la clôture d'une enchère avec un gagnant, ou lorsqu'un administrateur signale une non-livraison.</p>
      <h3>5.2 Montant</h3>
      <p>La pénalité est un montant forfaitaire de <strong>50,00 $ CAD</strong>, automatiquement prélevé sur le moyen de paiement du Vendeur.</p>
      <h3>5.3 Échec du paiement</h3>
      <p>Si le prélèvement échoue, le compte du Vendeur sera signalé pour examen administratif et pourra être suspendu.</p>
      <h3>5.4 Autorisation</h3>
      <p>En créant une annonce sur BidVex, vous autorisez BidVex à prélever votre moyen de paiement pour toute pénalité d'annulation applicable.</p>

      <h2>6. Système de dépôt fiduciaire et code de retrait (articles non véhiculaires)</h2>
      <h3>6.1 Fonctionnement</h3>
      <p>Pour les articles non véhiculaires, lorsqu'un Acheteur remporte une enchère, les fonds sont détenus en fiducie par BidVex. Un code de retrait unique de 6 caractères est généré et envoyé à l'Acheteur. Le Vendeur doit entrer ce code pour confirmer la remise et libérer les fonds.</p>
      <h3>6.2 Livraison du code</h3>
      <p>Le code est envoyé à l'adresse courriel de l'Acheteur. L'Acheteur est responsable de présenter ce code au Vendeur.</p>
      <h3>6.3 Libération des fonds</h3>
      <p>Les fonds sont transférés au compte Stripe Connect du Vendeur uniquement après la saisie du code correct.</p>
      <h3>6.4 Libération automatique après 48 heures</h3>
      <p>Si l'Acheteur ne présente pas le code dans les 48 heures, les fonds sont <strong>automatiquement libérés</strong> au Vendeur. Les deux parties sont notifiées par courriel.</p>
      <h3>6.5 Litige</h3>
      <p>Chaque partie peut ouvrir un litige sur un dépôt actif. Les litiges sont examinés par l'équipe BidVex. Les fonds restent détenus pendant la résolution.</p>
      <h3>6.6 Exclusion des véhicules</h3>
      <p>Les transactions de véhicules sont exclues du système de dépôt fiduciaire. Les véhicules utilisent un flux de paiement séparé.</p>

      <h2>7. Licence de vendeur de véhicules</h2>
      <p>Seuls les vendeurs de véhicules licenciés avec un permis OPC vérifié peuvent lister des véhicules routiers. Les vendeurs individuels (non licenciés) sont interdits. Les tentatives frauduleuses entraîneront la suspension immédiate du compte.</p>

      <h2>8. Frais et tarification</h2>
      <p>BidVex facture des primes acheteur, des commissions vendeur et des frais de plateforme calculés par notre système de tarification. Les barèmes varient selon le niveau d'abonnement. Tous les frais sont affichés de manière transparente avant la confirmation.</p>

      <h2>9. Conduite sur la plateforme</h2>
      <h3>9.1 Comportements interdits</h3>
      <ul>
        <li>Enchères fictives sur vos propres articles</li>
        <li>Mise en vente d'articles contrefaits, volés ou illégaux</li>
        <li>Descriptions trompeuses</li>
        <li>Harcèlement via messages ou la communauté Q&amp;R</li>
        <li>Manipulation des résultats d'enchères</li>
        <li>Contournement des systèmes de paiement ou de dépôt fiduciaire</li>
      </ul>
      <h3>9.2 Obligations du vendeur</h3>
      <p>Les Vendeurs doivent livrer les articles tels que décrits. La non-livraison déclenche la pénalité d'annulation.</p>
      <h3>9.3 Obligations de l'acheteur</h3>
      <p>Les Acheteurs doivent compléter le paiement rapidement. Ils doivent présenter leur code de retrait lors de la collecte.</p>

      <h2>10. Communauté Q&amp;R</h2>
      <p>La communauté Q&amp;R est fournie à titre informatif. Les utilisateurs ne doivent pas publier de spam, contenu offensant, informations personnelles d'autrui ou sollicitations commerciales. BidVex se réserve le droit de modérer le contenu.</p>

      <h2>11. Stripe Connect et traitement des paiements</h2>
      <p>BidVex utilise Stripe comme processeur de paiement. En utilisant la Plateforme, vous acceptez les conditions de Stripe et autorisez BidVex à créer des charges, des retenues, des transferts et des pénalités en votre nom.</p>

      <h2>12. Limitation de responsabilité</h2>
      <p>BidVex agit comme facilitateur de marché et n'est pas partie à la vente. BidVex n'est pas responsable de la qualité, sécurité ou légalité des articles listés. Notre responsabilité est limitée aux frais perçus.</p>

      <h2>13. Loi applicable</h2>
      <p>Ces Conditions sont régies par les lois de la province de Québec et les lois fédérales du Canada. Tout litige sera résolu devant les tribunaux du Québec.</p>

      <h2>14. Modifications</h2>
      <p>BidVex se réserve le droit de modifier ces Conditions. Les changements importants seront communiqués par courriel. L'utilisation continue après les modifications constitue une acceptation.</p>

      <h2>15. Contact</h2>
      <p>Pour toute question, contactez-nous à <strong>legal@bidvex.com</strong>.</p>
    </div>
  </div>
);
