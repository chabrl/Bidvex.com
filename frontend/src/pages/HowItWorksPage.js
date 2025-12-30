import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { 
  Search, UserPlus, Gavel, Trophy, CreditCard, 
  CheckCircle2, Sparkles, Shield, Clock, ArrowRight,
  ChevronDown, Play
} from 'lucide-react';
import { Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const HowItWorksPage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [cmsContent, setCmsContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [openFaq, setOpenFaq] = useState(null);
  const language = i18n.language || 'en';

  useEffect(() => {
    fetchContent();
  }, [language]);

  const fetchContent = async () => {
    setLoading(true);
    try {
      const response = await axios.get(
        `${API}/site-config/legal-pages?language=${language}`
      );

      if (response.data.success && response.data.pages.how_it_works) {
        setCmsContent(response.data.pages.how_it_works);
      }
    } catch (error) {
      console.error('[HowItWorks] Error fetching content:', error);
    } finally {
      setLoading(false);
    }
  };

  const steps = language === 'fr' ? [
    {
      icon: <Search className="h-10 w-10" />,
      title: "Parcourir et Découvrir",
      description: "Explorez des milliers d'articles uniques de vendeurs de confiance dans le monde entier. Utilisez les filtres pour trouver exactement ce que vous cherchez.",
      features: ["Filtres de recherche intelligents", "Navigation par catégorie", "Recherches sauvegardées"]
    },
    {
      icon: <UserPlus className="h-10 w-10" />,
      title: "Inscription Gratuite",
      description: "Créez votre compte gratuit en quelques secondes. Vérifiez votre identité pour débloquer toutes les capacités d'enchères.",
      features: ["Inscription rapide", "Vérification sécurisée", "Personnalisation du profil"]
    },
    {
      icon: <Gavel className="h-10 w-10" />,
      title: "Placer Votre Enchère",
      description: "Prêt à concourir? Entrez votre enchère maximale et notre système enchérira automatiquement pour vous jusqu'à votre maximum.",
      features: ["Enchères par procuration", "Alertes en temps réel", "Protection anti-sniping"]
    },
    {
      icon: <Trophy className="h-10 w-10" />,
      title: "Remporter l'Enchère",
      description: "Lorsque le minuteur atteint zéro et que vous avez l'enchère la plus élevée, vous gagnez! Recevez une confirmation instantanée.",
      features: ["Confirmation par e-mail", "Conversation automatique", "Paiement sécurisé"]
    },
    {
      icon: <CreditCard className="h-10 w-10" />,
      title: "Paiement Sécurisé",
      description: "BidVex utilise Stripe pour un traitement sécurisé. Votre carte enregistrée est automatiquement débitée du montant gagnant.",
      features: ["Conforme PCI DSS", "Cryptage de bout en bout", "Protection de l'acheteur"]
    }
  ] : [
    {
      icon: <Search className="h-10 w-10" />,
      title: "Browse & Discover",
      description: "Explore thousands of unique items from trusted sellers worldwide. Use filters to find exactly what you're looking for.",
      features: ["Smart search filters", "Category browsing", "Saved searches"]
    },
    {
      icon: <UserPlus className="h-10 w-10" />,
      title: "Register Free",
      description: "Create your free account in seconds. Verify your identity to unlock full bidding capabilities.",
      features: ["Quick signup", "Secure verification", "Profile customization"]
    },
    {
      icon: <Gavel className="h-10 w-10" />,
      title: "Place Your Bid",
      description: "Ready to compete? Enter your maximum bid and our system will automatically bid for you up to your max.",
      features: ["Proxy bidding", "Real-time alerts", "Anti-sniping protection"]
    },
    {
      icon: <Trophy className="h-10 w-10" />,
      title: "Win the Auction",
      description: "When the timer hits zero and you have the highest bid, you win! Receive instant confirmation.",
      features: ["Email confirmation", "Automatic handshake", "Secure payment"]
    },
    {
      icon: <CreditCard className="h-10 w-10" />,
      title: "Secure Payment",
      description: "BidVex uses Stripe for secure processing. Your saved card is automatically charged for the winning amount.",
      features: ["PCI DSS compliant", "End-to-end encryption", "Buyer protection"]
    }
  ];

  const faqs = language === 'fr' ? [
    {
      question: "Comment fonctionne l'anti-sniping?",
      answer: "Si une enchère est placée dans les 2 dernières minutes, l'horloge s'étend de 2 minutes. Cela garantit que tout le monde a une dernière chance équitable."
    },
    {
      question: "Puis-je retirer mon enchère?",
      answer: "Non, toutes les enchères sont des engagements contraignants. Veuillez enchérir soigneusement et uniquement sur des articles que vous avez l'intention d'acheter."
    },
    {
      question: "Offrez-vous la livraison?",
      answer: "Le ramassage local est notre protocole standard. Cependant, certains vendeurs offrent la livraison. Recherchez l'icône de livraison (📦) sur la page de détail du lot."
    },
    {
      question: "Que se passe-t-il si je suis surenchéri?",
      answer: "Vous recevrez une notification instantanée. Vous pouvez enchérir à nouveau si l'enchère est toujours active."
    }
  ] : [
    {
      question: "How does anti-sniping work?",
      answer: "If a bid is placed in the final 2 minutes, the clock extends by 2 minutes. This ensures everyone gets a fair final chance."
    },
    {
      question: "Can I retract my bid?",
      answer: "No, all bids are binding commitments. Please bid carefully and only on items you intend to purchase."
    },
    {
      question: "Do you offer shipping?",
      answer: "Local pickup is our standard protocol. However, some sellers offer shipping. Look for the Shipping Icon (📦) on the lot detail page."
    },
    {
      question: "What if I get outbid?",
      answer: "You'll receive instant notification. You can bid again if the auction is still active."
    }
  ];

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-blue-50 to-white">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">
            {language === 'fr' ? 'Chargement...' : 'Loading...'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Hero Section - Inspired by screenshot */}
      <section className="relative bg-gradient-to-br from-[#0A1F44] via-[#1E3A8A] to-[#2563EB] text-white overflow-hidden">
        {/* Animated background elements */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-10 w-72 h-72 bg-cyan-400 rounded-full filter blur-3xl animate-pulse"></div>
          <div className="absolute bottom-20 right-10 w-96 h-96 bg-blue-400 rounded-full filter blur-3xl animate-pulse delay-1000"></div>
        </div>

        <div className="relative container mx-auto px-4 py-20 md:py-32 text-center">
          {/* Badge */}
          <Badge 
            variant="secondary" 
            className="mb-6 bg-white/10 text-white border-white/20 backdrop-blur-sm px-4 py-2 text-sm font-normal"
          >
            <Sparkles className="h-4 w-4 mr-2" />
            {language === 'fr' ? 'Votre Guide pour Gagner' : 'Your Guide to Winning'}
          </Badge>

          {/* Main Heading */}
          <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold mb-6 leading-tight">
            {language === 'fr' ? (
              <>
                Maîtrisez l'Art des{' '}
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
                  Enchères sur BidVex
                </span>
              </>
            ) : (
              <>
                Master the Art of{' '}
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-400">
                  Bidding on BidVex
                </span>
              </>
            )}
          </h1>

          {/* Subheading */}
          <p className="text-lg md:text-xl text-blue-100 mb-10 max-w-3xl mx-auto">
            {language === 'fr' 
              ? "Rejoignez des milliers d'enchérisseurs intelligents qui ont découvert le frisson de gagner. Suivez notre processus simple en 5 étapes pour commencer votre voyage."
              : "Join thousands of smart bidders who've discovered the thrill of winning. Follow our simple 5-step process to start your journey."
            }
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button 
              onClick={() => navigate('/marketplace')}
              size="lg"
              className="bg-white text-blue-900 hover:bg-blue-50 px-8 py-6 text-lg font-semibold shadow-xl"
            >
              {language === 'fr' ? 'Commencer à Enchérir' : 'Start Bidding Now'}
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button 
              onClick={() => document.getElementById('steps')?.scrollIntoView({ behavior: 'smooth' })}
              size="lg"
              variant="outline"
              className="bg-transparent border-2 border-white text-white hover:bg-white/10 px-8 py-6 text-lg font-semibold"
            >
              <Play className="mr-2 h-5 w-5" />
              {language === 'fr' ? 'Regarder Comment' : 'See How It Works'}
            </Button>
          </div>
        </div>

        {/* Wave SVG at bottom */}
        <div className="absolute bottom-0 left-0 w-full">
          <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-auto">
            <path d="M0 0L60 10C120 20 240 40 360 46.7C480 53 600 47 720 43.3C840 40 960 40 1080 46.7C1200 53 1320 67 1380 73.3L1440 80V120H1380C1320 120 1200 120 1080 120C960 120 840 120 720 120C600 120 480 120 360 120C240 120 120 120 60 120H0V0Z" fill="white"/>
          </svg>
        </div>
      </section>

      {/* 5-Step Process */}
      <section id="steps" className="py-20 bg-white">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              {language === 'fr' ? 'Comment Ça Marche' : 'How It Works'}
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              {language === 'fr' 
                ? "Suivez ces 5 étapes simples pour commencer à gagner sur BidVex"
                : "Follow these 5 simple steps to start winning on BidVex"
              }
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-7xl mx-auto">
            {steps.map((step, index) => (
              <Card 
                key={index} 
                className="relative border-2 hover:border-blue-500 transition-all duration-300 hover:shadow-xl group"
              >
                {/* Step Number */}
                <div className="absolute -top-4 -left-4 w-12 h-12 bg-gradient-to-br from-blue-600 to-cyan-500 text-white rounded-full flex items-center justify-center text-xl font-bold shadow-lg">
                  {index + 1}
                </div>

                <CardContent className="pt-8 pb-6 px-6">
                  {/* Icon */}
                  <div className="mb-4 text-blue-600 group-hover:scale-110 transition-transform">
                    {step.icon}
                  </div>

                  {/* Title */}
                  <h3 className="text-xl font-bold text-gray-900 mb-3">
                    {step.title}
                  </h3>

                  {/* Description */}
                  <p className="text-gray-600 mb-4">
                    {step.description}
                  </p>

                  {/* Features */}
                  <ul className="space-y-2">
                    {step.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                        <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Key Features */}
      <section className="py-20 bg-gradient-to-b from-blue-50 to-white">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              {language === 'fr' ? 'Pourquoi Choisir BidVex?' : 'Why Choose BidVex?'}
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-cyan-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <Shield className="h-8 w-8 text-white" />
              </div>
              <h3 className="text-xl font-bold mb-2">
                {language === 'fr' ? 'Sécurisé & Fiable' : 'Safe & Secure'}
              </h3>
              <p className="text-gray-600">
                {language === 'fr' 
                  ? 'Vérification obligatoire et traitement des paiements cryptés'
                  : 'Mandatory verification and encrypted payment processing'
                }
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-cyan-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <Clock className="h-8 w-8 text-white" />
              </div>
              <h3 className="text-xl font-bold mb-2">
                {language === 'fr' ? 'Enchères Équitables' : 'Fair Bidding'}
              </h3>
              <p className="text-gray-600">
                {language === 'fr' 
                  ? "Protection anti-sniping pour garantir que tout le monde ait une chance"
                  : 'Anti-sniping protection ensures everyone gets a fair shot'
                }
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-cyan-500 rounded-full flex items-center justify-center mx-auto mb-4">
                <Sparkles className="h-8 w-8 text-white" />
              </div>
              <h3 className="text-xl font-bold mb-2">
                {language === 'fr' ? 'Objets Uniques' : 'Unique Items'}
              </h3>
              <p className="text-gray-600">
                {language === 'fr' 
                  ? "Des milliers d'articles uniques de vendeurs de confiance"
                  : 'Thousands of unique items from trusted sellers worldwide'
                }
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-20 bg-white">
        <div className="container mx-auto px-4 max-w-4xl">
          <div className="text-center mb-12">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              {language === 'fr' ? 'Questions Fréquentes' : 'Frequently Asked Questions'}
            </h2>
          </div>

          <div className="space-y-4">
            {faqs.map((faq, index) => (
              <Card key={index} className="border-2">
                <CardContent 
                  className="p-0 cursor-pointer"
                  onClick={() => setOpenFaq(openFaq === index ? null : index)}
                >
                  <div className="p-6 flex justify-between items-center">
                    <h3 className="text-lg font-semibold text-gray-900 pr-4">
                      {faq.question}
                    </h3>
                    <ChevronDown 
                      className={`h-5 w-5 text-gray-500 flex-shrink-0 transition-transform ${
                        openFaq === index ? 'transform rotate-180' : ''
                      }`}
                    />
                  </div>
                  {openFaq === index && (
                    <div className="px-6 pb-6">
                      <p className="text-gray-600">{faq.answer}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CMS Content Section (if admin added custom content) */}
      {cmsContent && cmsContent.content && cmsContent.content !== '' && (
        <section className="py-20 bg-gray-50">
          <div className="container mx-auto px-4 max-w-4xl">
            <Card>
              <CardContent className="p-8 md:p-12">
                <div 
                  className="prose prose-lg max-w-none"
                  dangerouslySetInnerHTML={{ __html: cmsContent.content }}
                />
              </CardContent>
            </Card>
          </div>
        </section>
      )}

      {/* Final CTA */}
      <section className="py-20 bg-gradient-to-br from-blue-900 to-cyan-700 text-white">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            {language === 'fr' ? 'Prêt à Commencer?' : 'Ready to Get Started?'}
          </h2>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            {language === 'fr' 
              ? "Rejoignez BidVex aujourd'hui et découvrez le frisson de gagner aux enchères en ligne."
              : 'Join BidVex today and experience the thrill of winning online auctions.'
            }
          </p>
          <Button 
            onClick={() => navigate('/auth?mode=register')}
            size="lg"
            className="bg-white text-blue-900 hover:bg-blue-50 px-8 py-6 text-lg font-semibold shadow-xl"
          >
            {language === 'fr' ? 'Créer un Compte Gratuit' : 'Create Free Account'}
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </section>
    </div>
  );
};

export default HowItWorksPage;
