import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { 
  Shield, Mail, Lock, Eye, Users, Building2,
  CreditCard, Database, Cookie, Cpu, Clock, CheckCircle,
  FileText, Globe, UserCheck, Server, AlertTriangle
} from 'lucide-react';

export const PrivacyFR = () => {
  return (
    <div className="min-h-screen py-12 px-4 max-w-4xl mx-auto">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3 mb-4">
            <Shield className="h-8 w-8 text-primary" />
            <CardTitle className="text-3xl">Politique de confidentialité de BidVex</CardTitle>
          </div>
          <p className="text-muted-foreground">Dernière mise à jour : Mars 2026</p>
        </CardHeader>
        <CardContent className="prose prose-sm max-w-none space-y-8">
          
          {/* Table des matières */}
          <section className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Table des matières</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <ol className="list-decimal pl-6 space-y-1 text-blue-600 dark:text-blue-400">
                <li><a href="#introduction" className="hover:underline">Introduction</a></li>
                <li><a href="#information-collect" className="hover:underline">Renseignements recueillis</a></li>
                <li><a href="#purpose" className="hover:underline">Finalités du traitement</a></li>
                <li><a href="#sharing" className="hover:underline">Partage et divulgation</a></li>
                <li><a href="#cookies" className="hover:underline">Témoins et suivi</a></li>
              </ol>
              <ol className="list-decimal pl-6 space-y-1 text-blue-600 dark:text-blue-400" start={6}>
                <li><a href="#ai" className="hover:underline">Moteur de recommandation IA</a></li>
                <li><a href="#security" className="hover:underline">Sécurité des données</a></li>
                <li><a href="#rights" className="hover:underline">Vos droits en matière de confidentialité</a></li>
                <li><a href="#retention" className="hover:underline">Conservation des données</a></li>
                <li><a href="#contact" className="hover:underline">Nous joindre</a></li>
              </ol>
            </div>
          </section>

          {/* 1. Introduction */}
          <section id="introduction">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">1</span>
              Introduction
            </h2>
            <p className="mb-4">
              Chez BidVex Inc. (« BidVex », « nous », « notre »), nous nous engageons à protéger la confidentialité et la sécurité de vos renseignements personnels. La présente Politique de confidentialité explique comment nous recueillons, utilisons, divulguons et protégeons vos données lorsque vous utilisez notre plateforme d'enchères en ligne (« la Plateforme »).
            </p>
            <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <p className="text-blue-800 dark:text-blue-200 text-sm">
                <strong>Conformité :</strong> Cette politique est conçue pour se conformer à la <strong>Loi sur la protection des renseignements personnels dans le secteur privé (Loi 25 du Québec)</strong>, à la <strong>Loi sur la protection des renseignements personnels et les documents électroniques (LPRPDE)</strong> et au <strong>Règlement général sur la protection des données (RGPD)</strong>.
              </p>
            </div>
          </section>

          {/* 2. Renseignements recueillis */}
          <section id="information-collect">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">2</span>
              <Database className="h-5 w-5" /> Renseignements recueillis
            </h2>
            <p className="mb-4">Pour fournir un environnement d'enchères sécurisé et efficace, nous recueillons les catégories de données suivantes :</p>
            
            <div className="space-y-4">
              {/* Vendeurs */}
              <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg p-5">
                <h3 className="text-lg font-semibold text-emerald-800 dark:text-emerald-200 mb-3 flex items-center gap-2">
                  <Building2 className="h-5 w-5" /> 2.1 Vendeurs (y compris les sections Véhicules et Équipements)
                </h3>
                <div className="space-y-3 text-emerald-700 dark:text-emerald-300">
                  <div className="flex items-start gap-2">
                    <UserCheck className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Données d'identité et de vérification :</strong> Nom complet, date de naissance et pièce d'identité émise par le gouvernement (pour la vérification d'identité et la prévention de la fraude).</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <Mail className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Coordonnées :</strong> Adresse courriel, numéro de téléphone et adresse physique (professionnelle ou résidentielle).</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <Building2 className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Données d'entreprise :</strong> Nom de l'entreprise, numéros d'identification fiscale et permis de concessionnaire (le cas échéant).</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <FileText className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Données sur les actifs :</strong> NIV, rapports d'historique des véhicules/équipements, marque, modèle, année, photos et documents de propriété connexes.</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <CreditCard className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Données financières :</strong> Coordonnées bancaires et informations de règlement pour les versements.</p>
                  </div>
                </div>
              </div>

              {/* Acheteurs */}
              <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-5">
                <h3 className="text-lg font-semibold text-blue-800 dark:text-blue-200 mb-3 flex items-center gap-2">
                  <Users className="h-5 w-5" /> 2.2 Acheteurs
                </h3>
                <div className="space-y-3 text-blue-700 dark:text-blue-300">
                  <div className="flex items-start gap-2">
                    <UserCheck className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Données d'identité :</strong> Nom complet et nom d'utilisateur.</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <Mail className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Coordonnées :</strong> Adresse courriel, numéro de téléphone et adresse de facturation/livraison.</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <CreditCard className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Données de paiement :</strong> Carte de crédit et détails du mode de paiement. <em>Remarque : Toutes les données de paiement sont traitées de manière sécurisée via Stripe; BidVex ne stocke pas les numéros de carte de crédit complets.</em></p>
                  </div>
                  <div className="flex items-start gap-2">
                    <FileText className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Données de transaction :</strong> Historique des enchères, articles surveillés et registres des enchères remportées.</p>
                  </div>
                </div>
              </div>

              {/* Données techniques */}
              <div className="bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-5">
                <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-3 flex items-center gap-2">
                  <Server className="h-5 w-5" /> 2.3 Données techniques (tous les utilisateurs)
                </h3>
                <p className="text-slate-600 dark:text-slate-400">
                  Adresse IP, type et version du navigateur, paramètre de fuseau horaire, identifiants d'appareil et informations sur le système d'exploitation pour la surveillance de la sécurité et l'optimisation de la plateforme.
                </p>
              </div>
            </div>
          </section>

          {/* 3. Finalités du traitement */}
          <section id="purpose">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">3</span>
              Finalités du traitement
            </h2>
            <p className="mb-4">Nous traitons vos données personnelles sur les bases juridiques suivantes :</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Nécessité contractuelle</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Pour faciliter les transactions d'enchères, d'achat et de vente.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <Shield className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Vérification d'identité</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Pour maintenir un marché de haute confiance et prévenir la fraude.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <Mail className="h-5 w-5 text-purple-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Communication</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Pour permettre la messagerie sécurisée entre acheteurs et vendeurs.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <CreditCard className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Traitement des paiements</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Pour traiter les frais de transaction de manière sécurisée via Stripe.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <Cpu className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Amélioration</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Pour analyser les habitudes d'utilisation et optimiser les recommandations.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <FileText className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Conformité juridique</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Pour satisfaire aux obligations fiscales, comptables et de lutte contre le blanchiment.</p>
                </div>
              </div>
            </div>
          </section>

          {/* 4. Partage et divulgation */}
          <section id="sharing">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">4</span>
              Partage et divulgation des renseignements
            </h2>
            
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4">
              <p className="text-red-800 dark:text-red-200 font-semibold flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Nous ne vendons pas vos données personnelles à des tiers.
              </p>
            </div>
            
            <p className="mb-3">La divulgation se produit uniquement dans les contextes suivants :</p>
            
            <div className="space-y-3">
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <h4 className="font-semibold">Conclusion de la transaction</h4>
                <p className="text-sm text-slate-600 dark:text-slate-400">À la conclusion d'une enchère réussie, l'acheteur gagnant et le vendeur reçoivent les coordonnées de l'autre pour finaliser la logistique.</p>
              </div>
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <h4 className="font-semibold">Profil public</h4>
                <p className="text-sm text-slate-600 dark:text-slate-400">Les indicateurs de confiance, les badges vérifiés et les évaluations des utilisateurs sont affichés publiquement pour maintenir la transparence de la communauté.</p>
              </div>
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <h4 className="font-semibold">Fournisseurs de services</h4>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">Nous partageons des données avec des partenaires de confiance strictement à des fins opérationnelles :</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <div className="bg-white dark:bg-slate-800 rounded px-3 py-2 text-center text-xs">
                    <p className="font-semibold">Stripe</p>
                    <p className="text-slate-500">Paiements</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded px-3 py-2 text-center text-xs">
                    <p className="font-semibold">SendGrid</p>
                    <p className="text-slate-500">Courriel</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded px-3 py-2 text-center text-xs">
                    <p className="font-semibold">Twilio</p>
                    <p className="text-slate-500">SMS</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded px-3 py-2 text-center text-xs">
                    <p className="font-semibold">AWS/GCP</p>
                    <p className="text-slate-500">Hébergement</p>
                  </div>
                </div>
              </div>
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <h4 className="font-semibold">Autorités juridiques</h4>
                <p className="text-sm text-slate-600 dark:text-slate-400">Nous pouvons divulguer des données si la loi, une ordonnance du tribunal ou la protection des droits et de la sécurité de nos utilisateurs l'exige.</p>
              </div>
            </div>
          </section>

          {/* 5. Témoins */}
          <section id="cookies">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">5</span>
              <Cookie className="h-5 w-5" /> Témoins et suivi
            </h2>
            <p className="mb-4">Nous utilisons des témoins (cookies) pour améliorer votre expérience et analyser le trafic.</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4">
                <h4 className="font-semibold text-green-800 dark:text-green-200 mb-1">Témoins essentiels</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Requis pour les fonctionnalités de base de la plateforme (p. ex., rester connecté).</p>
              </div>
              <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h4 className="font-semibold text-blue-800 dark:text-blue-200 mb-1">Témoins analytiques</h4>
                <p className="text-sm text-blue-700 dark:text-blue-300">Nous aident à comprendre comment les utilisateurs interagissent avec le site.</p>
              </div>
              <div className="bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 rounded-lg p-4">
                <h4 className="font-semibold text-purple-800 dark:text-purple-200 mb-1">Témoins de personnalisation</h4>
                <p className="text-sm text-purple-700 dark:text-purple-300">Mémorisent vos préférences, comme la langue (anglais/français).</p>
              </div>
              <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <h4 className="font-semibold text-amber-800 dark:text-amber-200 mb-1">Témoins publicitaires</h4>
                <p className="text-sm text-amber-700 dark:text-amber-300">Utilisés pour diffuser des publicités pertinentes. Désactivation disponible via les paramètres Google Ads.</p>
              </div>
            </div>
          </section>

          {/* 6. IA */}
          <section id="ai">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center text-purple-600 text-sm font-bold">6</span>
              <Cpu className="h-5 w-5 text-purple-600" /> Moteur de recommandation alimenté par l'IA
            </h2>
            
            <div className="bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 rounded-lg p-5">
              <p className="text-purple-800 dark:text-purple-200 mb-3">
                BidVex utilise un moteur de recommandation exclusif pour suggérer des articles basés sur :
              </p>
              <ul className="list-disc pl-6 space-y-1 text-purple-700 dark:text-purple-300 mb-4">
                <li>Votre historique de navigation et de recherche</li>
                <li>Vos habitudes d'enchères et d'achats passés</li>
                <li>Les articles ajoutés à votre « Liste de surveillance »</li>
              </ul>
              <div className="bg-white dark:bg-slate-800 rounded-lg p-3 border border-purple-200 dark:border-purple-700">
                <p className="text-sm flex items-center gap-2">
                  <Eye className="h-4 w-4 text-purple-600" />
                  <span><strong>Désactivation :</strong> Les utilisateurs peuvent désactiver les recommandations personnalisées dans leurs Paramètres de compte. Cela n'affectera pas les fonctionnalités de base des enchères ou de la plateforme.</span>
                </p>
              </div>
            </div>
          </section>

          {/* 7. Sécurité */}
          <section id="security">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center text-green-600 text-sm font-bold">7</span>
              <Lock className="h-5 w-5 text-green-600" /> Sécurité des données
            </h2>
            <p className="mb-4">Nous mettons en œuvre des mesures de sécurité de pointe pour protéger vos données :</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <Lock className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">TLS/SSL</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Chiffrement en transit</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <Shield className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">AES-256</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Chiffrement au repos</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <CreditCard className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">PCI-DSS</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Conformité des paiements</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <UserCheck className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">AMF</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Auth. multifactorielle</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <Users className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">Basé sur les rôles</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Contrôle d'accès</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <Eye className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">24/7</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Surveillance de sécurité</p>
              </div>
            </div>
          </section>

          {/* 8. Droits */}
          <section id="rights">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">8</span>
              <Globe className="h-5 w-5" /> Vos droits en matière de confidentialité
            </h2>
            <p className="mb-4">Selon votre juridiction (Québec, Canada ou UE), vous avez les droits suivants :</p>
            
            <div className="space-y-3">
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <Eye className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Accès</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Le droit de demander une copie des données personnelles que nous détenons à votre sujet.</p>
                </div>
              </div>
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <FileText className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Rectification</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Le droit de corriger des informations inexactes ou incomplètes.</p>
                </div>
              </div>
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <AlertTriangle className="h-5 w-5 text-red-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Suppression (Droit à l'oubli)</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Le droit de demander la suppression de vos données, sous réserve des exigences légales de conservation.</p>
                </div>
              </div>
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <Database className="h-5 w-5 text-purple-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Portabilité</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Le droit de recevoir vos données dans un format structuré et lisible par machine.</p>
                </div>
              </div>
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <Lock className="h-5 w-5 text-amber-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Retrait du consentement</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Le droit d'arrêter le traitement pour des fins spécifiques (p. ex., marketing).</p>
                </div>
              </div>
            </div>
            
            <div className="mt-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <p className="text-blue-800 dark:text-blue-200 text-sm">
                <strong>Pour exercer ces droits,</strong> veuillez contacter notre Responsable de la protection des données à <a href="mailto:support@bidvex.com" className="underline">support@bidvex.com</a>.
              </p>
            </div>
          </section>

          {/* 9. Conservation */}
          <section id="retention">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">9</span>
              <Clock className="h-5 w-5" /> Conservation des données
            </h2>
            
            <div className="space-y-3">
              <div className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl font-bold text-blue-600">7</span>
                </div>
                <div>
                  <h4 className="font-semibold">Données de compte</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Conservées pendant la durée de votre compte actif et jusqu'à 7 ans après la fermeture.</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl font-bold text-green-600">7</span>
                </div>
                <div>
                  <h4 className="font-semibold">Registres de transactions</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Conservés pendant 7 ans pour se conformer aux obligations fiscales et juridiques canadiennes et québécoises.</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900 rounded-lg flex items-center justify-center flex-shrink-0">
                  <CheckCircle className="h-8 w-8 text-amber-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Documents d'identification</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Supprimés une fois la vérification réussie, sauf si nécessaire pour la prévention continue de la fraude.</p>
                </div>
              </div>
            </div>
          </section>

          {/* 10. Nous joindre */}
          <section id="contact" className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">10</span>
              Nous joindre
            </h2>
            <p className="mb-4">Pour toute question concernant cette politique ou nos pratiques en matière de données, veuillez contacter :</p>
            
            <div className="bg-white dark:bg-slate-900 rounded-lg p-5 border border-slate-200 dark:border-slate-700">
              <p className="font-semibold text-lg mb-4">Responsable de la protection des données de BidVex</p>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                    <Mail className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Courriel</p>
                    <a href="mailto:support@bidvex.com" className="font-medium text-blue-600 hover:underline">support@bidvex.com</a>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Pied de page */}
          <div className="text-center text-sm text-muted-foreground pt-6 border-t">
            <p>&copy; 2026 BidVex Inc. Tous droits réservés.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PrivacyFR;
