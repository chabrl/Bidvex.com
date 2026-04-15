import React from 'react';

export const PrivacyFR = () => (
  <div className="min-h-screen bg-background py-12 px-4">
    <div className="max-w-4xl mx-auto prose prose-sm dark:prose-invert">
      <h1>BidVex Inc. — Politique de confidentialité</h1>
      <p className="text-muted-foreground">Dernière mise à jour : 15 avril 2026 | Date d'entrée en vigueur : 15 avril 2026</p>

      <h2>1. Introduction</h2>
      <p>BidVex Inc. (« BidVex », « nous ») s'engage à protéger la vie privée de ses utilisateurs. Cette politique explique comment nous collectons, utilisons, stockons et protégeons vos renseignements personnels. Cette politique est conforme à la LPRPDE et à la Loi 25 du Québec.</p>

      <h2>2. Renseignements collectés</h2>
      <h3>2.1 Informations de compte</h3>
      <p>Nom, adresse courriel, numéro de téléphone, province de résidence, langue préférée (FR/EN), type de compte.</p>
      <h3>2.2 Informations de paiement</h3>
      <p>Nous utilisons Stripe. Nous stockons : identifiant client Stripe, jetons de méthode de paiement (jamais les numéros de carte bruts), marque de carte, quatre derniers chiffres et date d'expiration.</p>
      <h3>2.3 Données de transaction</h3>
      <p>Montants d'enchères, résultats, intentions de paiement, états de dépôt fiduciaire, codes de retrait, transferts, pénalités et factures.</p>
      <h3>2.4 Données de dépôt fiduciaire</h3>
      <p>Codes de retrait, états du dépôt (détenu/libéré/auto-libéré/contesté), horodatages de saisie, journaux de tentatives échouées, et calendriers de libération automatique.</p>
      <h3>2.5 Données d'utilisation</h3>
      <p>Événements de clic, pages vues, données de session, informations sur l'appareil, adresses IP. Nous utilisons PostHog pour l'analytique.</p>
      <h3>2.6 Données de communication</h3>
      <p>Messages entre utilisateurs, publications Q&amp;R communautaires, événements d'ouverture/clic de courriel (via SendGrid).</p>

      <h2>3. Utilisation des renseignements</h2>
      <ul>
        <li>Faciliter les enchères, paiements et transactions de dépôt fiduciaire</li>
        <li>Générer et livrer les codes de retrait aux Acheteurs</li>
        <li>Vérifier les moyens de paiement (système Sticky Card)</li>
        <li>Traiter les pénalités d'annulation</li>
        <li>Détecter et prévenir la fraude</li>
        <li>Envoyer des courriels transactionnels et marketing (avec consentement)</li>
        <li>Se conformer aux obligations légales</li>
        <li>Améliorer la Plateforme par l'analytique</li>
      </ul>

      <h2>4. Stripe et données de paiement</h2>
      <p>Stripe traite vos données de carte dans un environnement conforme PCI-DSS. BidVex ne stocke que des références tokenisées. Nous utilisons des objets Stripe Customer avec métadonnées pour la prévention de la fraude.</p>

      <h2>5. Partage des données</h2>
      <ul>
        <li><strong>Stripe</strong> : Traitement des paiements et transferts</li>
        <li><strong>SendGrid</strong> : Livraison de courriels</li>
        <li><strong>Autorités</strong> : Lorsque requis par la loi</li>
        <li><strong>Autres utilisateurs</strong> : Votre nom d'affichage est visible. Les adresses courriel ne sont jamais partagées.</li>
      </ul>

      <h2>6. Conservation des données</h2>
      <ul>
        <li><strong>Données de compte</strong> : Durée du compte + 3 ans après suppression</li>
        <li><strong>Dossiers de transactions</strong> : 7 ans (conformité fiscale)</li>
        <li><strong>Journaux de dépôt fiduciaire</strong> : 5 ans</li>
        <li><strong>Journaux de pénalités</strong> : 7 ans</li>
        <li><strong>Journaux de tentatives de retrait</strong> : 2 ans</li>
        <li><strong>Journaux d'événements courriel</strong> : 1 an</li>
      </ul>

      <h2>7. Vos droits</h2>
      <p>En vertu de la LPRPDE et de la Loi 25 :</p>
      <ul>
        <li><strong>Accès</strong> : Demander une copie de vos renseignements</li>
        <li><strong>Correction</strong> : Demander la correction de données inexactes</li>
        <li><strong>Suppression</strong> : Demander la suppression (sous réserve des obligations légales)</li>
        <li><strong>Portabilité</strong> : Recevoir vos données dans un format structuré</li>
        <li><strong>Retrait du consentement</strong> : Retirer le consentement marketing à tout moment</li>
      </ul>
      <p><strong>Limitations</strong> : Nous ne pouvons pas supprimer les dossiers financiers requis pour la conformité fiscale, les dépôts actifs ou les dossiers de pénalités.</p>

      <h2>8. Sécurité</h2>
      <ul>
        <li>Chiffrement HTTPS/TLS pour toutes les transmissions</li>
        <li>Tokenisation des paiements via Stripe (PCI-DSS Niveau 1)</li>
        <li>Codes de retrait générés cryptographiquement</li>
        <li>Surveillance des tentatives échouées avec détection de force brute</li>
        <li>Contrôle d'accès basé sur les rôles</li>
        <li>Accès MongoDB restreint au réseau interne</li>
      </ul>

      <h2>9. Cookies et suivi</h2>
      <p>Nous utilisons des cookies essentiels pour l'authentification et les préférences. PostHog pour l'analytique (désactivation possible). SendGrid pour le suivi des courriels.</p>

      <h2>10. Services bilingues</h2>
      <p>BidVex est une plateforme bilingue. Toutes les communications sont envoyées dans votre langue préférée.</p>

      <h2>11. Vie privée des mineurs</h2>
      <p>BidVex n'est pas destiné aux utilisateurs de moins de 18 ans.</p>

      <h2>12. Modifications</h2>
      <p>Nous pouvons mettre à jour cette politique. Les changements importants seront communiqués par courriel.</p>

      <h2>13. Contact</h2>
      <p>Pour toute question : <strong>privacy@bidvex.com</strong></p>
    </div>
  </div>
);
