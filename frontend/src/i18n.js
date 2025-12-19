import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Helper to get persisted language from localStorage
const getPersistedLanguage = () => {
  try {
    const stored = localStorage.getItem('bidvex_language');
    if (stored && ['en', 'fr'].includes(stored)) {
      return stored;
    }
  } catch (e) {
    console.warn('localStorage not available for language persistence');
  }
  return null;
};

// Helper to persist language choice
export const persistLanguage = (lng) => {
  try {
    localStorage.setItem('bidvex_language', lng);
  } catch (e) {
    console.warn('Could not persist language preference');
  }
};

const resources = {
  en: {
    translation: {
      // Navigation
      nav: {
        home: 'Home',
        marketplace: 'Marketplace',
        lotsAuction: 'Lots Auction',
        sell: 'Sell',
        myAccount: 'My Account',
        login: 'Login',
        register: 'Register',
        logout: 'Logout',
        sellerDashboard: 'Seller Dashboard',
        buyerDashboard: 'Buyer Dashboard',
        adminPanel: 'Admin Panel',
        affiliateDashboard: 'Affiliate Dashboard',
        watchlist: 'Watchlist',
        messages: 'Messages',
        howItWorks: 'How It Works',
      },

      // Hero Section
      hero: {
        title: 'Discover Unique Treasures',
        subtitle: 'Your Premier Auction Marketplace',
        description: 'Bid on exclusive items or sell your treasures to a global audience',
        cta: 'Explore Auctions',
        browseAuctions: 'Browse Auctions',
        sellNow: 'Start Selling',
        howBiddingWorks: 'How Bidding Works',
        nextAuction: 'Next auction ends in',
        viewAuction: 'View Auction',
        startBidding: 'Start Bidding Today',
        discoverDeals: 'Discover rare finds and exclusive deals in our trusted marketplace',
      },

      // Homepage Sections
      homepage: {
        // Hero
        liveAuctionsNow: 'Live Auctions Happening Now',
        discover: 'Discover.',
        bid: 'Bid.',
        win: 'Win.',
        heroDescription: 'Experience the thrill of live auctions. Join thousands of bidders competing for unique items at unbeatable prices. Your next treasure awaits.',
        howItWorks: 'How It Works',
        
        // Trust Indicators
        securePayments: 'Secure Payments',
        verifiedSellers: 'Verified Sellers',
        buyerProtection: 'Buyer Protection',
        
        // Stats
        activeBidders: 'Active Bidders',
        liveAuctions: 'Live Auctions',
        itemsWon: 'Items Won',
        satisfaction: 'Satisfaction',
        
        // Sections
        endingSoon: 'Ending Soon',
        endingSoonDesc: "Don't miss out! These auctions close soon",
        hotItems: 'Hot Items',
        hotItemsDesc: 'Trending auctions with the most activity',
        featuredAuctions: 'Featured Auctions',
        curatedAuctions: 'Curated Auctions',
        handPicked: 'Hand-picked items from our top sellers',
        justListed: '🆕 Just Listed',
        freshAuctions: 'Fresh auctions added today',
        whyChooseBidvex: 'Why Choose BidVex?',
        trustedPlatform: 'The trusted platform for smart bidders',
        topSellers: 'Our Best Sellers',
        topPerformers: 'Top Performers',
        
        // Actions
        viewAll: 'View All',
        bidNow: 'Bid Now',
        learnMore: 'Learn More',
        gettingStarted: 'Getting Started',
        viewAllHotItems: 'View All Hot Items',
        
        // Status
        live: 'LIVE',
        activeBidding: 'Active bidding',
        currentBid: 'Current Bid',
        ended: 'Ended',
        views: 'views',
        bids: 'bids',
        totalSales: 'Total Sales',
        itemsSold: 'Items Sold',
        new: 'NEW',
        featured: 'Featured',
        
        // Features
        liveBidding: 'Live Bidding',
        liveBiddingDesc: 'Real-time auctions with instant updates',
        securePaymentsDesc: 'Bank-level encryption via Stripe',
        buyerProtectionDesc: 'Full refund guarantee on disputes',
        globalCommunity: 'Global Community',
        globalCommunityDesc: 'Verified buyers and sellers worldwide',
        
        // How It Works
        howItWorksTitle: 'How It Works',
        startWinning: 'Start winning amazing deals in three simple steps',
        browse: 'Browse',
        browseDesc: 'Find unique items from trusted sellers',
        bidStep: 'Bid',
        bidStepDesc: 'Place competitive bids in real-time',
        winStep: 'Win',
        winStepDesc: 'Secure your items with safe payment',
        
        // Fallback for dynamic content
        translatedFromOriginal: 'Translated from original',
      },

      // Authentication
      auth: {
        welcomeBack: 'Welcome Back',
        createAccount: 'Create Your Account',
        signInPrompt: 'Sign in to your account',
        createAccountPrompt: 'Create a new account to start bidding',
        welcomeMessage: 'Welcome back!',
        accountCreatedMessage: 'Account created successfully!',
        authFailedMessage: 'Authentication failed',
        email: 'Email',
        emailAddress: 'Email Address',
        password: 'Password',
        name: 'Full Name',
        phone: 'Phone Number',
        accountType: 'Account Type',
        personal: 'Personal',
        business: 'Business',
        address: 'Address',
        companyName: 'Company Name',
        taxNumber: 'Tax Number',
        loginBtn: 'Sign In',
        registerBtn: 'Create Account',
        googleLogin: 'Continue with Google',
        noAccount: "Don't have an account?",
        hasAccount: 'Already have an account?',
        forgotPassword: 'Forgot Password?',
        rememberMe: 'Remember Me',
      },

      // Marketplace
      marketplace: {
        title: 'Active Auctions',
        search: 'Search listings...',
        searchPlaceholder: 'Search for items, categories, or sellers...',
        category: 'Category',
        location: 'Location',
        condition: 'Condition',
        priceRange: 'Price Range',
        sortBy: 'Sort By',
        newest: 'Newest First',
        ending: 'Ending Soon',
        priceLow: 'Price: Low to High',
        priceHigh: 'Price: High to Low',
        currentBid: 'Current Bid',
        startingBid: 'Starting Bid',
        buyNow: 'Buy It Now',
        bids: 'bids',
        endsIn: 'Ends in',
        ended: 'Auction Ended',
        noResults: 'No auctions found',
        filter: 'Filter',
        clearFilters: 'Clear Filters',
      },

      // Listing Details
      listing: {
        details: 'Details',
        placeBid: 'Place Bid',
        buyNow: 'Buy Now',
        yourBid: 'Your Bid',
        submitBid: 'Submit Bid',
        bidHistory: 'Bid History',
        seller: 'Seller',
        location: 'Location',
        condition: 'Condition',
        views: 'views',
        timeLeft: 'Time Left',
        description: 'Description',
        shippingInfo: 'Shipping Information',
        paymentMethods: 'Accepted Payment Methods',
        askQuestion: 'Ask a Question',
        reportListing: 'Report Listing',
        shareLink: 'Share',
        addToWatchlist: 'Add to Watchlist',
        removeFromWatchlist: 'Remove from Watchlist',
      },

      // Bid Error Guide
      bidErrorGuide: {
        title: 'Common Bid Errors',
        subtitle: 'Understanding bidding issues and how to fix them',
        errors: {
          bidTooLow: {
            title: 'Bid must be higher than current price',
            description: 'Your bid amount is below the current price. Try bidding an amount higher than the displayed current bid.',
            solution: 'Increase your bid amount to at least match the minimum required bid.',
          },
          minimumIncrement: {
            title: 'Bid must be at least ${{amount}}',
            description: 'The minimum bid increment has not been met. Each bid must increase by a specific amount.',
            solution: 'Enter a bid amount of at least ${{amount}} to meet the minimum increment requirement.',
          },
          networkError: {
            title: 'Network error. Please check your connection.',
            description: 'Unable to connect to the server. This may be due to internet connectivity issues.',
            solution: 'Check your internet connection and try again. If the problem persists, refresh the page.',
          },
          invalidAmount: {
            title: 'Invalid bid amount',
            description: 'The bid amount entered is not a valid number or contains invalid characters.',
            solution: 'Enter a valid numeric amount without currency symbols or special characters.',
          },
          auctionEnded: {
            title: 'Auction has ended',
            description: 'This auction is no longer accepting bids as the bidding period has closed.',
            solution: 'Browse other active auctions or wait for similar items to be listed.',
          },
          insufficientFunds: {
            title: 'Insufficient funds',
            description: 'Your account balance or payment method may not cover this bid amount.',
            solution: 'Update your payment method or lower your bid amount.',
          },
          unauthorized: {
            title: 'Please sign in to bid',
            description: 'You must be logged in to place bids on auctions.',
            solution: 'Sign in to your account or create a new account to start bidding.',
          },
        },
        helpText: 'Still having trouble? Contact our support team for assistance.',
        closeButton: 'Got it',
      },

      // Dashboard
      dashboard: {
        seller: {
          title: 'Seller Dashboard',
          activeListings: 'Active Listings',
          soldItems: 'Sold Items',
          draftListings: 'Draft Listings',
          totalSales: 'Total Sales',
          createListing: 'Create New Listing',
          createLot: 'Create Lot',
          commission: 'Platform Commission: 5%',
          viewAll: 'View All',
          revenue: 'Revenue',
          activeAuctions: 'Active Auctions',
          businessAccount: 'Business Account',
          personalAccount: 'Personal Account',
          commissionRate: 'Commission',
          deleteListing: 'Are you sure you want to delete this listing?',
          listingDeleted: 'Listing deleted successfully',
          deleteFailed: 'Failed to delete listing',
          loadFailed: 'Failed to load dashboard',
        },
        buyer: {
          title: 'Buyer Dashboard',
          activeBids: 'Active Bids',
          wonItems: 'Won Items',
          watchlist: 'Watchlist',
          totalSpent: 'Total Spent',
          bidActivity: 'Bid Activity',
          savedSearches: 'Saved Searches',
        },
      },

      // Profile Settings
      profile: {
        title: 'Profile Settings',
        accountSettings: 'Account Settings',
        personalInfo: 'Personal Information',
        personalInformation: 'Personal Information',
        updateDetails: 'Update your profile details',
        preferences: 'Preferences',
        language: 'Language',
        currency: 'Preferred Currency',
        selectLanguage: 'Select Language',
        selectCurrency: 'Select Currency',
        english: 'English',
        french: 'Français',
        saveChanges: 'Save Changes',
        changesSaved: 'Changes saved successfully',
        fullName: 'Full Name',
        phoneNumber: 'Phone Number',
        address: 'Address',
        companyName: 'Company Name',
        taxNumber: 'Tax Number',
        paymentMethods: 'Payment Methods',
        notifications: 'Notifications',
        profileTab: 'Profile',
        paymentTab: 'Payment Methods',
        notificationsTab: 'Notifications',
      },

      // Currency Enforcement
      currency: {
        locked: 'Locked',
        enforced: 'Currency Enforced',
        complianceMessage: 'Currency is determined by your location to comply with local tax rules. If you\'re traveling or have moved, you can request verification.',
        requestChange: 'Request Currency Change',
        appeal: 'Appeal',
        appealSubmitted: 'Appeal submitted successfully',
        appealReason: 'Reason for Request',
        requestedCurrency: 'Requested Currency',
        submitAppeal: 'Submit Appeal',
        appealStatus: 'Appeal Status',
        pending: 'Pending',
        approved: 'Approved',
        rejected: 'Rejected',
        currentCurrency: 'Current Currency',
        enforcedCurrency: 'Enforced Currency',
        confidenceScore: 'Confidence Score',
      },

      // Admin Panel
      admin: {
        dashboard: 'Admin Dashboard',
        title: 'Admin Panel',
        overview: 'Overview',
        users: 'User Management',
        auctions: 'Auction Control',
        lots: 'Lots Management',
        analytics: 'Analytics',
        settings: 'Settings',
        trustSafety: 'Trust & Safety',
        reports: 'Reports',
        logs: 'Admin Logs',
        announcements: 'Announcements',
        promotions: 'Promotions',
        categories: 'Categories',
        currencyAppeals: 'Currency Appeals',
        affiliates: 'Affiliates',
        messaging: 'Messaging Oversight',
        moderateLots: 'Moderate Lots',
        
        // Currency Appeals Manager
        appeals: {
          title: 'Currency Appeal Requests',
          description: 'Review and manage user currency preference appeals',
          noAppeals: 'No currency appeals found',
          userName: 'User Name',
          from: 'From',
          to: 'To',
          submitted: 'Submitted',
          reason: 'Reason',
          status: 'Status',
          approve: 'Approve',
          reject: 'Reject',
          approveConfirm: 'Are you sure you want to approve this appeal?',
          rejectConfirm: 'Are you sure you want to reject this appeal?',
          approved: 'Appeal approved successfully',
          rejected: 'Appeal rejected successfully',
          error: 'Failed to update appeal',
        },

        // User Management
        userManagement: {
          searchUsers: 'Search users...',
          totalUsers: 'Total Users',
          activeUsers: 'Active Users',
          bannedUsers: 'Banned Users',
          accountType: 'Account Type',
          status: 'Status',
          actions: 'Actions',
          viewProfile: 'View Profile',
          banUser: 'Ban User',
          unbanUser: 'Unban User',
          deleteUser: 'Delete User',
        },
      },

      // Lots Auction
      lots: {
        auctionTitle: 'Lots Auction',
        multiItemAuctions: 'Multi-Item Auctions',
        comingSoon: 'Coming Soon',
        upcoming: 'Upcoming',
        activeAuctions: 'Active Auctions',
        category: 'Category',
        location: 'Location',
        items: 'Items',
        lotCount: 'Lot Count',
        lots: 'lots',
        timeRemaining: 'Time Remaining',
        endsIn: 'Ends in',
        startDate: 'Starts',
        viewDetails: 'View Details',
        viewAuction: 'View Auction',
        ended: 'Ended',
        general: 'General',
      },

      // Common UI Elements
      common: {
        loading: 'Loading...',
        save: 'Save',
        cancel: 'Cancel',
        delete: 'Delete',
        edit: 'Edit',
        close: 'Close',
        confirm: 'Confirm',
        error: 'Error',
        success: 'Success',
        warning: 'Warning',
        info: 'Info',
        yes: 'Yes',
        no: 'No',
        ok: 'OK',
        back: 'Back',
        next: 'Next',
        previous: 'Previous',
        submit: 'Submit',
        search: 'Search',
        filter: 'Filter',
        sort: 'Sort',
        view: 'View',
        download: 'Download',
        upload: 'Upload',
        share: 'Share',
        cad: 'CAD',
        usd: 'USD',
        currency: 'Currency',
        showMore: 'Show More',
        showLess: 'Show Less',
        downloadPDF: 'Download PDF',
      },

      // Auction Terms
      auction: {
        termsAndConditions: 'Terms & Conditions',
        englishTerms: 'English Terms',
        frenchTerms: 'French Terms',
        noTermsProvided: 'No terms provided by seller',
        agreeToTerms: "I have read and agree to the auction's Terms & Conditions",
        mustAgreeBeforeBid: 'You must agree to the terms before placing a bid',
        mustAgreeToTermsFirst: 'Please agree to terms & conditions first',
        agreeToTermsToPlaceBid: 'Please scroll up and agree to the Terms & Conditions to place a bid',
      },

      // Bidding
      bid: {
        placeBid: 'Place Bid',
        mustAgreeToTerms: 'You must agree to the auction terms before placing a bid',
      },

      // Payment
      payment: {
        addCard: 'Add Payment Method',
        deleteCard: 'Delete Card',
        confirmDelete: 'Are you sure you want to delete this payment method?',
        cardDeleted: 'Payment method deleted',
        cardDeleteFailed: 'Failed to delete payment method',
        cardAdded: 'Payment method added successfully',
        cardFailed: 'Failed to add payment method',
        cardNumber: 'Card Number',
        expiryDate: 'Expiry Date',
        cvc: 'CVC',
        saveCard: 'Save Card',
      },

      // Messages
      messages: {
        noMessages: 'No messages yet',
        sendMessage: 'Send Message',
        typeMessage: 'Type your message...',
        conversations: 'Conversations',
        newMessage: 'New Message',
      },

      // Watchlist
      watchlist: {
        title: 'My Watchlist',
        empty: 'Your watchlist is empty',
        addItems: 'Start adding items you\'re interested in',
        removeItem: 'Remove from Watchlist',
        viewListing: 'View Listing',
        emptyTitle: "You're not watching any items yet",
        emptyDescription: "Start exploring auctions or listings to track your favorites.",
        browseMarketplace: 'Browse Marketplace',
        viewAuctions: 'View Auctions',
        goToAuction: 'Go to Auction',
        viewLot: 'View Lot',
      },

      // Errors & Validation
      errors: {
        required: 'This field is required',
        invalidEmail: 'Invalid email address',
        invalidPhone: 'Invalid phone number',
        passwordTooShort: 'Password must be at least 8 characters',
        passwordMatch: 'Passwords must match',
        networkError: 'Network error. Please try again.',
        unauthorized: 'You are not authorized to perform this action',
        notFound: 'Resource not found',
        serverError: 'Server error. Please try again later.',
      },

      // Notifications
      notifications: {
        newBid: 'New bid on your item',
        outbid: 'You have been outbid',
        auctionEnding: 'Auction ending soon',
        auctionWon: 'Congratulations! You won the auction',
        auctionLost: 'Auction ended - you were outbid',
        paymentReceived: 'Payment received',
        itemShipped: 'Item shipped',
        messageReceived: 'New message received',
        markAllRead: 'Mark all as read',
        noNotifications: 'No notifications',
      },

      // Footer
      footer: {
        aboutUs: 'About Us',
        contactUs: 'Contact Us',
        termsOfService: 'Terms of Service',
        privacyPolicy: 'Privacy Policy',
        faq: 'FAQ',
        support: 'Support',
        followUs: 'Follow Us',
        allRightsReserved: 'All rights reserved',
        howItWorks: 'How It Works',
        cookiePreferences: 'Cookie Preferences',
      },

      // How It Works
      howItWorks: {
        title: 'How BidVex Works',
        badge: 'How It Works',
        mainTitle: 'Start Bidding in',
        simpleSteps: '5 Simple Steps',
        subtitle: 'Whether you\'re buying or selling, BidVex makes online auctions simple, secure, and exciting',
        forBuyers: 'For Buyers',
        forSellers: 'For Sellers',
        step1Title: '1. Browse & Discover',
        step1Desc: 'Explore our marketplace to find unique items. Use filters to narrow down by category, price, location, and more.',
        step2Title: '2. Register & Verify',
        step2Desc: 'Create your free account and verify your email. Complete your profile to build trust with the community.',
        step3Title: '3. Place Your Bid',
        step3Desc: 'Found something you like? Place a bid and watch the auction in real-time. You\'ll get instant notifications if you\'re outbid.',
        step4Title: '4. Win & Celebrate',
        step4Desc: 'If you win, you\'ll receive an email confirmation. Complete your secure payment through our Stripe integration.',
        step5Title: '5. Secure Payment & Delivery',
        step5Desc: 'Complete payment securely and coordinate delivery with the seller. All transactions are protected by our buyer guarantee.',
        faqTitle: 'Frequently Asked Questions',
        faq1Q: 'How do I start bidding?',
        faq1A: 'First, create a free account and verify your email. Then browse our marketplace, find an item you like, and click \'Place Bid\' to enter your bid amount. You\'ll be notified if someone outbids you.',
        faq2Q: 'Is my payment information secure?',
        faq2A: 'Absolutely! All payments are processed through Stripe, a leading payment processor trusted by millions. We never store your credit card information on our servers.',
        faq3Q: 'What happens if I win an auction?',
        faq3A: 'Congratulations! You\'ll receive an email confirmation and be directed to complete your payment. Once payment is confirmed, you can coordinate delivery or pickup with the seller through our messaging system.',
        faq4Q: 'Can I cancel my bid?',
        faq4A: 'Bids are binding commitments. Once placed, bids cannot be retracted. Please bid responsibly and make sure you\'re willing to complete the purchase if you win.',
        faq5Q: 'How do seller fees work?',
        faq5A: 'Sellers pay a small commission on successful sales. Personal accounts pay 5%, while business accounts pay 4.5%. This helps us maintain a secure, feature-rich platform for everyone.',
        getStarted: 'Get Started Today',
        joinCommunity: 'Join thousands of happy buyers and sellers',
        signUpNow: 'Sign Up Now',
        browsePlatform: 'Browse Auctions',
      },
    },
  },
  fr: {
    translation: {
      // Navigation
      nav: {
        home: 'Accueil',
        marketplace: 'Marché',
        lotsAuction: 'Enchères par Lots',
        sell: 'Vendre',
        myAccount: 'Mon Compte',
        login: 'Connexion',
        register: "S'inscrire",
        logout: 'Déconnexion',
        sellerDashboard: 'Tableau de bord vendeur',
        buyerDashboard: 'Tableau de bord acheteur',
        adminPanel: 'Panneau Admin',
        affiliateDashboard: 'Tableau de bord affilié',
        watchlist: 'Liste de surveillance',
        messages: 'Messages',
        howItWorks: 'Comment ça marche',
      },

      // Hero Section
      hero: {
        title: 'Découvrez des Trésors Uniques',
        subtitle: 'Votre Marché aux Enchères Premium',
        description: 'Enchérissez sur des articles exclusifs ou vendez vos trésors à un public mondial',
        cta: 'Explorer les Enchères',
        browseAuctions: 'Parcourir les Enchères',
        sellNow: 'Commencer à Vendre',
        howBiddingWorks: 'Comment Fonctionnent les Enchères',
        nextAuction: 'Prochaine enchère se termine dans',
        viewAuction: "Voir l'Enchère",
        startBidding: "Commencer à Enchérir Aujourd'hui",
        discoverDeals: 'Découvrez des trouvailles rares et des offres exclusives sur notre marché de confiance',
      },

      // Homepage Sections
      homepage: {
        // Hero
        liveAuctionsNow: 'Enchères en Direct',
        discover: 'Découvrir.',
        bid: 'Enchérir.',
        win: 'Gagner.',
        heroDescription: "Vivez le frisson des enchères en direct. Rejoignez des milliers d'enchérisseurs pour des articles uniques à des prix imbattables. Votre prochain trésor vous attend.",
        howItWorks: 'Comment ça marche',
        
        // Trust Indicators
        securePayments: 'Paiements Sécurisés',
        verifiedSellers: 'Vendeurs Vérifiés',
        buyerProtection: 'Protection Acheteur',
        
        // Stats
        activeBidders: 'Enchérisseurs Actifs',
        liveAuctions: 'Enchères en Direct',
        itemsWon: 'Articles Gagnés',
        satisfaction: 'Satisfaction',
        
        // Sections
        endingSoon: 'Se Termine Bientôt',
        endingSoonDesc: 'Ne manquez pas ! Ces enchères se terminent bientôt',
        hotItems: 'Articles Populaires',
        hotItemsDesc: 'Enchères tendances avec le plus d\'activité',
        featuredAuctions: 'Enchères en Vedette',
        curatedAuctions: 'Enchères Sélectionnées',
        handPicked: 'Articles sélectionnés de nos meilleurs vendeurs',
        justListed: '🆕 Nouveautés',
        freshAuctions: "Nouvelles enchères ajoutées aujourd'hui",
        whyChooseBidvex: 'Pourquoi Choisir BidVex?',
        trustedPlatform: 'La plateforme de confiance pour les enchérisseurs avisés',
        topSellers: 'Nos Meilleurs Vendeurs',
        topPerformers: 'Meilleurs Performeurs',
        
        // Actions
        viewAll: 'Voir Tout',
        bidNow: 'Enchérir',
        learnMore: 'En Savoir Plus',
        gettingStarted: 'Pour Commencer',
        viewAllHotItems: 'Voir Tous les Articles Populaires',
        
        // Status
        live: 'EN DIRECT',
        activeBidding: 'Enchères actives',
        currentBid: 'Enchère Actuelle',
        ended: 'Terminé',
        views: 'vues',
        bids: 'enchères',
        totalSales: 'Ventes Totales',
        itemsSold: 'Articles Vendus',
        new: 'NOUVEAU',
        featured: 'En vedette',
        
        // Features
        liveBidding: 'Enchères en Direct',
        liveBiddingDesc: 'Enchères en temps réel avec mises à jour instantanées',
        securePaymentsDesc: 'Chiffrement bancaire via Stripe',
        buyerProtectionDesc: 'Garantie de remboursement complet en cas de litige',
        globalCommunity: 'Communauté Mondiale',
        globalCommunityDesc: 'Acheteurs et vendeurs vérifiés dans le monde entier',
        
        // How It Works
        howItWorksTitle: 'Comment Ça Marche',
        startWinning: 'Commencez à gagner des offres incroyables en trois étapes simples',
        browse: 'Parcourir',
        browseDesc: 'Trouvez des articles uniques de vendeurs de confiance',
        bidStep: 'Enchérir',
        bidStepDesc: 'Placez des enchères compétitives en temps réel',
        winStep: 'Gagner',
        winStepDesc: 'Sécurisez vos articles avec un paiement sûr',
        
        // Fallback for dynamic content
        translatedFromOriginal: 'Traduit de l\'original',
      },

      // Authentication
      auth: {
        welcomeBack: 'Bienvenue',
        createAccount: 'Créer un Compte',
        signInPrompt: 'Connectez-vous à votre compte',
        createAccountPrompt: 'Créez un compte pour commencer à enchérir',
        welcomeMessage: 'Bienvenue!',
        accountCreatedMessage: 'Compte créé avec succès!',
        authFailedMessage: 'Échec de l\'authentification',
        email: 'Email',
        emailAddress: 'Adresse e-mail',
        password: 'Mot de passe',
        name: 'Nom complet',
        phone: 'Téléphone',
        accountType: 'Type de compte',
        personal: 'Personnel',
        business: 'Entreprise',
        address: 'Adresse',
        companyName: 'Nom de l\'entreprise',
        taxNumber: 'Numéro fiscal',
        loginBtn: 'Se connecter',
        registerBtn: 'Créer un compte',
        googleLogin: 'Continuer avec Google',
        noAccount: 'Pas de compte?',
        hasAccount: 'Déjà un compte?',
        forgotPassword: 'Mot de passe oublié?',
        rememberMe: 'Se souvenir de moi',
      },

      // Marketplace
      marketplace: {
        title: 'Enchères Actives',
        search: 'Rechercher des annonces...',
        searchPlaceholder: 'Rechercher des articles, catégories ou vendeurs...',
        category: 'Catégorie',
        location: 'Emplacement',
        condition: 'État',
        priceRange: 'Fourchette de prix',
        sortBy: 'Trier par',
        newest: "Plus récent d'abord",
        ending: 'Se terminant bientôt',
        priceLow: 'Prix: Bas à Élevé',
        priceHigh: 'Prix: Élevé à Bas',
        currentBid: 'Enchère actuelle',
        startingBid: 'Enchère de départ',
        buyNow: 'Acheter maintenant',
        bids: 'enchères',
        endsIn: 'Se termine dans',
        ended: 'Enchère terminée',
        noResults: 'Aucune enchère trouvée',
        filter: 'Filtrer',
        clearFilters: 'Effacer les filtres',
      },

      // Listing Details
      listing: {
        details: 'Détails',
        placeBid: 'Placer une enchère',
        buyNow: 'Acheter maintenant',
        yourBid: 'Votre enchère',
        submitBid: "Soumettre l'enchère",
        bidHistory: 'Historique des enchères',
        seller: 'Vendeur',
        location: 'Emplacement',
        condition: 'État',
        views: 'vues',
        timeLeft: 'Temps restant',
        description: 'Description',
        shippingInfo: "Informations d'expédition",
        paymentMethods: 'Modes de paiement acceptés',
        askQuestion: 'Poser une question',
        reportListing: "Signaler l'annonce",
        shareLink: 'Partager',
        addToWatchlist: 'Ajouter à la liste de surveillance',
        removeFromWatchlist: 'Retirer de la liste de surveillance',
      },

      // Guide des Erreurs d'Enchères
      bidErrorGuide: {
        title: 'Erreurs Courantes d\'Enchères',
        subtitle: 'Comprendre les problèmes d\'enchères et comment les résoudre',
        errors: {
          bidTooLow: {
            title: 'L\'offre doit être supérieure au prix actuel',
            description: 'Votre montant d\'enchère est inférieur au prix actuel. Essayez d\'enchérir un montant plus élevé que l\'enchère actuelle affichée.',
            solution: 'Augmentez votre montant d\'enchère pour au moins correspondre à l\'enchère minimum requise.',
          },
          minimumIncrement: {
            title: 'L\'offre doit être d\'au moins {{amount}} $',
            description: 'Le pas d\'enchère minimum n\'a pas été respecté. Chaque enchère doit augmenter d\'un montant spécifique.',
            solution: 'Entrez un montant d\'enchère d\'au moins {{amount}} $ pour respecter le pas minimum requis.',
          },
          networkError: {
            title: 'Erreur réseau. Veuillez vérifier votre connexion.',
            description: 'Impossible de se connecter au serveur. Cela peut être dû à des problèmes de connectivité Internet.',
            solution: 'Vérifiez votre connexion Internet et réessayez. Si le problème persiste, actualisez la page.',
          },
          invalidAmount: {
            title: 'Montant d\'offre invalide',
            description: 'Le montant d\'enchère saisi n\'est pas un nombre valide ou contient des caractères invalides.',
            solution: 'Entrez un montant numérique valide sans symboles monétaires ou caractères spéciaux.',
          },
          auctionEnded: {
            title: 'L\'enchère est terminée',
            description: 'Cette enchère n\'accepte plus d\'offres car la période d\'enchères est close.',
            solution: 'Parcourez d\'autres enchères actives ou attendez que des articles similaires soient mis en vente.',
          },
          insufficientFunds: {
            title: 'Fonds insuffisants',
            description: 'Le solde de votre compte ou votre méthode de paiement pourrait ne pas couvrir ce montant d\'enchère.',
            solution: 'Mettez à jour votre méthode de paiement ou réduisez votre montant d\'enchère.',
          },
          unauthorized: {
            title: 'Veuillez vous connecter pour enchérir',
            description: 'Vous devez être connecté pour placer des enchères sur les ventes.',
            solution: 'Connectez-vous à votre compte ou créez un nouveau compte pour commencer à enchérir.',
          },
        },
        helpText: 'Vous avez toujours des problèmes? Contactez notre équipe d\'assistance pour obtenir de l\'aide.',
        closeButton: 'Compris',
      },

      // Dashboard
      dashboard: {
        seller: {
          title: 'Tableau de bord vendeur',
          activeListings: 'Annonces actives',
          soldItems: 'Articles vendus',
          draftListings: 'Brouillons',
          totalSales: 'Ventes totales',
          createListing: 'Créer une annonce',
          createLot: 'Créer un lot',
          commission: 'Commission: 5%',
          viewAll: 'Voir tout',
          revenue: 'Revenus',
          activeAuctions: 'Enchères actives',
          businessAccount: 'Compte entreprise',
          personalAccount: 'Compte personnel',
          commissionRate: 'Commission',
          deleteListing: 'Êtes-vous sûr de vouloir supprimer cette annonce?',
          listingDeleted: 'Annonce supprimée avec succès',
          deleteFailed: 'Échec de la suppression',
          loadFailed: 'Échec du chargement du tableau de bord',
        },
        buyer: {
          title: 'Tableau de bord acheteur',
          activeBids: 'Enchères actives',
          wonItems: 'Articles remportés',
          watchlist: 'Favoris',
          totalSpent: 'Dépenses totales',
          bidActivity: 'Activité d\'enchères',
          savedSearches: 'Recherches sauvegardées',
        },
      },

      // Profile Settings
      profile: {
        title: 'Paramètres du Profil',
        accountSettings: 'Paramètres du Compte',
        personalInfo: 'Informations Personnelles',
        personalInformation: 'Informations Personnelles',
        updateDetails: 'Mettre à jour vos détails de profil',
        preferences: 'Préférences',
        language: 'Langue',
        currency: 'Devise Préférée',
        selectLanguage: 'Sélectionner la Langue',
        selectCurrency: 'Sélectionner la Devise',
        english: 'English',
        french: 'Français',
        saveChanges: 'Enregistrer les Modifications',
        changesSaved: 'Modifications enregistrées avec succès',
        fullName: 'Nom Complet',
        phoneNumber: 'Numéro de Téléphone',
        address: 'Adresse',
        companyName: "Nom de l'Entreprise",
        taxNumber: 'Numéro Fiscal',
        paymentMethods: 'Modes de Paiement',
        notifications: 'Notifications',
        profileTab: 'Profil',
        paymentTab: 'Modes de Paiement',
        notificationsTab: 'Notifications',
      },

      // Currency Enforcement
      currency: {
        locked: 'Verrouillée',
        enforced: 'Devise Appliquée',
        complianceMessage: "La devise est déterminée par votre emplacement pour se conformer aux règles fiscales locales. Si vous voyagez ou avez déménagé, vous pouvez demander une vérification.",
        requestChange: 'Demander un Changement de Devise',
        appeal: 'Faire Appel',
        appealSubmitted: 'Appel soumis avec succès',
        appealReason: 'Raison de la Demande',
        requestedCurrency: 'Devise Demandée',
        submitAppeal: "Soumettre l'Appel",
        appealStatus: "Statut de l'Appel",
        pending: 'En Attente',
        approved: 'Approuvé',
        rejected: 'Rejeté',
        currentCurrency: 'Devise Actuelle',
        enforcedCurrency: 'Devise Appliquée',
        confidenceScore: 'Score de Confiance',
      },

      // Admin Panel
      admin: {
        dashboard: 'Tableau de Bord Admin',
        title: 'Panneau Admin',
        overview: 'Aperçu',
        users: 'Gestion des Utilisateurs',
        auctions: 'Contrôle des Enchères',
        lots: 'Gestion des Lots',
        analytics: 'Analytique',
        settings: 'Paramètres',
        trustSafety: 'Confiance et Sécurité',
        reports: 'Rapports',
        logs: 'Journaux Admin',
        announcements: 'Annonces',
        promotions: 'Promotions',
        categories: 'Catégories',
        currencyAppeals: 'Appels de Devise',
        affiliates: 'Affiliés',
        messaging: 'Surveillance de la Messagerie',
        moderateLots: 'Modérer les Lots',
        
        // Currency Appeals Manager
        appeals: {
          title: 'Demandes d\'Appel de Devise',
          description: 'Examiner et gérer les appels de préférence de devise des utilisateurs',
          noAppeals: 'Aucun appel de devise trouvé',
          userName: "Nom d'Utilisateur",
          from: 'De',
          to: 'À',
          submitted: 'Soumis',
          reason: 'Raison',
          status: 'Statut',
          approve: 'Approuver',
          reject: 'Rejeter',
          approveConfirm: 'Êtes-vous sûr de vouloir approuver cet appel?',
          rejectConfirm: 'Êtes-vous sûr de vouloir rejeter cet appel?',
          approved: 'Appel approuvé avec succès',
          rejected: 'Appel rejeté avec succès',
          error: "Échec de la mise à jour de l'appel",
        },

        // User Management
        userManagement: {
          searchUsers: 'Rechercher des utilisateurs...',
          totalUsers: 'Total des Utilisateurs',
          activeUsers: 'Utilisateurs Actifs',
          bannedUsers: 'Utilisateurs Bannis',
          accountType: 'Type de Compte',
          status: 'Statut',
          actions: 'Actions',
          viewProfile: 'Voir le Profil',
          banUser: "Bannir l'Utilisateur",
          unbanUser: "Débannir l'Utilisateur",
          deleteUser: "Supprimer l'Utilisateur",
        },
      },

      // Lots Auction
      lots: {
        auctionTitle: 'Enchères par Lots',
        multiItemAuctions: 'Enchères Multi-Articles',
        comingSoon: 'Prochainement',
        upcoming: 'À Venir',
        activeAuctions: 'Enchères Actives',
        category: 'Catégorie',
        location: 'Emplacement',
        items: 'Articles',
        lotCount: 'Nombre de Lots',
        lots: 'lots',
        timeRemaining: 'Temps Restant',
        endsIn: 'Se termine dans',
        startDate: 'Commence',
        viewDetails: 'Voir les Détails',
        viewAuction: "Voir l'Enchère",
        ended: 'Terminé',
        general: 'Général',
      },

      // Common UI Elements
      common: {
        loading: 'Chargement...',
        save: 'Enregistrer',
        cancel: 'Annuler',
        delete: 'Supprimer',
        edit: 'Modifier',
        close: 'Fermer',
        confirm: 'Confirmer',
        error: 'Erreur',
        success: 'Succès',
        warning: 'Avertissement',
        info: 'Info',
        yes: 'Oui',
        no: 'Non',
        ok: 'OK',
        back: 'Retour',
        next: 'Suivant',
        previous: 'Précédent',
        submit: 'Soumettre',
        search: 'Rechercher',
        filter: 'Filtrer',
        sort: 'Trier',
        view: 'Voir',
        download: 'Télécharger',
        upload: 'Téléverser',
        share: 'Partager',
        cad: 'CAD',
        usd: 'USD',
        currency: 'Devise',
        showMore: 'Voir Plus',
        showLess: 'Voir Moins',
        downloadPDF: 'Télécharger PDF',
      },

      // Termes de l'Enchère
      auction: {
        termsAndConditions: 'Termes et Conditions',
        englishTerms: 'Termes en Anglais',
        frenchTerms: 'Termes en Français',
        noTermsProvided: 'Aucune condition fournie par le vendeur',
        agreeToTerms: "J'ai lu et j'accepte les Conditions de vente aux enchères",
        mustAgreeBeforeBid: "Vous devez accepter les conditions avant de placer une enchère",
        mustAgreeToTermsFirst: 'Veuillez accepter les conditions générales d\'abord',
        agreeToTermsToPlaceBid: 'Veuillez faire défiler vers le haut et accepter les Termes et Conditions pour placer une enchère',
      },

      // Enchères
      bid: {
        placeBid: 'Placer une enchère',
        mustAgreeToTerms: "Vous devez accepter les conditions de l'enchère avant de placer une enchère",
      },

      // Payment
      payment: {
        addCard: 'Ajouter un Mode de Paiement',
        deleteCard: 'Supprimer la Carte',
        confirmDelete: 'Êtes-vous sûr de vouloir supprimer ce mode de paiement?',
        cardDeleted: 'Mode de paiement supprimé',
        cardDeleteFailed: 'Échec de la suppression du mode de paiement',
        cardAdded: 'Mode de paiement ajouté avec succès',
        cardFailed: "Échec de l'ajout du mode de paiement",
        cardNumber: 'Numéro de Carte',
        expiryDate: "Date d'Expiration",
        cvc: 'CVC',
        saveCard: 'Enregistrer la Carte',
      },

      // Messages
      messages: {
        noMessages: 'Aucun message pour le moment',
        sendMessage: 'Envoyer un Message',
        typeMessage: 'Tapez votre message...',
        conversations: 'Conversations',
        newMessage: 'Nouveau Message',
      },

      // Watchlist
      watchlist: {
        title: 'Ma Liste de Surveillance',
        empty: 'Votre liste de surveillance est vide',
        addItems: 'Commencez à ajouter des articles qui vous intéressent',
        removeItem: 'Retirer de la Liste de Surveillance',
        viewListing: "Voir l'Annonce",
        emptyTitle: "Vous ne suivez aucun article pour le moment",
        emptyDescription: "Explorez les enchères ou les annonces pour suivre vos coups de cœur.",
        browseMarketplace: 'Parcourir le Marché',
        viewAuctions: 'Voir les Enchères',
        goToAuction: "Aller à l'Enchère",
        viewLot: 'Voir le Lot',
      },

      // Errors & Validation
      errors: {
        required: 'Ce champ est requis',
        invalidEmail: 'Adresse e-mail invalide',
        invalidPhone: 'Numéro de téléphone invalide',
        passwordTooShort: 'Le mot de passe doit contenir au moins 8 caractères',
        passwordMatch: 'Les mots de passe doivent correspondre',
        networkError: 'Erreur réseau. Veuillez réessayer.',
        unauthorized: "Vous n'êtes pas autorisé à effectuer cette action",
        notFound: 'Ressource non trouvée',
        serverError: 'Erreur serveur. Veuillez réessayer plus tard.',
      },

      // Notifications
      notifications: {
        newBid: 'Nouvelle enchère sur votre article',
        outbid: 'Vous avez été surenchéri',
        auctionEnding: "L'enchère se termine bientôt",
        auctionWon: "Félicitations! Vous avez remporté l'enchère",
        auctionLost: "Enchère terminée - vous avez été surenchéri",
        paymentReceived: 'Paiement reçu',
        itemShipped: 'Article expédié',
        messageReceived: 'Nouveau message reçu',
        markAllRead: 'Marquer tout comme lu',
        noNotifications: 'Aucune notification',
      },

      // Footer
      footer: {
        aboutUs: 'À propos',
        contactUs: 'Contact',
        termsOfService: 'Conditions d\'utilisation',
        privacyPolicy: 'Confidentialité',
        faq: 'FAQ',
        support: 'Support',
        followUs: 'Suivez-nous',
        allRightsReserved: 'Tous droits réservés',
        howItWorks: 'Comment ça marche',
        cookiePreferences: 'Préférences cookies',
      },

      // How It Works
      howItWorks: {
        title: 'Comment Fonctionne BidVex',
        badge: 'Comment ça marche',
        mainTitle: 'Commencez à enchérir en',
        simpleSteps: '5 étapes simples',
        subtitle: 'Que vous achetiez ou vendiez, BidVex rend les enchères en ligne simples, sécurisées et passionnantes',
        forBuyers: 'Pour les acheteurs',
        forSellers: 'Pour les vendeurs',
        step1Title: '1. Parcourir et Découvrir',
        step1Desc: 'Explorez notre marché pour trouver des articles uniques. Utilisez les filtres pour affiner par catégorie, prix, emplacement, et plus encore.',
        step2Title: '2. Inscription et Vérification',
        step2Desc: 'Créez votre compte gratuit et vérifiez votre email. Complétez votre profil pour gagner la confiance de la communauté.',
        step3Title: '3. Placer Votre Enchère',
        step3Desc: 'Vous avez trouvé quelque chose qui vous plaît? Placez une enchère et suivez l\'auction en temps réel. Vous recevrez des notifications instantanées si vous êtes surenchéri.',
        step4Title: '4. Gagner et Célébrer',
        step4Desc: 'Si vous gagnez, vous recevrez un email de confirmation. Effectuez votre paiement sécurisé via notre intégration Stripe.',
        step5Title: '5. Paiement Sécurisé et Livraison',
        step5Desc: 'Effectuez le paiement en toute sécurité et coordonnez la livraison avec le vendeur. Toutes les transactions sont protégées par notre garantie acheteur.',
        faqTitle: 'Questions Fréquentes',
        faq1Q: 'Comment commencer à enchérir?',
        faq1A: 'D\'abord, créez un compte gratuit et vérifiez votre email. Ensuite, parcourez notre marché, trouvez un article qui vous plaît, et cliquez sur \'Placer une Enchère\' pour entrer votre montant. Vous serez notifié si quelqu\'un vous surenchérit.',
        faq2Q: 'Mes informations de paiement sont-elles sécurisées?',
        faq2A: 'Absolument! Tous les paiements sont traités via Stripe, un processeur de paiement de premier plan approuvé par des millions. Nous ne stockons jamais vos informations de carte de crédit sur nos serveurs.',
        faq3Q: 'Que se passe-t-il si je remporte une enchère?',
        faq3A: 'Félicitations! Vous recevrez un email de confirmation et serez dirigé pour effectuer votre paiement. Une fois le paiement confirmé, vous pourrez coordonner la livraison ou le retrait avec le vendeur via notre système de messagerie.',
        faq4Q: 'Puis-je annuler mon enchère?',
        faq4A: 'Les enchères sont des engagements contraignants. Une fois placées, les enchères ne peuvent pas être rétractées. Veuillez enchérir de manière responsable et assurez-vous d\'être prêt à finaliser l\'achat si vous gagnez.',
        faq5Q: 'Comment fonctionnent les frais vendeur?',
        faq5A: 'Les vendeurs paient une petite commission sur les ventes réussies. Les comptes personnels paient 5%, tandis que les comptes entreprise paient 4,5%. Cela nous aide à maintenir une plateforme sécurisée et riche en fonctionnalités pour tous.',
        getStarted: 'Commencez Aujourd\'hui',
        joinCommunity: 'Rejoignez des milliers d\'acheteurs et vendeurs satisfaits',
        signUpNow: 'S\'inscrire Maintenant',
        browsePlatform: 'Parcourir les Enchères',
      },
    },
  },
};

// Determine initial language with priority: localStorage > browser > default
const initialLanguage = getPersistedLanguage() || 
  (typeof navigator !== 'undefined' && navigator.language?.startsWith('fr') ? 'fr' : 'en');

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    lng: initialLanguage,
    fallbackLng: 'en',
    supportedLngs: ['en', 'fr'],
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: 'bidvex_language',
      caches: ['localStorage'],
    },
  });

// Persist language changes
i18n.on('languageChanged', (lng) => {
  persistLanguage(lng);
  // Update HTML lang attribute for accessibility
  document.documentElement.lang = lng;
});

export default i18n;
