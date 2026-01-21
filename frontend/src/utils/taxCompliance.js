// Canadian Tax Compliance - Legal Declarations
// CRA Part XX (Platform Economy Reporting) & Revenu Québec Requirements

export const TAX_DECLARATIONS = {
  en: {
    title: "Tax Information & Seller Declaration",
    subtitle: "Required for Canadian Revenue Agency (CRA) compliance",
    
    individual: {
      header: "Individual / Casual Seller Declaration",
      description: "I confirm that I am selling items as an individual (not a registered business). I understand that:",
      points: [
        "BidVex may be required to report my sales information to the Canada Revenue Agency (CRA) and Revenu Québec as per Part XX of the Income Tax Act.",
        "If my annual sales exceed $30,000 CAD, I am required to register for GST/HST and QST.",
        "BidVex may collect and remit GST/QST (14.975%) on my behalf for sales to Quebec buyers.",
        "I must provide accurate tax information including my Social Insurance Number (SIN) and date of birth for CRA reporting.",
        "I am responsible for declaring this income on my personal tax return."
      ],
      agreement: "I hereby certify that the information provided is true and accurate. I understand my tax obligations as an individual seller in Canada."
    },
    
    business: {
      header: "Registered Business / Corporation Declaration",
      description: "I confirm that I am a registered business entity. I understand that:",
      points: [
        "I must provide valid GST/HST and QST registration numbers that will be verified with the CRA registry.",
        "I am responsible for collecting and remitting all applicable taxes (GST/QST) to the government.",
        "My business information (Legal Name, Business Number, NEQ) will be reported to CRA and Revenu Québec annually.",
        "I must maintain proper business registration and tax compliance throughout my use of the platform.",
        "BidVex will issue annual transaction reports (T4A/Relevé 1) if my sales exceed reporting thresholds."
      ],
      agreement: "I hereby certify that I am an authorized representative of this business and that all tax registration information provided is valid and current."
    },
    
    threshold_warning: "⚠️ Important: Individual sellers who exceed $30,000 in annual sales must register for GST/QST and convert to a Business account.",
    privacy_notice: "Your tax information is encrypted and stored securely. It is only shared with Canadian tax authorities as required by law.",
    cra_reference: "This collection is required under Part XX of the Income Tax Act (Platform Economy Reporting Rules, effective January 1, 2024)."
  },
  
  fr: {
    title: "Informations Fiscales et Déclaration du Vendeur",
    subtitle: "Requis pour la conformité avec l'Agence du revenu du Canada (ARC)",
    
    individual: {
      header: "Déclaration de Vendeur Individuel / Occasionnel",
      description: "Je confirme que je vends des articles en tant qu'individu (pas une entreprise enregistrée). Je comprends que :",
      points: [
        "BidVex peut être tenu de déclarer mes informations de vente à l'Agence du revenu du Canada (ARC) et à Revenu Québec conformément à la partie XX de la Loi de l'impôt sur le revenu.",
        "Si mes ventes annuelles dépassent 30 000 $ CAD, je dois m'inscrire à la TPS/TVH et à la TVQ.",
        "BidVex peut percevoir et remettre la TPS/TVQ (14,975 %) en mon nom pour les ventes aux acheteurs québécois.",
        "Je dois fournir des informations fiscales exactes, y compris mon numéro d'assurance sociale (NAS) et ma date de naissance pour les rapports de l'ARC.",
        "Je suis responsable de déclarer ce revenu dans ma déclaration de revenus personnelle."
      ],
      agreement: "Je certifie par la présente que les informations fournies sont vraies et exactes. Je comprends mes obligations fiscales en tant que vendeur individuel au Canada."
    },
    
    business: {
      header: "Déclaration d'Entreprise Enregistrée / Société",
      description: "Je confirme que je suis une entité commerciale enregistrée. Je comprends que :",
      points: [
        "Je dois fournir des numéros d'inscription TPS/TVH et TVQ valides qui seront vérifiés auprès du registre de l'ARC.",
        "Je suis responsable de percevoir et de remettre toutes les taxes applicables (TPS/TVQ) au gouvernement.",
        "Les informations de mon entreprise (nom légal, numéro d'entreprise, NEQ) seront déclarées à l'ARC et à Revenu Québec annuellement.",
        "Je dois maintenir une inscription commerciale et une conformité fiscale appropriées tout au long de mon utilisation de la plateforme.",
        "BidVex émettra des rapports de transactions annuels (T4A/Relevé 1) si mes ventes dépassent les seuils de déclaration."
      ],
      agreement: "Je certifie par la présente que je suis un représentant autorisé de cette entreprise et que toutes les informations d'inscription fiscale fournies sont valides et à jour."
    },
    
    threshold_warning: "⚠️ Important : Les vendeurs individuels qui dépassent 30 000 $ de ventes annuelles doivent s'inscrire à la TPS/TVQ et convertir leur compte en compte Entreprise.",
    privacy_notice: "Vos informations fiscales sont cryptées et stockées en toute sécurité. Elles ne sont partagées qu'avec les autorités fiscales canadiennes comme l'exige la loi.",
    cra_reference: "Cette collecte est requise en vertu de la partie XX de la Loi de l'impôt sur le revenu (Règles de déclaration de l'économie des plateformes, en vigueur le 1er janvier 2024)."
  }
};

// Field requirements by seller type
export const TAX_FIELD_REQUIREMENTS = {
  individual: {
    required: ['tax_id', 'date_of_birth', 'address'],
    optional: ['gst_number', 'qst_number'],
    labels: {
      en: {
        tax_id: 'Social Insurance Number (SIN)',
        date_of_birth: 'Date of Birth',
        address: 'Principal Residential Address'
      },
      fr: {
        tax_id: 'Numéro d\'assurance sociale (NAS)',
        date_of_birth: 'Date de naissance',
        address: 'Adresse résidentielle principale'
      }
    }
  },
  business: {
    required: ['tax_id', 'neq_number', 'gst_number', 'qst_number', 'legal_business_name', 'registered_office_address'],
    optional: [],
    labels: {
      en: {
        tax_id: 'Business Number (BN)',
        neq_number: 'Quebec Enterprise Number (NEQ)',
        gst_number: 'GST/HST Registration Number',
        qst_number: 'QST Registration Number',
        legal_business_name: 'Registered Corporation Name',
        registered_office_address: 'Registered Business Office Address'
      },
      fr: {
        tax_id: 'Numéro d\'entreprise (NE)',
        neq_number: 'Numéro d\'entreprise du Québec (NEQ)',
        gst_number: 'Numéro d\'inscription TPS/TVH',
        qst_number: 'Numéro d\'inscription TVQ',
        legal_business_name: 'Nom de la société enregistrée',
        registered_office_address: 'Adresse du bureau d\'affaires enregistré'
      }
    }
  }
};

// Tax calculation logic
export const calculateTax = (amount, sellerType, isRegistered) => {
  const GST_RATE = 0.05;      // 5% federal
  const QST_RATE = 0.09975;   // 9.975% Quebec
  const COMBINED_RATE = 0.14975; // 14.975% total
  
  if (sellerType === 'individual' && !isRegistered) {
    // Platform is "deemed supplier" - must collect tax
    return {
      platform_collects: true,
      gst: amount * GST_RATE,
      qst: amount * QST_RATE,
      total_tax: amount * COMBINED_RATE,
      note: "Platform collects GST/QST on behalf of individual seller"
    };
  } else if (sellerType === 'business' && isRegistered) {
    // Business handles own taxes
    return {
      platform_collects: false,
      gst: 0,
      qst: 0,
      total_tax: 0,
      note: "Registered business seller handles own tax collection and remittance"
    };
  }
  
  return {
    platform_collects: false,
    gst: 0,
    qst: 0,
    total_tax: 0,
    note: "Tax calculation pending verification"
  };
};

// Threshold monitoring
export const ANNUAL_SALES_THRESHOLD = 30000; // $30,000 CAD threshold for mandatory GST/QST registration
export const EXCLUDED_SELLER_THRESHOLDS = {
  transactions: 30,
  revenue: 2800 // Approximate threshold for CRA reporting exclusion
};
