#!/usr/bin/env node
/**
 * P2: Add all translation keys for hardcoded strings found by audit
 */
const fs = require('fs');
const path = require('path');

const EN_PATH = path.resolve(__dirname, '../src/locales/en.json');
const FR_PATH = path.resolve(__dirname, '../src/locales/fr.json');
const en = JSON.parse(fs.readFileSync(EN_PATH, 'utf8'));
const fr = JSON.parse(fs.readFileSync(FR_PATH, 'utf8'));

function setKey(obj, dotKey, value) {
  const parts = dotKey.split('.');
  let current = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    if (!current[parts[i]] || typeof current[parts[i]] !== 'object') current[parts[i]] = {};
    current = current[parts[i]];
  }
  if (current[parts[parts.length - 1]] === undefined) {
    current[parts[parts.length - 1]] = value;
    return true;
  }
  return false;
}

const keys = {
  // AdminBannerManager
  'admin.bannerTitle': { en: 'Banner Title', fr: 'Titre de la bannière' },
  'admin.bannerImage': { en: 'Banner Image', fr: 'Image de la bannière' },
  // AutoBidModal
  'bidding.currentBid': { en: 'Current Bid', fr: 'Enchère actuelle' },
  'bidding.maxBidAmount': { en: 'Maximum Bid Amount', fr: 'Montant maximum de l\'enchère' },
  // AvatarUpload
  'profile.editProfilePhoto': { en: 'Edit Profile Photo', fr: 'Modifier la photo de profil' },
  // BuyNowButton
  'marketplace.buyNowLabel': { en: 'Buy Now', fr: 'Acheter maintenant' },
  // DecomposedMarketplace + FlattenedMarketplace filters
  'marketplace.promotedFirst': { en: 'Promoted First', fr: 'Promus en premier' },
  'marketplace.endingSoon': { en: 'Ending Soon', fr: 'Se terminant bientôt' },
  'marketplace.newestFirst': { en: 'Newest First', fr: 'Plus récent d\'abord' },
  'marketplace.allConditions': { en: 'All Conditions', fr: 'Tous les états' },
  'marketplace.likeNew': { en: 'Like New', fr: 'Comme neuf' },
  'marketplace.allCategories': { en: 'All Categories', fr: 'Toutes les catégories' },
  'marketplace.excellent': { en: 'Excellent', fr: 'Excellent' },
  // LocationSearchMap
  'common.errorLoadingMaps': { en: 'Error loading maps', fr: 'Erreur de chargement des cartes' },
  // LocationSelector
  'locationSelector.unitedStates': { en: 'United States', fr: 'États-Unis' },
  // PromotionManagerModal
  'admin.allAges': { en: 'All Ages', fr: 'Tous les âges' },
  'admin.interests': { en: 'Interests', fr: 'Intérêts' },
  // RealtimeBiddingPanel
  'auction.thisLotContains': { en: 'This lot contains', fr: 'Ce lot contient' },
  // ShareButton / SocialShare
  'common.copyLink': { en: 'Copy Link', fr: 'Copier le lien' },
  'common.facebook': { en: 'Facebook', fr: 'Facebook' },
  // TrendySubscriptionCards
  'subscription.subtotal': { en: 'Subtotal', fr: 'Sous-total' },
  'subscription.processingFee': { en: 'Processing fee', fr: 'Frais de traitement' },
  // HeroBannerEditor
  'admin.desktopImage': { en: 'Desktop Image', fr: 'Image bureau' },
  'admin.mobileImage': { en: 'Mobile Image', fr: 'Image mobile' },
  'admin.titleColor': { en: 'Title Color', fr: 'Couleur du titre' },
  'admin.subtitleColor': { en: 'Subtitle Color', fr: 'Couleur du sous-titre' },
  'admin.buttonBackground': { en: 'Button Background', fr: 'Fond du bouton' },
  'admin.buttonTextColor': { en: 'Button Text Color', fr: 'Couleur du texte du bouton' },
  'admin.overlayColor': { en: 'Overlay Color', fr: 'Couleur de superposition' },
  'admin.overlayOpacity': { en: 'Overlay Opacity', fr: 'Opacité de superposition' },
  'admin.fontFamily': { en: 'Font Family', fr: 'Police de caractères' },
  'admin.titleSize': { en: 'Title Size', fr: 'Taille du titre' },
  'admin.subtitleSize': { en: 'Subtitle Size', fr: 'Taille du sous-titre' },
  // AuctionRulesDisplay
  'auction.bidsInFinal': { en: 'Bids in final', fr: 'Enchères dans les dernières' },
  'auction.bindingBids': { en: 'Binding bids', fr: 'Enchères contraignantes' },
  'auction.tieredIncrements': { en: 'Tiered increments', fr: 'Incréments gradués' },
  'auction.transparentHistory': { en: 'Transparent history', fr: 'Historique transparent' },
  // LegalDisclaimers
  'auction.allBidsBinding': { en: 'All bids are legally binding contracts', fr: 'Toutes les enchères sont des contrats juridiquement contraignants' },
  'auction.yourDepositOf': { en: 'Your deposit of', fr: 'Votre dépôt de' },
  // PricingBreakdown
  'fees.totalPayable': { en: 'Total Payable', fr: 'Total à payer' },
  'fees.depositCredit': { en: 'Deposit Credit', fr: 'Crédit de dépôt' },
  // PricingCalculator
  'fees.enterBidAmount': { en: 'Enter a bid amount to see pricing breakdown', fr: 'Entrez un montant pour voir la ventilation des prix' },
  'fees.transactionFeeDesc': { en: 'Transaction processing and platform service fee', fr: 'Frais de traitement des transactions et frais de service de la plateforme' },
  // SellerDocumentManager
  'vehicles.requiredDocuments': { en: 'Required Documents', fr: 'Documents requis' },
  // AdminTaxDashboard
  'admin.startDate': { en: 'Start Date', fr: 'Date de début' },
  'admin.endDate': { en: 'End Date', fr: 'Date de fin' },
  'admin.detailedBreakdown': { en: 'Detailed Regional Breakdown', fr: 'Ventilation régionale détaillée' },
  // AuthPage
  'auth.newPasswordLabel': { en: 'New Password', fr: 'Nouveau mot de passe' },
  'auth.confirmPasswordLabel': { en: 'Confirm Password', fr: 'Confirmer le mot de passe' },
  'auth.setNewPassword': { en: 'Set New Password', fr: 'Définir le nouveau mot de passe' },
  // BuyerDashboard
  'auction.auctionEnded': { en: 'Auction Ended', fr: 'Enchère terminée' },
  'dashboard.buyer.purchaseHistory': { en: 'Purchase History', fr: 'Historique des achats' },
  // ClientEmailMarketing
  'admin.auctionAlert': { en: 'Auction Alert', fr: 'Alerte d\'enchère' },
  'common.unsubscribe': { en: 'Unsubscribe', fr: 'Se désabonner' },
  'admin.allPremiumTemplates': { en: 'All premium templates', fr: 'Tous les modèles premium' },
  'admin.priorityDelivery': { en: 'Priority delivery queue', fr: 'File d\'attente de livraison prioritaire' },
  'admin.advancedAnalytics': { en: 'Advanced analytics', fr: 'Analytique avancée' },
  'admin.campaignPerformance': { en: 'Campaign Performance', fr: 'Performance de la campagne' },
  'admin.addContact': { en: 'Add Contact', fr: 'Ajouter un contact' },
  'admin.bulkAddContacts': { en: 'Bulk Add Contacts', fr: 'Ajouter des contacts en lot' },
  'admin.startWithTemplate': { en: 'Start with a Template', fr: 'Commencer avec un modèle' },
  // CreateListingPage
  'profile.accountSettingsLink': { en: 'Account Settings', fr: 'Paramètres du compte' },
  // InviteAcceptPage
  'auth.fullNameLabel': { en: 'Full Name', fr: 'Nom complet' },
  'auth.passwordLabel': { en: 'Password', fr: 'Mot de passe' },
  // LegalPage
  'legal.mustBeAtLeast': { en: 'You must be at least', fr: 'Vous devez avoir au moins' },
  'legal.fullPaymentDue': { en: 'Full payment for all winning bids is due within', fr: 'Le paiement intégral de toutes les enchères gagnantes est dû dans' },
  'legal.latePaymentPenalty': { en: 'Payments not received by the due date may incur a late payment penalty of', fr: 'Les paiements non reçus à la date d\'échéance peuvent entraîner une pénalité de retard de' },
  'legal.paymentsHandledVia': { en: 'All payments are handled via', fr: 'Tous les paiements sont traités via' },
  'legal.governedByLaws': { en: 'These Terms and your use of the Platform are governed by and construed in accordance with the laws of the', fr: 'Ces conditions et votre utilisation de la plateforme sont régies par les lois de la' },
  'legal.provinceOfQuebec': { en: 'Province of Quebec', fr: 'Province de Québec' },
  'legal.compliancePolicy': { en: 'This policy is designed to comply with the', fr: 'Cette politique est conçue pour se conformer à la' },
  'legal.encryptionInTransit': { en: 'Encryption in transit', fr: 'Chiffrement en transit' },
  'legal.encryptionAtRest': { en: 'Encryption at rest', fr: 'Chiffrement au repos' },
  'legal.paymentCompliance': { en: 'Payment compliance', fr: 'Conformité des paiements' },
  // ProfileSettingsPage
  'profile.managePaymentMethods': { en: 'Manage your payment methods for bidding', fr: 'Gérez vos modes de paiement pour les enchères' },
  // SubscriptionPricingPage
  'subscription.paymentSetupPending': { en: 'Payment setup pending', fr: 'Configuration de paiement en attente' },
  'subscription.cancelAnytime': { en: 'Cancel Anytime', fr: 'Annulez à tout moment' },
  'subscription.instantAccess': { en: 'Instant Access', fr: 'Accès instantané' },
  // AIGuardDashboard
  'admin.allStatuses': { en: 'All Statuses', fr: 'Tous les statuts' },
  'admin.pendingReview': { en: 'Pending Review', fr: 'En attente d\'examen' },
  'admin.underInvestigation': { en: 'Under Investigation', fr: 'En cours d\'enquête' },
  'admin.confirmedFraud': { en: 'Confirmed Fraud', fr: 'Fraude confirmée' },
  'admin.allTypes': { en: 'All Types', fr: 'Tous les types' },
  // AdminLogs
  'admin.userUpdates': { en: 'User Updates', fr: 'Mises à jour utilisateurs' },
  'admin.moderation': { en: 'Moderation', fr: 'Modération' },
  // AffiliateManager
  'admin.payoutRequests': { en: 'Payout Requests', fr: 'Demandes de versement' },
  'admin.manageAffiliateStatus': { en: 'Manage Affiliate Status', fr: 'Gérer le statut d\'affilié' },
  // AnalyticsDashboard
  'admin.listingStatusDistribution': { en: 'Listing Status Distribution', fr: 'Répartition des statuts d\'annonces' },
  // AnnouncementManager
  'admin.createAnnouncement': { en: 'Create Announcement', fr: 'Créer une annonce' },
  'admin.allUsers': { en: 'All Users', fr: 'Tous les utilisateurs' },
  'admin.buyersOnly': { en: 'Buyers Only', fr: 'Acheteurs seulement' },
  'admin.sellersOnly': { en: 'Sellers Only', fr: 'Vendeurs seulement' },
  'admin.businessAccounts': { en: 'Business Accounts', fr: 'Comptes entreprise' },
  // AuctionControl
  'admin.setLimitsDesc': { en: 'Set limits to maintain marketplace quality', fr: 'Définir des limites pour maintenir la qualité du marché' },
  'admin.configureBidding': { en: 'Configure auction bidding behavior', fr: 'Configurer le comportement des enchères' },
  // BrandingLayoutManager
  'admin.defineBrandColors': { en: 'Define your brand colors', fr: 'Définissez les couleurs de votre marque' },
  // CouponManager
  'admin.discountType': { en: 'Discount Type', fr: 'Type de remise' },
  'admin.applicablePlans': { en: 'Applicable Plans', fr: 'Plans applicables' },
  'admin.allCoupons': { en: 'All Coupons', fr: 'Tous les coupons' },
  'common.inactive': { en: 'Inactive', fr: 'Inactif' },
  // CurrencyAppealsManager
  'admin.adminNotes': { en: 'Admin Notes', fr: 'Notes de l\'administrateur' },
  'admin.appealStatistics': { en: 'Appeal Statistics', fr: 'Statistiques des appels' },
  // EmailMarketingManager
  'admin.sendTestEmail': { en: 'Send Test Email', fr: 'Envoyer un courriel test' },
  'admin.previewCampaign': { en: 'Preview the campaign in your inbox', fr: 'Prévisualisez la campagne dans votre boîte' },
  'admin.emailAddress': { en: 'Email Address', fr: 'Adresse courriel' },
  'admin.scheduleCampaign': { en: 'Schedule Campaign', fr: 'Planifier la campagne' },
  'admin.chooseWhenToSend': { en: 'Choose when to send this campaign', fr: 'Choisissez quand envoyer cette campagne' },
  'admin.cancelScheduledCampaign': { en: 'This will cancel the scheduled campaign', fr: 'Cela annulera la campagne planifiée' },
  'admin.keepScheduled': { en: 'Keep Scheduled', fr: 'Garder planifié' },
  'admin.allStatus': { en: 'All Status', fr: 'Tous les statuts' },
  'admin.scheduled': { en: 'Scheduled', fr: 'Planifié' },
  'admin.cancelled': { en: 'Cancelled', fr: 'Annulé' },
  'admin.fromName': { en: 'From Name', fr: 'Nom de l\'expéditeur' },
  'admin.anyActivity': { en: 'Any Activity', fr: 'Toute activité' },
  // MarketplaceSettings
  'admin.controlAuctionCreation': { en: 'Control who can create auctions', fr: 'Contrôler qui peut créer des enchères' },
  'admin.setMaxQuantities': { en: 'Set maximum quantities per user', fr: 'Définir les quantités maximales par utilisateur' },
  'admin.configurePricing': { en: 'Configure bid increments and pricing', fr: 'Configurer les incréments et les prix' },
  // PricingManager
  'admin.planActive': { en: 'Plan Active', fr: 'Plan actif' },
  // PromotionManager
  'admin.createNewPromotion': { en: 'Create New Promotion', fr: 'Créer une nouvelle promotion' },
  'admin.featureListingsManually': { en: 'Feature Listings Manually', fr: 'Mettre en vedette manuellement' },
  // ReportManager
  'admin.resolved': { en: 'Resolved', fr: 'Résolu' },
  // SiteModeManager
  'admin.selectSiteMode': { en: 'Select Site Mode', fr: 'Sélectionner le mode du site' },
  'admin.chooseSiteMode': { en: 'Choose how visitors will see your website', fr: 'Choisissez comment les visiteurs verront votre site' },
  'admin.pageSettings': { en: 'Page Settings', fr: 'Paramètres de page' },
  'admin.customizeMessage': { en: 'Customize the message shown to visitors', fr: 'Personnalisez le message affiché aux visiteurs' },
  'admin.emailSignups': { en: 'Email signups from coming soon page', fr: 'Inscriptions par courriel depuis la page prochainement' },
  'admin.launchSubscribers': { en: 'Launch Subscribers', fr: 'Abonnés au lancement' },
  'admin.manageSubscribers': { en: 'Manage email subscribers from the coming soon page', fr: 'Gérer les abonnés par courriel de la page prochainement' },
  'common.subscribed': { en: 'Subscribed', fr: 'Abonné' },
  // SubscriptionManager
  'admin.selectPlan': { en: 'Select Plan', fr: 'Sélectionner le plan' },
  'admin.durationType': { en: 'Duration Type', fr: 'Type de durée' },
  'admin.numberOfDays': { en: 'Number of Days', fr: 'Nombre de jours' },
  'admin.additionalDays': { en: 'Additional Days', fr: 'Jours supplémentaires' },
  'admin.allPlans': { en: 'All Plans', fr: 'Tous les plans' },
  'admin.allSources': { en: 'All Sources', fr: 'Toutes les sources' },
  // TaxVerificationQueue
  'admin.receiveEmailConfirmation': { en: 'Receive email confirmation', fr: 'Recevoir la confirmation par courriel' },
  // TrustSafetyDashboard
  'admin.userTrustScores': { en: 'User Trust Scores', fr: 'Scores de confiance des utilisateurs' },
  'admin.fraudDetectionFlags': { en: 'Fraud Detection Flags', fr: 'Signaux de détection de fraude' },
  'admin.requireSellerVerification': { en: 'Require Seller Verification', fr: 'Exiger la vérification du vendeur' },
  'admin.requireBuyerVerification': { en: 'Require Buyer Verification', fr: 'Exiger la vérification de l\'acheteur' },
  // VehicleAdminManager
  'admin.enableVehicleAuctions': { en: 'Enable Vehicle Auctions', fr: 'Activer les enchères de véhicules' },
  'admin.enableVehicleListing': { en: 'Enable Vehicle Listing', fr: 'Activer l\'inscription de véhicules' },
  'admin.recentActions': { en: 'Recent Actions', fr: 'Actions récentes' },
  'admin.auditTrail': { en: 'Audit trail for vehicle module operations', fr: 'Journal d\'audit pour les opérations du module véhicule' },
  'admin.freeTier': { en: 'Free Tier', fr: 'Niveau gratuit' },
  // CreateVehicleListingPage
  'vehicleListing.financed': { en: 'Financed', fr: 'Financé' },
  'vehicleListing.lienExists': { en: 'Lien Exists', fr: 'Privilège existant' },
  'vehicleListing.pendingRelease': { en: 'Pending Release', fr: 'En attente de mainlevée' },
  'vehicleListing.mechanicalNotes': { en: 'Mechanical Notes', fr: 'Notes mécaniques' },
  'vehicleListing.cosmeticNotes': { en: 'Cosmetic Notes', fr: 'Notes esthétiques' },
  'vehicleListing.timedAuction': { en: 'Timed Auction', fr: 'Enchère minutée' },
  'vehicleListing.liveAuction': { en: 'Live Auction', fr: 'Enchère en direct' },
  'vehicleListing.buyNowOnly': { en: 'Buy Now Only', fr: 'Achat immédiat seulement' },
  'vehicleListing.dealersOnly': { en: 'Dealers Only', fr: 'Concessionnaires seulement' },
  'vehicleListing.infoAccurate': { en: 'All information provided is accurate and complete', fr: 'Toutes les informations fournies sont exactes et complètes' },
  'vehicleListing.legalAuthority': { en: 'You have legal authority to sell this vehicle', fr: 'Vous avez l\'autorité légale pour vendre ce véhicule' },
  'vehicleListing.respondPromptly': { en: 'You will respond to buyer inquiries promptly', fr: 'Vous répondrez rapidement aux demandes des acheteurs' },
  // SellerFinancialsPage
  'seller.financialOverview': { en: 'Financial Overview', fr: 'Aperçu financier' },
  // SellerRegistrationPage
  'seller.accountStatus': { en: 'Seller Account Status', fr: 'Statut du compte vendeur' },
  'seller.businessPhone': { en: 'Business Phone', fr: 'Téléphone professionnel' },
  'seller.businessAddress': { en: 'Business Address', fr: 'Adresse professionnelle' },
  'seller.licenseProvince': { en: 'License Province', fr: 'Province du permis' },
  'seller.applicationReview': { en: 'Your application will be reviewed by our team', fr: 'Votre candidature sera examinée par notre équipe' },
  // VehicleDetailPage
  'auction.loginToBid': { en: 'Login to Bid', fr: 'Connectez-vous pour enchérir' },
  'auction.buyerProtection': { en: 'Buyer Protection', fr: 'Protection acheteur' },
  'auction.securePayment': { en: 'Secure Payment', fr: 'Paiement sécurisé' },
  'vehicles.inspectVehicle': { en: 'You are responsible for inspecting the vehicle', fr: 'Vous êtes responsable de l\'inspection du véhicule' },
  'vehicles.sellerDisclosure': { en: 'The seller is responsible for title and ownership disclosure', fr: 'Le vendeur est responsable de la divulgation du titre et de la propriété' },
  'auction.allBidsLegallyBinding': { en: 'All bids are legally binding', fr: 'Toutes les enchères sont juridiquement contraignantes' },
  'vehicles.vehicleSpecifications': { en: 'Vehicle Specifications', fr: 'Spécifications du véhicule' },
  'vehicles.description': { en: 'Description', fr: 'Description' },
  'vehicles.documentation': { en: 'Documentation', fr: 'Documentation' },
  'vehicles.conditionReport': { en: 'Condition Report', fr: 'Rapport d\'état' },
  'vehicles.emailConfirmed': { en: 'Email Confirmed', fr: 'Courriel confirmé' },
  'vehicles.phoneVerified': { en: 'Phone Verified', fr: 'Téléphone vérifié' },
  'vehicles.licenseVerified': { en: 'License Verified', fr: 'Permis vérifié' },
};

let added = 0;
for (const [key, vals] of Object.entries(keys)) {
  const enAdded = setKey(en, key, vals.en);
  const frAdded = setKey(fr, key, vals.fr);
  if (enAdded || frAdded) added++;
}

fs.writeFileSync(EN_PATH, JSON.stringify(en, null, 2) + '\n', 'utf8');
fs.writeFileSync(FR_PATH, JSON.stringify(fr, null, 2) + '\n', 'utf8');
console.log(`Added ${added} new keys (${Object.keys(keys).length} total processed).`);
