#!/usr/bin/env node
/**
 * P2 Phase 2: Line-based precise replacements for remaining hardcoded strings
 * Uses exact line numbers from the audit report.
 */
const fs = require('fs');
const path = require('path');
const SRC = path.resolve(__dirname, '../src');

let count = 0;

function fixLine(relPath, lineNum, oldText, tKey) {
  const full = path.join(SRC, relPath);
  const lines = fs.readFileSync(full, 'utf8').split('\n');
  const idx = lineNum - 1;
  if (idx < 0 || idx >= lines.length) return false;
  
  const line = lines[idx];
  if (!line.includes(oldText)) {
    // Try adjacent lines (line numbers can shift after imports added)
    for (let offset = -3; offset <= 3; offset++) {
      if (idx + offset >= 0 && idx + offset < lines.length && lines[idx + offset].includes(oldText)) {
        lines[idx + offset] = lines[idx + offset].replace(oldText, `{t("${tKey}")}`);
        fs.writeFileSync(full, lines.join('\n'), 'utf8');
        count++;
        return true;
      }
    }
    console.warn(`  MISS: ${relPath}:${lineNum} "${oldText}" not found`);
    return false;
  }
  
  lines[idx] = line.replace(oldText, `{t("${tKey}")}`);
  fs.writeFileSync(full, lines.join('\n'), 'utf8');
  count++;
  return true;
}

console.log('P2 Phase 2: Fixing remaining hardcoded strings...\n');

// Components
fixLine('components/AutoBidModal.js', 156, 'Current Bid', 'bidding.currentBid');
fixLine('components/AvatarUpload.js', 92, 'Edit Profile Photo', 'profile.editProfilePhoto');
fixLine('components/BuyNowButton.js', 211, 'Buy Now', 'marketplace.buyNowLabel');
fixLine('components/LocationSearchMap.js', 79, 'Error loading maps', 'common.errorLoadingMaps');
fixLine('components/LocationSelector.js', 141, 'United States', 'locationSelector.unitedStates');
fixLine('components/PromotionManagerModal.js', 196, 'Interests', 'admin.interests');
fixLine('components/RealtimeBiddingPanel.js', 222, 'This lot contains', 'auction.thisLotContains');

// HeroBannerEditor (all label tags)
fixLine('components/admin/HeroBannerEditor.js', 537, 'Desktop Image', 'admin.desktopImage');
fixLine('components/admin/HeroBannerEditor.js', 557, 'Mobile Image', 'admin.mobileImage');
fixLine('components/admin/HeroBannerEditor.js', 589, 'Title Color', 'admin.titleColor');
fixLine('components/admin/HeroBannerEditor.js', 606, 'Subtitle Color', 'admin.subtitleColor');
fixLine('components/admin/HeroBannerEditor.js', 627, 'Button Background', 'admin.buttonBackground');
fixLine('components/admin/HeroBannerEditor.js', 644, 'Button Text Color', 'admin.buttonTextColor');
fixLine('components/admin/HeroBannerEditor.js', 665, 'Overlay Color', 'admin.overlayColor');
fixLine('components/admin/HeroBannerEditor.js', 683, 'Overlay Opacity', 'admin.overlayOpacity');
fixLine('components/admin/HeroBannerEditor.js', 704, 'Font Family', 'admin.fontFamily');
fixLine('components/admin/HeroBannerEditor.js', 724, 'Title Size', 'admin.titleSize');
fixLine('components/admin/HeroBannerEditor.js', 740, 'Subtitle Size', 'admin.subtitleSize');

// Vehicle components
fixLine('components/vehicles/PricingCalculator.js', 245, 'Enter a bid amount to see pricing breakdown', 'fees.enterBidAmount');
fixLine('components/vehicles/SellerDocumentManager.js', 390, 'Required Documents', 'vehicles.requiredDocuments');

// Pages
fixLine('pages/AdminTaxDashboard.js', 384, 'Detailed Regional Breakdown', 'admin.detailedBreakdown');
fixLine('pages/BuyerDashboard.js', 331, 'Auction Ended', 'auction.auctionEnded');
fixLine('pages/BuyerDashboard.js', 403, 'Purchase History', 'dashboard.buyer.purchaseHistory');

fixLine('pages/ClientEmailMarketing.js', 377, 'Auction Alert', 'admin.auctionAlert');
fixLine('pages/ClientEmailMarketing.js', 507, 'All premium templates', 'admin.allPremiumTemplates');
fixLine('pages/ClientEmailMarketing.js', 532, 'Priority delivery queue', 'admin.priorityDelivery');
fixLine('pages/ClientEmailMarketing.js', 533, 'Advanced analytics', 'admin.advancedAnalytics');
fixLine('pages/ClientEmailMarketing.js', 957, 'Campaign Performance', 'admin.campaignPerformance');
fixLine('pages/ClientEmailMarketing.js', 989, 'Add Contact', 'admin.addContact');
fixLine('pages/ClientEmailMarketing.js', 1034, 'Bulk Add Contacts', 'admin.bulkAddContacts');
fixLine('pages/ClientEmailMarketing.js', 1079, 'Start with a Template', 'admin.startWithTemplate');

fixLine('pages/CreateListingPage.js', 174, 'Account Settings', 'profile.accountSettingsLink');
fixLine('pages/ProfileSettingsPage.js', 366, 'Manage your payment methods for bidding', 'profile.managePaymentMethods');

fixLine('pages/LegalPage.js', 140, 'Payments not received by the due date may incur a late payment penalty of', 'legal.latePaymentPenalty');
fixLine('pages/LegalPage.js', 240, 'This policy is designed to comply with the', 'legal.compliancePolicy');
fixLine('pages/LegalPage.js', 304, 'Encryption in transit', 'legal.encryptionInTransit');
fixLine('pages/LegalPage.js', 305, 'Encryption at rest', 'legal.encryptionAtRest');
fixLine('pages/LegalPage.js', 306, 'Payment compliance', 'legal.paymentCompliance');

// Admin pages
fixLine('pages/admin/AIGuardDashboard.js', 371, 'All Statuses', 'admin.allStatuses');
fixLine('pages/admin/AIGuardDashboard.js', 372, 'Pending Review', 'admin.pendingReview');
fixLine('pages/admin/AIGuardDashboard.js', 373, 'Under Investigation', 'admin.underInvestigation');
fixLine('pages/admin/AIGuardDashboard.js', 375, 'Confirmed Fraud', 'admin.confirmedFraud');
fixLine('pages/admin/AIGuardDashboard.js', 383, 'All Types', 'admin.allTypes');

fixLine('pages/admin/AdminLogs.js', 85, 'User Updates', 'admin.userUpdates');
fixLine('pages/admin/AdminLogs.js', 86, 'Moderation', 'admin.moderation');
fixLine('pages/admin/AdminLogs.js', 87, 'Promotions', 'admin.promotions');

fixLine('pages/admin/AffiliateManager.js', 83, 'Payout Requests', 'admin.payoutRequests');
fixLine('pages/admin/AffiliateManager.js', 110, 'Manage Affiliate Status', 'admin.manageAffiliateStatus');

fixLine('pages/admin/AnalyticsDashboard.js', 94, 'Listing Status Distribution', 'admin.listingStatusDistribution');

fixLine('pages/admin/AnnouncementManager.js', 87, 'Create Announcement', 'admin.createAnnouncement');

fixLine('pages/admin/AuctionControl.js', 219, 'Set limits to maintain marketplace quality', 'admin.setLimitsDesc');
fixLine('pages/admin/AuctionControl.js', 308, 'Configure auction bidding behavior', 'admin.configureBidding');

fixLine('pages/admin/BrandingLayoutManager.js', 274, 'Define your brand colors', 'admin.defineBrandColors');

fixLine('pages/admin/CouponManager.js', 474, 'All Coupons', 'admin.allCoupons');
fixLine('pages/admin/CouponManager.js', 564, 'Inactive', 'common.inactive');

fixLine('pages/admin/CurrencyAppealsManager.js', 252, 'Appeal Statistics', 'admin.appealStatistics');

fixLine('pages/admin/EmailMarketingManager.js', 775, 'Send Test Email', 'admin.sendTestEmail');
fixLine('pages/admin/EmailMarketingManager.js', 776, 'Preview the campaign in your inbox', 'admin.previewCampaign');
fixLine('pages/admin/EmailMarketingManager.js', 803, 'Schedule Campaign', 'admin.scheduleCampaign');
fixLine('pages/admin/EmailMarketingManager.js', 804, 'Choose when to send this campaign', 'admin.chooseWhenToSend');
fixLine('pages/admin/EmailMarketingManager.js', 973, 'All Status', 'admin.allStatus');
fixLine('pages/admin/EmailMarketingManager.js', 975, 'Scheduled', 'admin.scheduled');
fixLine('pages/admin/EmailMarketingManager.js', 977, 'Cancelled', 'admin.cancelled');
fixLine('pages/admin/EmailMarketingManager.js', 1144, 'Any Activity', 'admin.anyActivity');
fixLine('pages/admin/EmailMarketingManager.js', 1407, 'Send Test Email', 'admin.sendTestEmail');
fixLine('pages/admin/EmailMarketingManager.js', 1408, 'Preview the campaign in your inbox', 'admin.previewCampaign');
fixLine('pages/admin/EmailMarketingManager.js', 1412, 'Email Address', 'admin.emailAddress');

fixLine('pages/admin/MarketplaceSettings.js', 214, 'Control who can create auctions', 'admin.controlAuctionCreation');
fixLine('pages/admin/MarketplaceSettings.js', 258, 'Set maximum quantities per user', 'admin.setMaxQuantities');
fixLine('pages/admin/MarketplaceSettings.js', 304, 'Configure bid increments and pricing', 'admin.configurePricing');

fixLine('pages/admin/PricingManager.js', 487, 'Plan Active', 'admin.planActive');

fixLine('pages/admin/PromotionManager.js', 96, 'Create New Promotion', 'admin.createNewPromotion');
fixLine('pages/admin/PromotionManager.js', 110, 'Featured', 'homepage.featured');
fixLine('pages/admin/PromotionManager.js', 153, 'Feature Listings Manually', 'admin.featureListingsManually');

fixLine('pages/admin/ReportManager.js', 63, 'Resolved', 'admin.resolved');

fixLine('pages/admin/SiteModeManager.js', 322, 'Select Site Mode', 'admin.selectSiteMode');
fixLine('pages/admin/SiteModeManager.js', 323, 'Choose how visitors will see your website', 'admin.chooseSiteMode');
fixLine('pages/admin/SiteModeManager.js', 365, 'Page Settings', 'admin.pageSettings');
fixLine('pages/admin/SiteModeManager.js', 366, 'Customize the message shown to visitors', 'admin.customizeMessage');
fixLine('pages/admin/SiteModeManager.js', 470, 'Email signups from coming soon page', 'admin.emailSignups');
fixLine('pages/admin/SiteModeManager.js', 528, 'Launch Subscribers', 'admin.launchSubscribers');
fixLine('pages/admin/SiteModeManager.js', 529, 'Manage email subscribers from the coming soon page', 'admin.manageSubscribers');
fixLine('pages/admin/SiteModeManager.js', 564, 'Subscribed', 'common.subscribed');

fixLine('pages/admin/SubscriptionManager.js', 835, 'All Plans', 'admin.allPlans');
fixLine('pages/admin/SubscriptionManager.js', 846, 'All Sources', 'admin.allSources');

fixLine('pages/admin/TaxVerificationQueue.js', 235, 'Receive email confirmation', 'admin.receiveEmailConfirmation');

fixLine('pages/admin/TrustSafetyDashboard.js', 149, 'User Trust Scores', 'admin.userTrustScores');
fixLine('pages/admin/TrustSafetyDashboard.js', 180, 'Fraud Detection Flags', 'admin.fraudDetectionFlags');
fixLine('pages/admin/TrustSafetyDashboard.js', 223, 'Require Seller Verification', 'admin.requireSellerVerification');
fixLine('pages/admin/TrustSafetyDashboard.js', 224, 'Require Buyer Verification', 'admin.requireBuyerVerification');

fixLine('pages/admin/VehicleAdminManager.js', 684, 'Enable Vehicle Auctions', 'admin.enableVehicleAuctions');
fixLine('pages/admin/VehicleAdminManager.js', 740, 'Enable Vehicle Listing', 'admin.enableVehicleListing');
fixLine('pages/admin/VehicleAdminManager.js', 845, 'Recent Actions', 'admin.recentActions');
fixLine('pages/admin/VehicleAdminManager.js', 846, 'Audit trail for vehicle module operations', 'admin.auditTrail');
fixLine('pages/admin/VehicleAdminManager.js', 965, 'Free Tier', 'admin.freeTier');

// Vehicle pages
fixLine('pages/vehicles/CreateVehicleListingPage.js', 611, 'Financed', 'vehicleListing.financed');
fixLine('pages/vehicles/CreateVehicleListingPage.js', 634, 'Lien Exists', 'vehicleListing.lienExists');
fixLine('pages/vehicles/CreateVehicleListingPage.js', 635, 'Pending Release', 'vehicleListing.pendingRelease');
fixLine('pages/vehicles/CreateVehicleListingPage.js', 866, 'Timed Auction', 'vehicleListing.timedAuction');
fixLine('pages/vehicles/CreateVehicleListingPage.js', 867, 'Live Auction', 'vehicleListing.liveAuction');
fixLine('pages/vehicles/CreateVehicleListingPage.js', 868, 'Buy Now Only', 'vehicleListing.buyNowOnly');
fixLine('pages/vehicles/CreateVehicleListingPage.js', 879, 'Dealers Only', 'vehicleListing.dealersOnly');
fixLine('pages/vehicles/CreateVehicleListingPage.js', 1037, 'All information provided is accurate and complete', 'vehicleListing.infoAccurate');
fixLine('pages/vehicles/CreateVehicleListingPage.js', 1038, 'You have legal authority to sell this vehicle', 'vehicleListing.legalAuthority');
fixLine('pages/vehicles/CreateVehicleListingPage.js', 1039, 'You will respond to buyer inquiries promptly', 'vehicleListing.respondPromptly');

fixLine('pages/vehicles/SellerFinancialsPage.js', 234, 'Financial Overview', 'seller.financialOverview');
fixLine('pages/vehicles/SellerRegistrationPage.js', 171, 'Seller Account Status', 'seller.accountStatus');
fixLine('pages/vehicles/SellerRegistrationPage.js', 445, 'Your application will be reviewed by our team', 'seller.applicationReview');

fixLine('pages/vehicles/VehicleDetailPage.js', 415, 'Login to Bid', 'auction.loginToBid');
fixLine('pages/vehicles/VehicleDetailPage.js', 630, 'Vehicle Specifications', 'vehicles.vehicleSpecifications');
fixLine('pages/vehicles/VehicleDetailPage.js', 689, 'Description', 'vehicles.description');
fixLine('pages/vehicles/VehicleDetailPage.js', 712, 'Documentation', 'vehicles.documentation');
fixLine('pages/vehicles/VehicleDetailPage.js', 743, 'Condition Report', 'vehicles.conditionReport');

console.log(`\nFixed ${count} remaining strings.`);
