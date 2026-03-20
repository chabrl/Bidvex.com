#!/usr/bin/env node
/**
 * P2: Replace all hardcoded English strings with t() calls
 * Also adds useTranslation import + hook where needed
 */
const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '../src');

// Track stats
let filesModified = 0;
let stringsReplaced = 0;

function processFile(relPath, replacements, opts = {}) {
  const fullPath = path.join(SRC, relPath);
  if (!fs.existsSync(fullPath)) {
    console.warn(`SKIP: ${relPath} not found`);
    return;
  }
  let content = fs.readFileSync(fullPath, 'utf8');
  const original = content;

  // Add useTranslation import if needed
  if (opts.addImport && !content.includes('useTranslation')) {
    // Find last import line
    const importLines = content.split('\n');
    let lastImportIdx = 0;
    for (let i = 0; i < importLines.length; i++) {
      if (importLines[i].startsWith('import ')) lastImportIdx = i;
    }
    importLines.splice(lastImportIdx + 1, 0, "import { useTranslation } from 'react-i18next';");
    content = importLines.join('\n');
  }

  // Add hook call if needed (after first line of component body)
  if (opts.addHook && !content.includes("const { t }") && !content.includes("const {t}")) {
    // Find the component function and add hook after first line
    // Common patterns: function Component() { ... or const Component = () => { ...
    // or export default function Component() { ...
    // Just add after first { after the component declaration
    const hookPatterns = [
      // Arrow function component: const X = (...) => {
      /^((?:export\s+)?const\s+\w+\s*=\s*\([^)]*\)\s*=>\s*\{)/m,
      // Function declaration: function X(...) {  
      /^((?:export\s+default\s+)?function\s+\w+\s*\([^)]*\)\s*\{)/m,
    ];
    
    let added = false;
    for (const pat of hookPatterns) {
      const match = content.match(pat);
      if (match) {
        const insertPos = content.indexOf(match[0]) + match[0].length;
        content = content.slice(0, insertPos) + '\n  const { t } = useTranslation();' + content.slice(insertPos);
        added = true;
        break;
      }
    }
    
    if (!added) {
      // Fallback: find `const [` (first useState) and insert before it
      const stateIdx = content.indexOf('const [');
      if (stateIdx > 0) {
        content = content.slice(0, stateIdx) + 'const { t } = useTranslation();\n  ' + content.slice(stateIdx);
      }
    }
  }

  // Apply replacements
  for (const [oldStr, newStr] of replacements) {
    if (content.includes(oldStr)) {
      content = content.replace(oldStr, newStr);
      stringsReplaced++;
    } else {
      // Try a more flexible match (different quote styles, whitespace)
      const flexOld = oldStr.replace(/"/g, "'");
      if (content.includes(flexOld)) {
        content = content.replace(flexOld, newStr.replace(/"/g, "'"));
        stringsReplaced++;
      }
    }
  }

  if (content !== original) {
    fs.writeFileSync(fullPath, content, 'utf8');
    filesModified++;
    console.log(`  ${relPath}: ${replacements.length} replacements`);
  }
}

console.log('P2: Fixing hardcoded strings...\n');

// ═══ Priority 1: AuthPage ═══
processFile('pages/AuthPage.js', [
  ['>New Password</Label>', '>{t("auth.newPasswordLabel")}</Label>'],
  ['>Confirm Password</Label>', '>{t("auth.confirmPasswordLabel")}</Label>'],
  ['<>Set New Password</>', '<>{t("auth.setNewPassword")}</>'],
]);

// ═══ Priority 2: Marketplace ═══
processFile('components/DecomposedMarketplace.js', [
  ['<option value="-promoted">Promoted First</option>', '<option value="-promoted">{t("marketplace.promotedFirst")}</option>'],
  ['<option value="ending_soon">Ending Soon</option>', '<option value="ending_soon">{t("marketplace.endingSoon")}</option>'],
  ['<option value="-created_at">Newest First</option>', '<option value="-created_at">{t("marketplace.newestFirst")}</option>'],
  ['<option value="">All Conditions</option>', '<option value="">{t("marketplace.allConditions")}</option>'],
  ['<option value="like_new">Like New</option>', '<option value="like_new">{t("marketplace.likeNew")}</option>'],
], { addImport: true, addHook: true });

processFile('components/FlattenedMarketplace.js', [
  ['<option value="">All Categories</option>', '<option value="">{t("marketplace.allCategories")}</option>'],
  ['<option value="">All Conditions</option>', '<option value="">{t("marketplace.allConditions")}</option>'],
  ['<option value="like_new">Like New</option>', '<option value="like_new">{t("marketplace.likeNew")}</option>'],
  ['<option value="excellent">Excellent</option>', '<option value="excellent">{t("marketplace.excellent")}</option>'],
  ['<option value="-promoted">Featured First</option>', '<option value="-promoted">{t("marketplace.featuredFirst")}</option>'],
  ['<option value="ending_soon">Ending Soon</option>', '<option value="ending_soon">{t("marketplace.endingSoon")}</option>'],
  ['<option value="-created_at">Newest First</option>', '<option value="-created_at">{t("marketplace.newestFirst")}</option>'],
]);

// ═══ Priority 3: BuyerDashboard ═══
processFile('pages/BuyerDashboard.js', [
  ['>Auction Ended</Badge>', '>{t("auction.auctionEnded")}</Badge>'],
  ['>Purchase History</h3>', '>{t("dashboard.buyer.purchaseHistory")}</h3>'],
]);

// ═══ Components ═══
processFile('components/AutoBidModal.js', [
  ['>Current Bid</span>', '>{t("bidding.currentBid")}</span>'],
  ['>Maximum Bid Amount</Label>', '>{t("bidding.maxBidAmount")}</Label>'],
], { addImport: true, addHook: true });

processFile('components/AvatarUpload.js', [
  ['>Edit Profile Photo</span>', '>{t("profile.editProfilePhoto")}</span>'],
], { addImport: true, addHook: true });

processFile('components/BuyNowButton.js', [
  ['>Buy Now</span>', '>{t("marketplace.buyNowLabel")}</span>'],
], { addImport: true, addHook: true });

processFile('components/LocationSearchMap.js', [
  ['>Error loading maps</p>', '>{t("common.errorLoadingMaps")}</p>'],
], { addImport: true, addHook: true });

processFile('components/LocationSelector.js', [
  ['>United States</option>', '>{t("locationSelector.unitedStates")}</option>'],
]);

processFile('components/PromotionManagerModal.js', [
  ['>All Ages</option>', '>{t("admin.allAges")}</option>'],
  ['>Interests</h4>', '>{t("admin.interests")}</h4>'],
], { addImport: true, addHook: true });

processFile('components/RealtimeBiddingPanel.js', [
  ['>This lot contains', '>{t("auction.thisLotContains")}'],
], { addImport: true, addHook: true });

processFile('components/ShareButton.js', [
  ['>Copy Link</span>', '>{t("common.copyLink")}</span>'],
  ['>Facebook</span>', '>{t("common.facebook")}</span>'],
], { addImport: true, addHook: true });

processFile('components/SocialShare.js', [
  ['>Copy Link</span>', '>{t("common.copyLink")}</span>'],
], { addImport: true, addHook: true });

processFile('components/TrendySubscriptionCards.js', [
  ['>Subtotal</span>', '>{t("subscription.subtotal")}</span>'],
  ['>Processing fee</span>', '>{t("subscription.processingFee")}</span>'],
], { addImport: true, addHook: true });

// ═══ HeroBannerEditor ═══
processFile('components/admin/HeroBannerEditor.js', [
  ['>Desktop Image</label>', '>{t("admin.desktopImage")}</label>'],
  ['>Mobile Image</label>', '>{t("admin.mobileImage")}</label>'],
  ['>Title Color</label>', '>{t("admin.titleColor")}</label>'],
  ['>Subtitle Color</label>', '>{t("admin.subtitleColor")}</label>'],
  ['>Button Background</label>', '>{t("admin.buttonBackground")}</label>'],
  ['>Button Text Color</label>', '>{t("admin.buttonTextColor")}</label>'],
  ['>Overlay Color</label>', '>{t("admin.overlayColor")}</label>'],
  ['>Overlay Opacity</label>', '>{t("admin.overlayOpacity")}</label>'],
  ['>Font Family</label>', '>{t("admin.fontFamily")}</label>'],
  ['>Title Size</label>', '>{t("admin.titleSize")}</label>'],
  ['>Subtitle Size</label>', '>{t("admin.subtitleSize")}</label>'],
], { addImport: true, addHook: true });

// ═══ Vehicle components ═══
processFile('components/vehicles/AuctionRulesDisplay.js', [
  ['>Bids in final', '>{t("auction.bidsInFinal")}'],
  ['>Binding bids</span>', '>{t("auction.bindingBids")}</span>'],
  ['>Tiered increments</span>', '>{t("auction.tieredIncrements")}</span>'],
  ['>Transparent history</span>', '>{t("auction.transparentHistory")}</span>'],
], { addImport: true, addHook: true });

processFile('components/vehicles/LegalDisclaimers.js', [
  ['>All bids are legally binding contracts', '>{t("auction.allBidsBinding")}'],
  ['>Your deposit of', '>{t("auction.yourDepositOf")}'],
], { addImport: true, addHook: true });

processFile('components/vehicles/PricingBreakdown.js', [
  ['>Total Payable</span>', '>{t("fees.totalPayable")}</span>'],
  ['>Deposit Credit</span>', '>{t("fees.depositCredit")}</span>'],
], { addImport: true, addHook: true });

processFile('components/vehicles/PricingCalculator.js', [
  ['>Enter a bid amount to see pricing breakdown</p>', '>{t("fees.enterBidAmount")}</p>'],
  ['>Transaction processing and platform service fee</p>', '>{t("fees.transactionFeeDesc")}</p>'],
], { addImport: true, addHook: true });

processFile('components/vehicles/SellerDocumentManager.js', [
  ['>Required Documents</h3>', '>{t("vehicles.requiredDocuments")}</h3>'],
], { addImport: true, addHook: true });

// ═══ Pages ═══
processFile('components/AdminBannerManager.js', [
  ['>Banner Title</Label>', '>{t("admin.bannerTitle")}</Label>'],
  ['>Banner Image</Label>', '>{t("admin.bannerImage")}</Label>'],
], { addImport: true, addHook: true });

processFile('pages/AdminTaxDashboard.js', [
  ['>Start Date</Label>', '>{t("admin.startDate")}</Label>'],
  ['>End Date</Label>', '>{t("admin.endDate")}</Label>'],
  ['>Detailed Regional Breakdown</h3>', '>{t("admin.detailedBreakdown")}</h3>'],
], { addImport: true, addHook: true });

processFile('pages/CreateListingPage.js', [
  ['>Account Settings</Link>', '>{t("profile.accountSettingsLink")}</Link>'],
]);

processFile('pages/InviteAcceptPage.js', [
  ['>Full Name</Label>', '>{t("auth.fullNameLabel")}</Label>'],
  ['>Password</Label>', '>{t("auth.passwordLabel")}</Label>'],
  ['>Confirm Password</Label>', '>{t("auth.confirmPasswordLabel")}</Label>'],
], { addImport: true, addHook: true });

processFile('pages/LegalPage.js', [
  ['>You must be at least', '>{t("legal.mustBeAtLeast")}'],
  ['>Full payment for all winning bids is due within', '>{t("legal.fullPaymentDue")}'],
  ['>Payments not received by the due date may incur a late payment penalty of', '>{t("legal.latePaymentPenalty")}'],
  ['>All payments are handled via', '>{t("legal.paymentsHandledVia")}'],
  ['>These Terms and your use of the Platform are governed by and construed in accordance with the laws of the', '>{t("legal.governedByLaws")}'],
  ['>Province of Quebec', '>{t("legal.provinceOfQuebec")}'],
  ['>This policy is designed to comply with the', '>{t("legal.compliancePolicy")}'],
  ['>Encryption in transit</li>', '>{t("legal.encryptionInTransit")}</li>'],
  ['>Encryption at rest</li>', '>{t("legal.encryptionAtRest")}</li>'],
  ['>Payment compliance</li>', '>{t("legal.paymentCompliance")}</li>'],
], { addImport: true, addHook: true });

processFile('pages/ProfileSettingsPage.js', [
  ['>Manage your payment methods for bidding</p>', '>{t("profile.managePaymentMethods")}</p>'],
]);

processFile('pages/SubscriptionPricingPage.js', [
  ['>Payment setup pending</span>', '>{t("subscription.paymentSetupPending")}</span>'],
  ['>Cancel Anytime</span>', '>{t("subscription.cancelAnytime")}</span>'],
  ['>Instant Access</span>', '>{t("subscription.instantAccess")}</span>'],
], { addImport: true, addHook: true });

processFile('pages/ClientEmailMarketing.js', [
  ['>Auction Alert</span>', '>{t("admin.auctionAlert")}</span>'],
  ['>Unsubscribe</a>', '>{t("common.unsubscribe")}</a>'],
  ['>All premium templates</span>', '>{t("admin.allPremiumTemplates")}</span>'],
  ['>Priority delivery queue</span>', '>{t("admin.priorityDelivery")}</span>'],
  ['>Advanced analytics</span>', '>{t("admin.advancedAnalytics")}</span>'],
  ['>Campaign Performance</h3>', '>{t("admin.campaignPerformance")}</h3>'],
  ['>Add Contact</span>', '>{t("admin.addContact")}</span>'],
  ['>Bulk Add Contacts</span>', '>{t("admin.bulkAddContacts")}</span>'],
  ['>Start with a Template</h3>', '>{t("admin.startWithTemplate")}</h3>'],
], { addImport: true, addHook: true });

// ═══ Admin pages ═══
processFile('pages/admin/AIGuardDashboard.js', [
  ['>All Statuses</option>', '>{t("admin.allStatuses")}</option>'],
  ['>Pending Review</option>', '>{t("admin.pendingReview")}</option>'],
  ['>Under Investigation</option>', '>{t("admin.underInvestigation")}</option>'],
  ['>Confirmed Fraud</option>', '>{t("admin.confirmedFraud")}</option>'],
  ['>All Types</option>', '>{t("admin.allTypes")}</option>'],
], { addImport: true, addHook: true });

processFile('pages/admin/AdminLogs.js', [
  ['>User Updates</option>', '>{t("admin.userUpdates")}</option>'],
  ['>Moderation</option>', '>{t("admin.moderation")}</option>'],
  ['value="promotions">Promotions</option>', 'value="promotions">{t("admin.promotions")}</option>'],
], { addImport: true, addHook: true });

processFile('pages/admin/AffiliateManager.js', [
  ['>Payout Requests</span>', '>{t("admin.payoutRequests")}</span>'],
  ['>Manage Affiliate Status</h3>', '>{t("admin.manageAffiliateStatus")}</h3>'],
], { addImport: true, addHook: true });

processFile('pages/admin/AnalyticsDashboard.js', [
  ['>Listing Status Distribution</h3>', '>{t("admin.listingStatusDistribution")}</h3>'],
], { addImport: true, addHook: true });

processFile('pages/admin/AnnouncementManager.js', [
  ['>Create Announcement</span>', '>{t("admin.createAnnouncement")}</span>'],
  ['>All Users</option>', '>{t("admin.allUsers")}</option>'],
  ['>Buyers Only</option>', '>{t("admin.buyersOnly")}</option>'],
  ['>Sellers Only</option>', '>{t("admin.sellersOnly")}</option>'],
  ['>Business Accounts</option>', '>{t("admin.businessAccounts")}</option>'],
], { addImport: true, addHook: true });

processFile('pages/admin/AuctionControl.js', [
  ['>Set limits to maintain marketplace quality</p>', '>{t("admin.setLimitsDesc")}</p>'],
  ['>Configure auction bidding behavior</p>', '>{t("admin.configureBidding")}</p>'],
], { addImport: true, addHook: true });

processFile('pages/admin/BrandingLayoutManager.js', [
  ['>Define your brand colors</p>', '>{t("admin.defineBrandColors")}</p>'],
], { addImport: true, addHook: true });

processFile('pages/admin/CouponManager.js', [
  ['>Discount Type</Label>', '>{t("admin.discountType")}</Label>'],
  ['>Applicable Plans</Label>', '>{t("admin.applicablePlans")}</Label>'],
  ['>All Coupons</option>', '>{t("admin.allCoupons")}</option>'],
  ['>Inactive</option>', '>{t("common.inactive")}</option>'],
], { addImport: true, addHook: true });

processFile('pages/admin/CurrencyAppealsManager.js', [
  ['>Admin Notes</Label>', '>{t("admin.adminNotes")}</Label>'],
  ['>Appeal Statistics</h3>', '>{t("admin.appealStatistics")}</h3>'],
], { addImport: true, addHook: true });

processFile('pages/admin/EmailMarketingManager.js', [
  ['>Unsubscribe</a>', '>{t("common.unsubscribe")}</a>'],
  ['>Send Test Email</h3>', '>{t("admin.sendTestEmail")}</h3>'],
  ['>Preview the campaign in your inbox</p>', '>{t("admin.previewCampaign")}</p>'],
  ['>Email Address</Label>', '>{t("admin.emailAddress")}</Label>'],
  ['>Schedule Campaign</h3>', '>{t("admin.scheduleCampaign")}</h3>'],
  ['>Choose when to send this campaign</p>', '>{t("admin.chooseWhenToSend")}</p>'],
  ['>This will cancel the scheduled campaign', '>{t("admin.cancelScheduledCampaign")}'],
  ['>Keep Scheduled</Button>', '>{t("admin.keepScheduled")}</Button>'],
  ['>All Status</option>', '>{t("admin.allStatus")}</option>'],
  ['>Scheduled</option>', '>{t("admin.scheduled")}</option>'],
  ['>Cancelled</option>', '>{t("admin.cancelled")}</option>'],
  ['>From Name</Label>', '>{t("admin.fromName")}</Label>'],
  ['>Any Activity</option>', '>{t("admin.anyActivity")}</option>'],
  ['>Send Test Email</Button>', '>{t("admin.sendTestEmail")}</Button>'],
], { addImport: true, addHook: true });

processFile('pages/admin/MarketplaceSettings.js', [
  ['>Control who can create auctions</p>', '>{t("admin.controlAuctionCreation")}</p>'],
  ['>Set maximum quantities per user</p>', '>{t("admin.setMaxQuantities")}</p>'],
  ['>Configure bid increments and pricing</p>', '>{t("admin.configurePricing")}</p>'],
], { addImport: true, addHook: true });

processFile('pages/admin/PricingManager.js', [
  ['>Inactive</Badge>', '>{t("common.inactive")}</Badge>'],
  ['>Plan Active</Badge>', '>{t("admin.planActive")}</Badge>'],
], { addImport: true, addHook: true });

processFile('pages/admin/PromotionManager.js', [
  ['>Create New Promotion</span>', '>{t("admin.createNewPromotion")}</span>'],
  ['>Featured</Badge>', '>{t("homepage.featured")}</Badge>'],
  ['>Feature Listings Manually</h3>', '>{t("admin.featureListingsManually")}</h3>'],
], { addImport: true, addHook: true });

processFile('pages/admin/ReportManager.js', [
  ['>Resolved</option>', '>{t("admin.resolved")}</option>'],
], { addImport: true, addHook: true });

processFile('pages/admin/SiteModeManager.js', [
  ['>Select Site Mode</h3>', '>{t("admin.selectSiteMode")}</h3>'],
  ['>Choose how visitors will see your website</p>', '>{t("admin.chooseSiteMode")}</p>'],
  ['>Page Settings</h3>', '>{t("admin.pageSettings")}</h3>'],
  ['>Customize the message shown to visitors</p>', '>{t("admin.customizeMessage")}</p>'],
  ['>Email signups from coming soon page</p>', '>{t("admin.emailSignups")}</p>'],
  ['>Launch Subscribers</h3>', '>{t("admin.launchSubscribers")}</h3>'],
  ['>Manage email subscribers from the coming soon page</p>', '>{t("admin.manageSubscribers")}</p>'],
  ['>Subscribed</span>', '>{t("common.subscribed")}</span>'],
], { addImport: true, addHook: true });

processFile('pages/admin/SubscriptionManager.js', [
  ['>Select Plan</Label>', '>{t("admin.selectPlan")}</Label>'],
  ['>Duration Type</Label>', '>{t("admin.durationType")}</Label>'],
  ['>Number of Days</Label>', '>{t("admin.numberOfDays")}</Label>'],
  ['>End Date</Label>', '>{t("admin.endDate")}</Label>'],
  ['>Additional Days</Label>', '>{t("admin.additionalDays")}</Label>'],
  ['>All Plans</option>', '>{t("admin.allPlans")}</option>'],
  ['>All Sources</option>', '>{t("admin.allSources")}</option>'],
], { addImport: true, addHook: true });

processFile('pages/admin/TaxVerificationQueue.js', [
  ['>Receive email confirmation</span>', '>{t("admin.receiveEmailConfirmation")}</span>'],
], { addImport: true, addHook: true });

processFile('pages/admin/TrustSafetyDashboard.js', [
  ['>User Trust Scores</h3>', '>{t("admin.userTrustScores")}</h3>'],
  ['>Fraud Detection Flags</h3>', '>{t("admin.fraudDetectionFlags")}</h3>'],
  ['>Require Seller Verification</span>', '>{t("admin.requireSellerVerification")}</span>'],
  ['>Require Buyer Verification</span>', '>{t("admin.requireBuyerVerification")}</span>'],
], { addImport: true, addHook: true });

processFile('pages/admin/VehicleAdminManager.js', [
  ['>Enable Vehicle Auctions</span>', '>{t("admin.enableVehicleAuctions")}</span>'],
  ['>Enable Vehicle Listing</span>', '>{t("admin.enableVehicleListing")}</span>'],
  ['>Recent Actions</h3>', '>{t("admin.recentActions")}</h3>'],
  ['>Audit trail for vehicle module operations</p>', '>{t("admin.auditTrail")}</p>'],
  ['>Free Tier</Badge>', '>{t("admin.freeTier")}</Badge>'],
], { addImport: true, addHook: true });

// ═══ Vehicle pages ═══
processFile('pages/vehicles/CreateVehicleListingPage.js', [
  ['>Financed</option>', '>{t("vehicleListing.financed")}</option>'],
  ['>Lien Exists</option>', '>{t("vehicleListing.lienExists")}</option>'],
  ['>Pending Release</option>', '>{t("vehicleListing.pendingRelease")}</option>'],
  ['>Mechanical Notes</Label>', '>{t("vehicleListing.mechanicalNotes")}</Label>'],
  ['>Cosmetic Notes</Label>', '>{t("vehicleListing.cosmeticNotes")}</Label>'],
  ['>Timed Auction</option>', '>{t("vehicleListing.timedAuction")}</option>'],
  ['>Live Auction</option>', '>{t("vehicleListing.liveAuction")}</option>'],
  ['>Buy Now Only</option>', '>{t("vehicleListing.buyNowOnly")}</option>'],
  ['>Dealers Only</option>', '>{t("vehicleListing.dealersOnly")}</option>'],
  ['>All information provided is accurate and complete</span>', '>{t("vehicleListing.infoAccurate")}</span>'],
  ['>You have legal authority to sell this vehicle</span>', '>{t("vehicleListing.legalAuthority")}</span>'],
  ['>You will respond to buyer inquiries promptly</span>', '>{t("vehicleListing.respondPromptly")}</span>'],
], { addImport: true, addHook: true });

processFile('pages/vehicles/SellerFinancialsPage.js', [
  ['>Financial Overview</h2>', '>{t("seller.financialOverview")}</h2>'],
], { addImport: true, addHook: true });

processFile('pages/vehicles/SellerRegistrationPage.js', [
  ['>Seller Account Status</h3>', '>{t("seller.accountStatus")}</h3>'],
  ['>Business Phone</Label>', '>{t("seller.businessPhone")}</Label>'],
  ['>Business Address</Label>', '>{t("seller.businessAddress")}</Label>'],
  ['>License Province</Label>', '>{t("seller.licenseProvince")}</Label>'],
  ['>Your application will be reviewed by our team</p>', '>{t("seller.applicationReview")}</p>'],
], { addImport: true, addHook: true });

processFile('pages/vehicles/VehicleDetailPage.js', [
  ['>Login to Bid</span>', '>{t("auction.loginToBid")}</span>'],
  ['>Buyer Protection</span>', '>{t("auction.buyerProtection")}</span>'],
  ['>Secure Payment</span>', '>{t("auction.securePayment")}</span>'],
  ['>You are responsible for inspecting the vehicle', '>{t("vehicles.inspectVehicle")}'],
  ['>The seller is responsible for title and ownership disclosure', '>{t("vehicles.sellerDisclosure")}'],
  ['>All bids are legally binding', '>{t("auction.allBidsLegallyBinding")}'],
  ['>Vehicle Specifications</h3>', '>{t("vehicles.vehicleSpecifications")}</h3>'],
  ['>Description</h3>', '>{t("vehicles.description")}</h3>'],
  ['>Documentation</h3>', '>{t("vehicles.documentation")}</h3>'],
  ['>Condition Report</h3>', '>{t("vehicles.conditionReport")}</h3>'],
  ['>Email Confirmed</span>', '>{t("vehicles.emailConfirmed")}</span>'],
  ['>Phone Verified</span>', '>{t("vehicles.phoneVerified")}</span>'],
  ['>License Verified</span>', '>{t("vehicles.licenseVerified")}</span>'],
], { addImport: true, addHook: true });

console.log(`\nDone: ${filesModified} files modified, ${stringsReplaced} strings replaced.`);
