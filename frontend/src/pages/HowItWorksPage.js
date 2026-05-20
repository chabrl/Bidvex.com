import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import {
  Gavel, ShoppingBag, UserPlus, Handshake, Car, Lightbulb,
  ChevronDown, ChevronUp, ArrowRight, Shield, Zap, DollarSign,
  Search, CreditCard, Truck, Bell, TrendingUp, Users, CheckCircle2,
  HelpCircle, Star, Lock, Eye
} from 'lucide-react';

const HowItWorks = () => {
  const { i18n } = useTranslation();
  const fr = i18n.language?.startsWith('fr');
  const [openFaq, setOpenFaq] = useState(null);

  const sections = [
    {
      id: 'sell',
      icon: <ShoppingBag className="h-7 w-7" />,
      color: 'from-blue-500 to-cyan-500',
      bg: 'bg-blue-50 dark:bg-blue-950',
      border: 'border-blue-200 dark:border-blue-800',
      title: fr ? 'Comment vendre' : 'How to Sell',
      subtitle: fr ? 'Mettez vos articles en vente en quelques minutes' : 'List your items for sale in minutes',
      steps: [
        { icon: <UserPlus className="h-5 w-5" />, en: 'Create your seller account and verify your identity.', fr: 'Créez votre compte vendeur et vérifiez votre identité.' },
        { icon: <ShoppingBag className="h-5 w-5" />, en: 'List your item with photos, description, and starting price.', fr: 'Publiez votre article avec photos, description et prix de départ.' },
        { icon: <Gavel className="h-5 w-5" />, en: 'Set your auction duration, reserve price, and payment preferences.', fr: 'Définissez la durée, le prix de réserve et vos préférences de paiement.' },
        { icon: <DollarSign className="h-5 w-5" />, en: 'Get paid automatically via Stripe when your item sells.', fr: 'Recevez votre paiement automatiquement via Stripe après la vente.' },
      ],
      cta: { label: fr ? 'Commencer à vendre' : 'Start Selling', href: '/create-listing' },
    },
    {
      id: 'bid',
      icon: <Gavel className="h-7 w-7" />,
      color: 'from-green-500 to-emerald-500',
      bg: 'bg-green-50 dark:bg-green-950',
      border: 'border-green-200 dark:border-green-800',
      title: fr ? 'Comment enchérir' : 'How to Bid',
      subtitle: fr ? 'Trouvez des aubaines et enchérissez en toute confiance' : 'Find great deals and bid with confidence',
      steps: [
        { icon: <Search className="h-5 w-5" />, en: 'Browse the marketplace or search by category, location, or keyword.', fr: 'Parcourez le marché ou recherchez par catégorie, lieu ou mot-clé.' },
        { icon: <Eye className="h-5 w-5" />, en: 'View item details, photos, and seller ratings before bidding.', fr: 'Consultez les détails, photos et évaluations du vendeur avant d\'enchérir.' },
        { icon: <Gavel className="h-5 w-5" />, en: 'Place your bid or set a maximum auto-bid. Your card is verified first.', fr: 'Placez votre enchère ou définissez une enchère automatique maximale. Votre carte est vérifiée d\'abord.' },
        { icon: <Bell className="h-5 w-5" />, en: 'Get notified if you\'re outbid. Win and pay securely through Stripe.', fr: 'Soyez notifié si vous êtes surenchéri. Gagnez et payez en toute sécurité via Stripe.' },
      ],
      cta: { label: fr ? 'Parcourir les enchères' : 'Browse Auctions', href: '/marketplace' },
    },
    {
      id: 'account',
      icon: <UserPlus className="h-7 w-7" />,
      color: 'from-purple-500 to-fuchsia-500',
      bg: 'bg-purple-50 dark:bg-purple-950',
      border: 'border-purple-200 dark:border-purple-800',
      title: fr ? 'Créer un compte' : 'Create an Account',
      subtitle: fr ? 'Inscription gratuite en 2 minutes' : 'Free sign-up in 2 minutes',
      steps: [
        { icon: <UserPlus className="h-5 w-5" />, en: 'Enter your name, email, and create a secure password.', fr: 'Entrez votre nom, courriel et créez un mot de passe sécurisé.' },
        { icon: <Shield className="h-5 w-5" />, en: 'Accept terms and acknowledge our AI disclosure (Law 25 compliance).', fr: 'Acceptez les conditions et notre divulgation IA (conformité Loi 25).' },
        { icon: <CreditCard className="h-5 w-5" />, en: 'Add a payment method to start bidding. Sellers connect Stripe for payouts.', fr: 'Ajoutez un mode de paiement pour enchérir. Les vendeurs connectent Stripe pour les versements.' },
      ],
      cta: { label: fr ? 'S\'inscrire gratuitement' : 'Sign Up Free', href: '/auth' },
    },
    {
      id: 'partner',
      icon: <Handshake className="h-7 w-7" />,
      color: 'from-amber-500 to-orange-500',
      bg: 'bg-amber-50 dark:bg-amber-950',
      border: 'border-amber-200 dark:border-amber-800',
      title: fr ? 'Devenir partenaire' : 'Become a Partner',
      subtitle: fr ? 'Avantages exclusifs pour les professionnels' : 'Exclusive benefits for professionals',
      steps: [
        { icon: <Handshake className="h-5 w-5" />, en: 'Apply as a Partner to access premium tools and lower commission rates.', fr: 'Postulez comme partenaire pour accéder aux outils premium et des taux réduits.' },
        { icon: <TrendingUp className="h-5 w-5" />, en: 'Partners pay only 3% flat commission. Set your own buyer premiums.', fr: 'Les partenaires paient seulement 3% de commission. Définissez vos propres primes acheteurs.' },
        { icon: <Star className="h-5 w-5" />, en: 'Get featured placement, priority support, and analytics dashboard.', fr: 'Obtenez un placement vedette, un support prioritaire et un tableau de bord analytique.' },
      ],
      cta: { label: fr ? 'Postuler comme partenaire' : 'Apply as Partner', href: '/become-a-partner' },
    },
    {
      id: 'vehicle-seller',
      icon: <Car className="h-7 w-7" />,
      color: 'from-red-500 to-rose-500',
      bg: 'bg-red-50 dark:bg-red-950',
      border: 'border-red-200 dark:border-red-800',
      title: fr ? 'Vendeur de véhicules' : 'Become a Vehicle Seller',
      subtitle: fr ? 'Concessionnaires licenciés par province' : 'Province-licensed dealers',
      steps: [
        { icon: <Shield className="h-5 w-5" />, en: 'Vehicle listings require a valid provincial dealer licence (e.g. OMVIC in ON, AMVIC in AB, VSA in BC, SAAQ in QC).', fr: 'Les annonces de véhicules nécessitent une licence de concessionnaire provinciale valide (p. ex. OMVIC en ON, AMVIC en AB, VSA en C.-B., SAAQ au QC).' },
        { icon: <Lock className="h-5 w-5" />, en: 'Submit your dealer licence number for verification by BidVex.', fr: 'Soumettez votre numéro de licence pour vérification par BidVex.' },
        { icon: <Car className="h-5 w-5" />, en: 'Once verified, list vehicles with VIN, condition, and inspection reports.', fr: 'Une fois vérifié, publiez des véhicules avec NIV, condition et rapports d\'inspection.' },
        { icon: <DollarSign className="h-5 w-5" />, en: 'Buyers pay a 2.5% platform fee. Seller pays $0 — the hammer price is settled directly.', fr: 'Les acheteurs paient 2,5% de frais de plateforme. Le vendeur ne paie rien — le prix marteau est réglé directement.' },
      ],
      cta: { label: fr ? 'Devenir vendeur véhicules' : 'Apply as Vehicle Seller', href: '/vehicle-auctions/seller/register' },
    },
    {
      id: 'buy-vehicle',
      icon: <Car className="h-7 w-7" />,
      color: 'from-teal-500 to-cyan-500',
      bg: 'bg-teal-50 dark:bg-teal-950',
      border: 'border-teal-200 dark:border-teal-800',
      title: fr ? 'Acheter un véhicule' : 'How to Buy a Vehicle',
      subtitle: fr ? 'Le processus légal en 7 étapes via un courtier licencié' : 'The 7-step legal flow through a licensed broker',
      steps: [
        { icon: <Search className="h-5 w-5" />,      en: 'Browse verified vehicle listings from licensed dealers. Check VIN, condition reports, photos, and reserve estimates.', fr: 'Parcourez les véhicules vérifiés de concessionnaires licenciés. Vérifiez le NIV, les rapports de condition, les photos et les estimations.' },
        { icon: <Users className="h-5 w-5" />,       en: 'Find a licensed broker. Canadian law requires a licensed dealer to bid at wholesale vehicle auctions. Browse our verified broker directory and choose one in your province.', fr: 'Trouvez un courtier licencié. La loi canadienne exige qu\'un concessionnaire licencié enchérisse aux enchères de véhicules en gros. Parcourez notre répertoire vérifié et choisissez-en un dans votre province.' },
        { icon: <CreditCard className="h-5 w-5" />,  en: 'Request a partnership. A $500 refundable security deposit is held (not charged) on your card as a good-faith commitment. It is released after your vehicle is handed over.', fr: 'Demandez un partenariat. Une caution de 500 $ remboursable est retenue (non débitée) sur votre carte en gage de bonne foi. Elle est libérée après la remise du véhicule.' },
        { icon: <Gavel className="h-5 w-5" />,       en: 'Authorize your maximum bid. Your broker places a proxy bid on your behalf — they are the legal bidder of record. You are fully protected.', fr: 'Autorisez votre enchère maximale. Votre courtier place une enchère par procuration en votre nom — il est l\'enchérisseur officiel. Vous êtes entièrement protégé.' },
        { icon: <Star className="h-5 w-5" />,        en: 'Auction closes — invoice generated. If your broker wins, BidVex instantly generates a detailed invoice showing exactly what you owe and to whom.', fr: 'L\'enchère ferme — la facture est générée. Si votre courtier gagne, BidVex génère instantanément une facture détaillée indiquant ce que vous devez et à qui.' },
        { icon: <DollarSign className="h-5 w-5" />,  en: 'Two separate payments: (1) BidVex platform fee + broker service fee via Stripe (one secure checkout). (2) Vehicle hammer price directly to your broker via bank wire or certified cheque. BidVex never touches the vehicle price.', fr: 'Deux paiements distincts : (1) Frais de plateforme BidVex + frais de courtier via Stripe (un seul paiement sécurisé). (2) Prix marteau du véhicule directement à votre courtier par virement bancaire ou chèque certifié. BidVex ne touche jamais au prix du véhicule.' },
        { icon: <Truck className="h-5 w-5" />,       en: 'Pick up your vehicle. Once your broker confirms full payment received, you get an 8-character pickup code. Show it at the seller\'s location with your ID. The vehicle is yours.', fr: 'Récupérez votre véhicule. Une fois que votre courtier confirme le paiement complet, vous recevez un code de retrait de 8 caractères. Présentez-le sur place avec votre pièce d\'identité. Le véhicule est à vous.' },
      ],
      cta: { label: fr ? 'Trouver un courtier' : 'Find a Broker', href: '/brokers' },
    },
    {
      id: 'tips',
      icon: <Lightbulb className="h-7 w-7" />,
      color: 'from-yellow-500 to-amber-500',
      bg: 'bg-yellow-50 dark:bg-yellow-950',
      border: 'border-yellow-200 dark:border-yellow-800',
      title: fr ? 'Conseils pro' : 'Pro Tips',
      subtitle: fr ? 'Maximisez vos profits et vendez plus vite' : 'Maximize profits and sell faster',
      steps: [
        { icon: <Star className="h-5 w-5" />, en: 'Use high-quality photos from multiple angles. First impressions matter.', fr: 'Utilisez des photos de haute qualité sous plusieurs angles. La première impression compte.' },
        { icon: <TrendingUp className="h-5 w-5" />, en: 'Set a competitive starting price. Lower starts attract more bidders and drive up the final price.', fr: 'Fixez un prix de départ compétitif. Des prix plus bas attirent plus d\'enchérisseurs et augmentent le prix final.' },
        { icon: <Bell className="h-5 w-5" />, en: 'Use Promoted Listings to boost visibility. Featured items sell 3x faster.', fr: 'Utilisez les annonces promues pour plus de visibilité. Les articles vedettes se vendent 3x plus vite.' },
        { icon: <Users className="h-5 w-5" />, en: 'Build your seller reputation. Respond quickly, ship promptly, and earn 5-star reviews.', fr: 'Bâtissez votre réputation de vendeur. Répondez vite, expédiez rapidement et obtenez des avis 5 étoiles.' },
      ],
    },
  ];

  const faqs = [
    { q: fr ? 'BidVex est-il sécuritaire?' : 'Is BidVex safe?', a: fr ? 'Oui. Tous les paiements sont traités par Stripe avec chiffrement SSL. Les vendeurs sont vérifiés et nous utilisons la détection de fraude par IA.' : 'Yes. All payments are processed by Stripe with SSL encryption. Sellers are verified and we use AI-powered fraud detection.' },
    { q: fr ? 'Quels sont les frais?' : 'What are the fees?', a: fr ? 'Acheteurs (non-véhicules) : prime de 5 %. Vendeurs (non-véhicules) : commission de 4 %. Véhicules : un courtier licencié est requis — vous payez à BidVex 2,5 % de frais de plateforme + les frais de service du courtier + TPS/TVQ (sur les services), tandis que le prix marteau est réglé directement avec le courtier en dehors de BidVex.' : 'Non-vehicle buyers: 5% premium. Non-vehicle sellers: 4% commission. Vehicles: a licensed broker is required — you pay BidVex 2.5% platform fee + broker service fee + GST/QST (on the service fees only), while the vehicle hammer price is settled directly with your broker outside of BidVex.' },
    { q: fr ? 'Comment fonctionne le paiement?' : 'How does payment work?', a: fr ? 'Les paiements sont traités automatiquement via Stripe. Les vendeurs reçoivent leurs fonds dans les 2-7 jours ouvrables.' : 'Payments are processed automatically via Stripe. Sellers receive their funds within 2-7 business days.' },
    { q: fr ? 'Puis-je vendre des véhicules?' : 'Can I sell vehicles?', a: fr ? 'Seuls les concessionnaires de véhicules licenciés par leur province (OMVIC, AMVIC, VSA, SAAQ, etc.) peuvent publier des véhicules. Postulez via la page "Devenir vendeur de véhicules".' : 'Only province-licensed vehicle dealers (OMVIC, AMVIC, VSA, SAAQ, etc.) can list vehicles. Apply via the "Become a Vehicle Seller" page.' },
    { q: fr ? 'Comment fonctionne le programme d\'affiliation?' : 'How does the affiliate program work?', a: fr ? 'Partagez votre lien unique. Vous gagnez 10% des frais BidVex sur chaque vente d\'un utilisateur référé. Les paiements sont automatiques.' : 'Share your unique link. You earn 10% of BidVex platform fees on every sale from a referred user. Payments are automatic.' },
    { q: fr ? 'Que se passe-t-il si je suis surenchéri?' : 'What happens if I\'m outbid?', a: fr ? 'Vous recevez une notification instantanée par courriel et dans l\'application. Vous pouvez immédiatement placer une nouvelle enchère.' : 'You receive an instant notification by email and in-app. You can immediately place a new bid.' },
    { q: fr ? 'BidVex livre-t-il les articles?' : 'Does BidVex deliver items?', a: fr ? 'BidVex est une plateforme d\'enchères. L\'expédition est arrangée entre l\'acheteur et le vendeur. Nous recommandons d\'utiliser un service de livraison avec suivi.' : 'BidVex is an auction platform. Shipping is arranged between buyer and seller. We recommend using a tracked delivery service.' },
  ];

  return (
    <div className="min-h-screen" data-testid="how-it-works-page">
      {/* Hero */}
      <section className="relative py-20 px-4 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan-900/20 via-transparent to-transparent" />
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/10 backdrop-blur text-sm font-medium mb-6">
            <Zap className="h-4 w-4 text-cyan-400" />
            {fr ? 'Plateforme d\'enchères #1 au Canada' : '#1 Auction Platform in Canada'}
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold mb-4 leading-tight">
            {fr ? 'Comment fonctionne BidVex' : 'How BidVex Works'}
          </h1>
          <p className="text-lg text-slate-300 max-w-2xl mx-auto mb-8">
            {fr
              ? 'Achetez, vendez et enchérissez en toute confiance. Paiements sécurisés, vendeurs vérifiés, et conformité complète.'
              : 'Buy, sell, and bid with confidence. Secure payments, verified sellers, and full regulatory compliance.'}
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link to="/auth">
              <Button size="lg" className="bg-cyan-500 hover:bg-cyan-600 text-white font-semibold gap-2" data-testid="hero-signup-cta">
                {fr ? 'Créer un compte gratuit' : 'Create Free Account'}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link to="/marketplace">
              <Button size="lg" variant="outline" className="border-white/30 text-white hover:bg-white/10 gap-2" data-testid="hero-browse-cta">
                {fr ? 'Parcourir le marché' : 'Browse Marketplace'}
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Trust Signals */}
      <section className="py-6 px-4 bg-slate-50 dark:bg-slate-900 border-y">
        <div className="max-w-5xl mx-auto flex flex-wrap justify-center gap-8 text-sm text-slate-600 dark:text-slate-400">
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-green-600" />
            <span>{fr ? 'Paiements sécurisés via Stripe' : 'Secure Payments via Stripe'}</span>
          </div>
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-blue-600" />
            <span>{fr ? 'Vendeurs vérifiés' : 'Verified Sellers'}</span>
          </div>
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-purple-600" />
            <span>{fr ? 'Détection de fraude par IA' : 'AI Fraud Detection'}</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-cyan-600" />
            <span>{fr ? 'Conforme Loi 25 (Québec)' : 'Quebec Law 25 Compliant'}</span>
          </div>
        </div>
      </section>

      {/* Sections */}
      <section className="py-16 px-4">
        <div className="max-w-5xl mx-auto space-y-12">
          {sections.map((section) => (
            <Card key={section.id} className={`overflow-hidden ${section.border}`} data-testid={`section-${section.id}`}>
              <div className={`px-6 py-5 bg-gradient-to-r ${section.color} text-white flex items-center gap-4`}>
                <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center shrink-0">
                  {section.icon}
                </div>
                <div>
                  <h2 className="text-xl font-bold">{section.title}</h2>
                  <p className="text-sm text-white/80">{section.subtitle}</p>
                </div>
              </div>
              <CardContent className="p-6">
                <div className="grid sm:grid-cols-2 gap-4">
                  {section.steps.map((step, i) => (
                    <div key={i} className="flex gap-3 items-start">
                      <div className={`w-8 h-8 rounded-lg ${section.bg} flex items-center justify-center shrink-0 mt-0.5`}>
                        <span className="text-xs font-bold text-slate-600 dark:text-slate-300">{i + 1}</span>
                      </div>
                      <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                        {fr ? step.fr : step.en}
                      </p>
                    </div>
                  ))}
                </div>
                {section.cta && (
                  <div className="mt-6 pt-4 border-t">
                    <Link to={section.cta.href}>
                      <Button className={`bg-gradient-to-r ${section.color} text-white border-0 gap-2`} data-testid={`cta-${section.id}`}>
                        {section.cta.label}
                        <ArrowRight className="h-4 w-4" />
                      </Button>
                    </Link>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* FAQ Accordion */}
      <section className="py-16 px-4 bg-slate-50 dark:bg-slate-900" data-testid="faq-section">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-10">
            <HelpCircle className="h-8 w-8 text-primary mx-auto mb-3" />
            <h2 className="text-2xl font-bold mb-2">
              {fr ? 'Questions fréquentes' : 'Frequently Asked Questions'}
            </h2>
            <p className="text-sm text-slate-500">{fr ? 'Tout ce que vous devez savoir' : 'Everything you need to know'}</p>
          </div>
          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <div key={i} className="border rounded-lg overflow-hidden bg-white dark:bg-slate-800" data-testid={`faq-item-${i}`}>
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full px-5 py-4 text-left flex items-center justify-between gap-4 hover:bg-slate-50 dark:hover:bg-slate-750 transition-colors"
                >
                  <span className="font-medium text-sm">{faq.q}</span>
                  {openFaq === i ? <ChevronUp className="h-4 w-4 shrink-0" /> : <ChevronDown className="h-4 w-4 shrink-0" />}
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-4 text-sm text-slate-600 dark:text-slate-400 leading-relaxed border-t pt-3">
                    {faq.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-16 px-4 bg-gradient-to-br from-slate-900 to-slate-800 text-white text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold mb-3">{fr ? 'Prêt à commencer?' : 'Ready to Get Started?'}</h2>
          <p className="text-slate-300 mb-8">{fr ? 'Rejoignez des milliers d\'acheteurs et vendeurs au Canada.' : 'Join thousands of buyers and sellers across Canada.'}</p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link to="/create-listing">
              <Button size="lg" className="bg-cyan-500 hover:bg-cyan-600 text-white font-semibold gap-2" data-testid="final-cta-sell">
                {fr ? 'Commencer à vendre' : 'Start Selling'}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link to="/marketplace">
              <Button size="lg" className="bg-white text-slate-900 hover:bg-slate-100 font-semibold gap-2" data-testid="final-cta-bid">
                {fr ? 'Commencer à enchérir' : 'Start Bidding'}
              </Button>
            </Link>
            <Link to="/become-a-partner">
              <Button size="lg" variant="outline" className="border-white/30 text-white hover:bg-white/10 gap-2" data-testid="final-cta-partner">
                {fr ? 'Devenir partenaire' : 'Apply as Partner'}
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default HowItWorks;
