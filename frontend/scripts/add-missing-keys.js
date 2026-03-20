#!/usr/bin/env node
/**
 * Add all missing translation keys identified by the audit
 */
const fs = require('fs');
const path = require('path');

const EN_PATH = path.resolve(__dirname, '../src/locales/en.json');
const FR_PATH = path.resolve(__dirname, '../src/locales/fr.json');

const en = JSON.parse(fs.readFileSync(EN_PATH, 'utf8'));
const fr = JSON.parse(fs.readFileSync(FR_PATH, 'utf8'));

// Missing keys with real EN and FR translations
const missing = {
  // Marketplace
  'marketplace.browseItems': { en: 'Browse Items', fr: 'Parcourir les articles' },
  'marketplace.itemsFromAuctions': { en: 'Items from auctions', fr: 'Articles des enchères' },
  'marketplace.subtitle': { en: 'Find your next great deal', fr: 'Trouvez votre prochaine bonne affaire' },
  'marketplace.featuredFirst': { en: 'Featured First', fr: 'En vedette d\'abord' },
  'marketplace.privateSaleTax': { en: 'Private sale tax', fr: 'Taxe de vente privée' },
  'marketplace.quickBid': { en: 'Quick Bid', fr: 'Enchère rapide' },
  'marketplace.startingFrom': { en: 'Starting from', fr: 'À partir de' },
  
  // Affiliate
  'affiliate.loadFailed': { en: 'Failed to load affiliate data', fr: 'Échec du chargement des données d\'affiliation' },
  'affiliate.enterValidAmount': { en: 'Please enter a valid amount', fr: 'Veuillez entrer un montant valide' },
  'affiliate.insufficientBalance': { en: 'Insufficient balance', fr: 'Solde insuffisant' },
  'affiliate.withdrawalSubmitted': { en: 'Withdrawal submitted successfully', fr: 'Retrait soumis avec succès' },
  'affiliate.withdrawalFailed': { en: 'Withdrawal failed', fr: 'Échec du retrait' },
  'affiliate.shareOn': { en: 'Share on', fr: 'Partager sur' },
  'affiliate.referralsDesc': { en: 'People who signed up using your link', fr: 'Personnes inscrites via votre lien' },
  'affiliate.referralName': { en: 'Referral Name', fr: 'Nom du référé' },
  'affiliate.signupDate': { en: 'Signup Date', fr: 'Date d\'inscription' },
  'affiliate.status': { en: 'Status', fr: 'Statut' },
  'affiliate.commission': { en: 'Commission', fr: 'Commission' },
  'affiliate.payoutDesc': { en: 'Request a payout from your earnings', fr: 'Demander un versement de vos gains' },
  'affiliate.enterAmount': { en: 'Enter amount', fr: 'Entrez le montant' },
  'affiliate.availableBalance': { en: 'Available Balance', fr: 'Solde disponible' },

  // Auth
  'auth.welcomeMessage': { en: 'Welcome to BidVex!', fr: 'Bienvenue sur BidVex!' },
  'auth.accountCreatedMessage': { en: 'Your account has been created successfully', fr: 'Votre compte a été créé avec succès' },
  'auth.authFailedMessage': { en: 'Authentication failed. Please try again.', fr: 'Échec de l\'authentification. Veuillez réessayer.' },
  'auth.companyName': { en: 'Company Name', fr: 'Nom de l\'entreprise' },
  'auth.taxNumber': { en: 'Tax Number', fr: 'Numéro de taxe' },
  'auth.emailRequired': { en: 'Email is required', fr: 'Le courriel est requis' },
  'auth.resetEmailSent': { en: 'Reset email sent', fr: 'Courriel de réinitialisation envoyé' },
  'auth.forgotPasswordDesc': { en: 'Enter your email to receive a reset link', fr: 'Entrez votre courriel pour recevoir un lien de réinitialisation' },
  'auth.checkYourEmail': { en: 'Check your email', fr: 'Vérifiez votre courriel' },
  'auth.resetEmailSentDesc': { en: 'We\'ve sent a password reset link to your email', fr: 'Nous avons envoyé un lien de réinitialisation à votre courriel' },
  'auth.emailPlaceholder': { en: 'Enter your email address', fr: 'Entrez votre adresse courriel' },
  'auth.sendResetLink': { en: 'Send Reset Link', fr: 'Envoyer le lien de réinitialisation' },
  'auth.whatToDoNext': { en: 'What to do next', fr: 'Que faire ensuite' },
  'auth.checkInbox': { en: 'Check your inbox', fr: 'Vérifiez votre boîte de réception' },
  'auth.checkSpam': { en: 'Check your spam folder', fr: 'Vérifiez votre dossier indésirables' },
  'auth.clickResetLink': { en: 'Click the reset link in the email', fr: 'Cliquez sur le lien de réinitialisation dans le courriel' },
  'auth.linkExpires': { en: 'The link expires in 1 hour', fr: 'Le lien expire dans 1 heure' },
  'auth.sendAnotherEmail': { en: 'Send another email', fr: 'Envoyer un autre courriel' },
  'auth.backToLogin': { en: 'Back to login', fr: 'Retour à la connexion' },
  'auth.signUp': { en: 'Sign Up', fr: 'S\'inscrire' },
  'auth.noResetToken': { en: 'No reset token provided', fr: 'Aucun jeton de réinitialisation fourni' },
  'auth.invalidToken': { en: 'Invalid or expired token', fr: 'Jeton invalide ou expiré' },
  'auth.tokenVerificationFailed': { en: 'Token verification failed', fr: 'Échec de la vérification du jeton' },
  'auth.tokenVerificationError': { en: 'An error occurred during verification', fr: 'Une erreur est survenue lors de la vérification' },
  'auth.passwordTooShort': { en: 'Password must be at least 8 characters', fr: 'Le mot de passe doit contenir au moins 8 caractères' },
  'auth.passwordsDontMatch': { en: 'Passwords don\'t match', fr: 'Les mots de passe ne correspondent pas' },
  'auth.passwordResetSuccess': { en: 'Password reset successful', fr: 'Réinitialisation du mot de passe réussie' },
  'auth.passwordResetSuccessMessage': { en: 'Your password has been reset successfully', fr: 'Votre mot de passe a été réinitialisé avec succès' },
  'auth.passwordResetFailed': { en: 'Password reset failed', fr: 'Échec de la réinitialisation du mot de passe' },
  'auth.verifyingToken': { en: 'Verifying token...', fr: 'Vérification du jeton...' },
  'auth.invalidResetLink': { en: 'Invalid reset link', fr: 'Lien de réinitialisation invalide' },
  'auth.possibleReasons': { en: 'Possible reasons:', fr: 'Raisons possibles :' },
  'auth.linkExpired': { en: 'The link has expired', fr: 'Le lien a expiré' },
  'auth.linkAlreadyUsed': { en: 'The link has already been used', fr: 'Le lien a déjà été utilisé' },
  'auth.linkInvalid': { en: 'The link is invalid', fr: 'Le lien est invalide' },
  'auth.requestNewLink': { en: 'Request a new link', fr: 'Demander un nouveau lien' },
  'auth.passwordResetComplete': { en: 'Password reset complete', fr: 'Réinitialisation terminée' },
  'auth.passwordResetCompleteDesc': { en: 'Your password has been updated', fr: 'Votre mot de passe a été mis à jour' },
  'auth.redirectingToLogin': { en: 'Redirecting to login...', fr: 'Redirection vers la connexion...' },
  'auth.goToLogin': { en: 'Go to login', fr: 'Aller à la connexion' },
  'auth.resetPassword': { en: 'Reset Password', fr: 'Réinitialiser le mot de passe' },
  'auth.resetPasswordDesc': { en: 'Enter your new password', fr: 'Entrez votre nouveau mot de passe' },
  'auth.linkExpiresIn': { en: 'Link expires in', fr: 'Le lien expire dans' },
  'auth.newPassword': { en: 'New Password', fr: 'Nouveau mot de passe' },
  'auth.enterNewPassword': { en: 'Enter new password', fr: 'Entrez le nouveau mot de passe' },
  'auth.passwordMinLength': { en: 'Minimum 8 characters', fr: 'Minimum 8 caractères' },
  'auth.confirmPassword': { en: 'Confirm Password', fr: 'Confirmer le mot de passe' },
  'auth.confirmNewPassword': { en: 'Confirm new password', fr: 'Confirmer le nouveau mot de passe' },
  'auth.passwordsMustMatch': { en: 'Passwords must match', fr: 'Les mots de passe doivent correspondre' },
  'auth.resettingPassword': { en: 'Resetting password...', fr: 'Réinitialisation en cours...' },
  'auth.resetPasswordBtn': { en: 'Reset Password', fr: 'Réinitialiser' },

  // Common
  'common.sending': { en: 'Sending...', fr: 'Envoi...' },
  'common.status': { en: 'Status', fr: 'Statut' },
  'common.minutes': { en: 'minutes', fr: 'minutes' },

  // Homepage
  'homepage.endingSoonDesc': { en: 'Last chance to bid on these auctions', fr: 'Dernière chance de miser sur ces enchères' },
  'homepage.ended': { en: 'Ended', fr: 'Terminé' },
  'homepage.bids': { en: 'bids', fr: 'enchères' },
  'homepage.featured': { en: 'Featured', fr: 'En vedette' },
  'homepage.curatedAuctions': { en: 'Curated Auctions', fr: 'Enchères sélectionnées' },
  'homepage.handPicked': { en: 'Hand-picked by our editors', fr: 'Sélectionnées par nos éditeurs' },
  'homepage.topPerformers': { en: 'Top Performers', fr: 'Meilleurs performeurs' },
  'homepage.totalSales': { en: 'Total Sales', fr: 'Ventes totales' },
  'homepage.itemsSold': { en: 'Items Sold', fr: 'Articles vendus' },

  // Listing
  'listing.verificationRequired': { en: 'Verification Required', fr: 'Vérification requise' },

  // Lots Marketplace
  'lotsMarketplace.title': { en: 'Lots Marketplace', fr: 'Marché des lots' },
  'lotsMarketplace.subtitle': { en: 'Browse multi-item auction lots', fr: 'Parcourez les enchères multi-articles' },
  'lotsMarketplace.noLots': { en: 'No lots available', fr: 'Aucun lot disponible' },
  'lotsMarketplace.noLotsDesc': { en: 'Check back later for new lot auctions', fr: 'Revenez plus tard pour de nouvelles enchères de lots' },

  // Auction
  'auction.englishTerms': { en: 'English Terms', fr: 'Conditions en anglais' },
  'auction.frenchTerms': { en: 'French Terms', fr: 'Conditions en français' },
  'auction.noTermsProvided': { en: 'No terms provided', fr: 'Aucune condition fournie' },
  'auction.mustAgreeToTermsFirst': { en: 'You must agree to the terms first', fr: 'Vous devez d\'abord accepter les conditions' },
  'auction.agreeToTermsToPlaceBid': { en: 'Agree to terms to place a bid', fr: 'Acceptez les conditions pour placer une enchère' },

  // Errors
  'errors.auctionMissing': { en: 'Auction not found', fr: 'Enchère introuvable' },
  'errors.needHelp': { en: 'Need help?', fr: 'Besoin d\'aide?' },
  'errors.paymentErrorDesc': { en: 'There was an issue with your payment', fr: 'Un problème est survenu avec votre paiement' },
  'errors.verificationTimeout': { en: 'Verification timed out', fr: 'Délai de vérification expiré' },
  'errors.timeoutDesc': { en: 'The verification process took too long', fr: 'Le processus de vérification a pris trop de temps' },

  // Payment
  'payment.cardDeleted': { en: 'Card deleted successfully', fr: 'Carte supprimée avec succès' },
  'payment.cardDeleteFailed': { en: 'Failed to delete card', fr: 'Échec de la suppression de la carte' },

  // Payment Success
  'paymentSuccess.contactSupport': { en: 'Contact Support', fr: 'Contacter le support' },
  'paymentSuccess.processing': { en: 'Processing your payment...', fr: 'Traitement de votre paiement...' },
  'paymentSuccess.pleaseWait': { en: 'Please wait while we confirm your payment', fr: 'Veuillez patienter pendant la confirmation de votre paiement' },
  'paymentSuccess.step2': { en: 'Step 2', fr: 'Étape 2' },
  'paymentSuccess.continueShop': { en: 'Continue Shopping', fr: 'Continuer les achats' },

  // Watchlist
  'watchlist.goToAuction': { en: 'Go to Auction', fr: 'Aller à l\'enchère' },
  'watchlist.viewLot': { en: 'View Lot', fr: 'Voir le lot' },
};

// Set nested key in object
function setKey(obj, dotKey, value) {
  const parts = dotKey.split('.');
  let current = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    if (!current[parts[i]] || typeof current[parts[i]] !== 'object') {
      current[parts[i]] = {};
    }
    current = current[parts[i]];
  }
  current[parts[parts.length - 1]] = value;
}

let added = 0;
for (const [key, { en: enVal, fr: frVal }] of Object.entries(missing)) {
  setKey(en, key, enVal);
  setKey(fr, key, frVal);
  added++;
}

fs.writeFileSync(EN_PATH, JSON.stringify(en, null, 2) + '\n', 'utf8');
fs.writeFileSync(FR_PATH, JSON.stringify(fr, null, 2) + '\n', 'utf8');

console.log(`Added ${added} missing keys to both JSON files.`);
