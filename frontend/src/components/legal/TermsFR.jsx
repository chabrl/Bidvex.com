import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { 
  FileText, Mail, Shield, AlertTriangle, Gavel, 
  Users, DollarSign, Scale, Lock, Ban, Clock, CheckCircle,
  XCircle, CreditCard, Building2
} from 'lucide-react';

export const TermsFR = () => {
  return (
    <div className="min-h-screen py-12 px-4 max-w-4xl mx-auto">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3 mb-4">
            <FileText className="h-8 w-8 text-primary" />
            <CardTitle className="text-3xl">Conditions générales d'utilisation de BidVex</CardTitle>
          </div>
          <p className="text-muted-foreground">Dernière mise à jour : Mars 2026</p>
        </CardHeader>
        <CardContent className="prose prose-sm max-w-none space-y-8">
          
          {/* Table des matières */}
          <section className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Table des matières</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <ol className="list-decimal pl-6 space-y-1 text-blue-600 dark:text-blue-400">
                <li><a href="#introduction" className="hover:underline">Introduction et acceptation</a></li>
                <li><a href="#platform-role" className="hover:underline">Rôle de la plateforme et avertissements</a></li>
                <li><a href="#user-accounts" className="hover:underline">Comptes d'utilisateur</a></li>
                <li><a href="#seller" className="hover:underline">Responsabilités du vendeur</a></li>
                <li><a href="#buyer" className="hover:underline">Responsabilités de l'acheteur</a></li>
                <li><a href="#bidding" className="hover:underline">Règles d'enchères</a></li>
                <li><a href="#fees" className="hover:underline">Frais, taxes et paiements</a></li>
                <li><a href="#as-is" className="hover:underline">Clause « TEL QUEL / LÀ OÙ IL SE TROUVE »</a></li>
              </ol>
              <ol className="list-decimal pl-6 space-y-1 text-blue-600 dark:text-blue-400" start={9}>
                <li><a href="#disputes" className="hover:underline">Résolution des litiges</a></li>
                <li><a href="#ip" className="hover:underline">Propriété intellectuelle</a></li>
                <li><a href="#prohibited" className="hover:underline">Conduites interdites</a></li>
                <li><a href="#liability" className="hover:underline">Limitation de responsabilité</a></li>
                <li><a href="#termination" className="hover:underline">Suspension et résiliation</a></li>
                <li><a href="#changes" className="hover:underline">Modifications des conditions</a></li>
                <li><a href="#governing" className="hover:underline">Droit applicable</a></li>
                <li><a href="#contact" className="hover:underline">Coordonnées</a></li>
              </ol>
            </div>
          </section>

          {/* 1. Introduction */}
          <section id="introduction">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">1</span>
              Introduction et acceptation des conditions
            </h2>
            <p className="mb-3">
              Bienvenue sur BidVex. Les présentes conditions générales d'utilisation (« Conditions ») constituent un accord juridiquement contraignant entre vous (« Utilisateur », « vous » ou « votre ») et BidVex Inc. (« BidVex », « nous », « notre »). Ces Conditions régissent votre accès et votre utilisation de notre plateforme d'enchères en ligne, de notre site Web et de nos services connexes (collectivement, « la Plateforme »).
            </p>
            <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4 my-4">
              <p className="text-blue-800 dark:text-blue-200">
                <strong>En créant un compte, en naviguant sur la Plateforme ou en participant à une enchère,</strong> vous reconnaissez avoir lu, compris et accepté d'être lié par les présentes Conditions ainsi que par notre Politique de confidentialité. Si vous n'acceptez pas ces Conditions, vous ne devez pas accéder à la Plateforme ni l'utiliser.
              </p>
            </div>
            <p>BidVex facilite les enchères en ligne pour divers articles, y compris, mais sans s'y limiter, les véhicules, les biens de consommation et les services commerciaux.</p>
          </section>

          {/* 2. Rôle de la plateforme */}
          <section id="platform-role">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">2</span>
              Rôle de la plateforme et avertissements
            </h2>
            
            <div className="space-y-4">
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold text-lg">2.1 Marché indépendant</h3>
                <p>BidVex est un marché numérique et n'est pas un vendeur, un concessionnaire, un courtier, un propriétaire, un dépositaire ou un mandataire des articles mis en vente. BidVex n'a pas la possession, le titre ou les droits de propriété sur les articles mis en vente.</p>
              </div>
              
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold text-lg">2.2 Parties à la transaction</h3>
                <p>Toutes les ventes sont conclues directement entre l'acheteur et le vendeur. BidVex n'est pas partie à la transaction réelle entre les acheteurs et les vendeurs. Nous ne transférons pas la propriété légale des articles du vendeur à l'acheteur.</p>
              </div>
              
              <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <h3 className="font-semibold text-lg text-amber-800 dark:text-amber-200 mb-2">2.3 Avertissements de BidVex</h3>
                <p className="text-amber-700 dark:text-amber-300 mb-2">BidVex ne peut pas et ne fait pas ce qui suit :</p>
                <ul className="list-disc pl-6 space-y-1 text-amber-700 dark:text-amber-300">
                  <li>Inspecter, certifier, garantir ou vérifier l'état, la sécurité, la légalité, l'exactitude ou la qualité des articles mis en vente;</li>
                  <li>Gérer ou coordonner la livraison, le transport, l'entreposage ou la logistique des articles;</li>
                  <li>Fournir des garanties, expresses ou implicites, concernant les articles; ou</li>
                  <li>Accepter la responsabilité ou garantir la résolution des litiges entre acheteurs et vendeurs.</li>
                </ul>
              </div>
            </div>
          </section>

          {/* 3. Comptes d'utilisateur */}
          <section id="user-accounts">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">3</span>
              <Users className="h-5 w-5" /> Comptes d'utilisateur
            </h2>
            
            <div className="grid gap-4">
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">3.1 Inscription</h3>
                <p>Pour participer aux enchères, vous devez vous inscrire et maintenir un compte d'utilisateur.</p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">3.2 Responsabilités de l'utilisateur</h3>
                <p className="mb-2">En créant un compte, vous acceptez de :</p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Fournir des informations exactes, actuelles et complètes lors du processus d'inscription;</li>
                  <li>Maintenir la sécurité de votre compte en protégeant votre mot de passe et en limitant l'accès;</li>
                  <li>Assumer l'entière responsabilité de toutes les activités qui se produisent sous votre compte; et</li>
                  <li>Signaler immédiatement tout accès ou utilisation non autorisé de votre compte à BidVex.</li>
                </ul>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">3.3 Admissibilité</h3>
                <p>Vous devez avoir au moins <strong>dix-huit (18) ans</strong> et posséder la capacité juridique de conclure des contrats contraignants pour vous inscrire et utiliser la Plateforme.</p>
              </div>
            </div>
          </section>

          {/* 4. Responsabilités du vendeur */}
          <section id="seller">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-emerald-100 dark:bg-emerald-900 rounded-full flex items-center justify-center text-emerald-600 text-sm font-bold">4</span>
              <Building2 className="h-5 w-5 text-emerald-600" /> Responsabilités du vendeur
            </h2>
            
            <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg p-4 mb-4">
              <h3 className="font-semibold text-lg text-emerald-800 dark:text-emerald-200 mb-2">4.1 Engagements du vendeur</h3>
              <p className="text-emerald-700 dark:text-emerald-300 mb-2">Les vendeurs doivent respecter les obligations suivantes :</p>
              <ul className="list-disc pl-6 space-y-1 text-emerald-700 dark:text-emerald-300">
                <li>Fournir des descriptions, des spécifications et des images de haute qualité exactes, complètes et détaillées des articles mis en vente;</li>
                <li>Confirmer et garantir la propriété légale ou le droit légal spécifique de vendre les articles mis en vente;</li>
                <li>Divulguer entièrement tout défaut, privilège, charge ou restriction connu sur les articles;</li>
                <li>Se conformer à toutes les lois et réglementations applicables concernant la vente des articles;</li>
                <li>Compléter la vente d'un article avec l'enchérisseur gagnant en temps opportun; et</li>
                <li>Répondre rapidement et professionnellement aux demandes des acheteurs.</li>
              </ul>
            </div>
            
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <h3 className="font-semibold text-lg text-red-800 dark:text-red-200 mb-2 flex items-center gap-2">
                <Ban className="h-5 w-5" /> 4.2 Annonces interdites
              </h3>
              <p className="text-red-700 dark:text-red-300">
                Il est strictement interdit aux vendeurs de mettre en vente des articles illégaux, contrefaits, volés, dangereux, rappelés ou autrement restreints par la loi ou la politique de BidVex.
              </p>
            </div>
          </section>

          {/* 5. Responsabilités de l'acheteur */}
          <section id="buyer">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">5</span>
              Responsabilités de l'acheteur
            </h2>
            
            <div className="grid gap-4">
              <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h3 className="font-semibold text-lg text-blue-800 dark:text-blue-200 mb-2">5.1 Diligence raisonnable</h3>
                <p className="text-blue-700 dark:text-blue-300">
                  Les acheteurs reconnaissent qu'il est de leur seule responsabilité d'inspecter les articles, de poser des questions au vendeur ou d'organiser des inspections par des tiers avant de placer une enchère, au besoin.
                </p>
              </div>
              
              <div className="bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 rounded-lg p-4">
                <h3 className="font-semibold text-lg text-purple-800 dark:text-purple-200 mb-2 flex items-center gap-2">
                  <Gavel className="h-5 w-5" /> 5.2 Enchères juridiquement contraignantes
                </h3>
                <p className="text-purple-700 dark:text-purple-300">
                  En plaçant une enchère, vous faites une <strong>offre juridiquement contraignante</strong> d'acheter l'article si votre enchère est la plus élevée à la clôture de l'enchère, sous réserve de tout prix de réserve.
                </p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">5.3 Conclusion de la transaction</h3>
                <p>Si vous êtes l'enchérisseur gagnant, vous acceptez de compléter le paiement dans les délais spécifiés et d'organiser la livraison ou le ramassage de l'article directement avec le vendeur.</p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">5.4 Informations exactes</h3>
                <p>Les acheteurs doivent fournir des informations d'expédition et de contact exactes pour assurer une communication et une conclusion de transaction réussies.</p>
              </div>
            </div>
          </section>

          {/* 6. Règles d'enchères */}
          <section id="bidding">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">6</span>
              <Gavel className="h-5 w-5" /> Règles d'enchères
            </h2>
            
            <div className="grid gap-4">
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <CheckCircle className="h-6 w-6 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold">6.1 Enchères contraignantes</h3>
                  <p>Toutes les enchères placées sur la Plateforme constituent des obligations contractuelles juridiquement contraignantes.</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <XCircle className="h-6 w-6 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold">6.2 Rétractation d'enchère</h3>
                  <p>Les rétractations d'enchères ne sont pas autorisées, sauf dans des circonstances exceptionnelles et limitées, comme une erreur typographique importante, et uniquement si elles sont demandées dans l'heure <strong>(1) heure</strong> suivant le placement de l'enchère.</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <Shield className="h-6 w-6 text-blue-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold">6.3 Prix de réserve</h3>
                  <p>Les vendeurs peuvent fixer un « Prix de réserve » (le prix minimum confidentiel que le vendeur est prêt à accepter). L'article ne sera pas vendu si le Prix de réserve n'est pas atteint.</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
                <Clock className="h-6 w-6 text-blue-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-blue-800 dark:text-blue-200">6.4 Politique anti-sniping</h3>
                  <p className="text-blue-700 dark:text-blue-300">Si une enchère est placée dans les <strong>deux (2) dernières minutes</strong> de l'heure de fin prévue d'une enchère, la durée de l'enchère sera prolongée de deux (2) minutes supplémentaires. Cela garantit un processus d'enchères équitable.</p>
                </div>
              </div>
            </div>
          </section>

          {/* 7. Frais */}
          <section id="fees">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center text-green-600 text-sm font-bold">7</span>
              <DollarSign className="h-5 w-5 text-green-600" /> Frais, taxes et structure de paiement
            </h2>
            
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold text-lg mb-3">7.1 Niveaux d'utilisateur</h3>
                <p className="mb-3">Lors de l'inscription, les utilisateurs sont assignés à un niveau spécifique. Ce niveau détermine les frais d'encanteur et la commission du vendeur applicables.</p>
                
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse">
                    <thead>
                      <tr className="bg-slate-100 dark:bg-slate-800">
                        <th className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-left font-semibold">Niveau</th>
                        <th className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center font-semibold">Frais d'encanteur</th>
                        <th className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center font-semibold">Commission du vendeur</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="bg-slate-50 dark:bg-slate-800/50">
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 font-medium">Standard</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center">5,0 %</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center">4,0 %</td>
                      </tr>
                      <tr className="bg-blue-50 dark:bg-blue-950/30">
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 font-medium text-blue-700 dark:text-blue-300">Premium</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center text-blue-700 dark:text-blue-300">3,5 %</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center text-blue-700 dark:text-blue-300">2,5 %</td>
                      </tr>
                      <tr className="bg-amber-50 dark:bg-amber-950/30">
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 font-medium text-amber-700 dark:text-amber-300">VIP Élite</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center text-amber-700 dark:text-amber-300">3,0 %</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center text-amber-700 dark:text-amber-300">2,0 %</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">7.2 Frais supplémentaires</h3>
                <p>Des <strong>frais de plateforme obligatoires de 2,5 %</strong> sont appliqués à toutes les transactions complétées pour les véhicules uniquement.</p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">7.3 Taxes</h3>
                <p>Les taxes (y compris la TPS, la TVP, la TVH et la TVQ, selon le cas) sont ajoutées à la facture finale. Les calculs de taxes sont basés sur le prix de vente final et la juridiction de la transaction.</p>
              </div>
              
              <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2 text-amber-800 dark:text-amber-200">7.4 Conditions de paiement</h3>
                <p className="text-amber-700 dark:text-amber-300 mb-2">Le paiement complet pour toutes les enchères gagnantes est dû dans les <strong>quatorze (14) jours</strong> suivant la clôture de l'enchère.</p>
                <p className="text-amber-700 dark:text-amber-300"><strong>Paiements en retard :</strong> Les paiements non reçus à la date d'échéance peuvent entraîner une pénalité de retard de <strong>2 % par mois</strong> (24 % par an) sur le solde impayé.</p>
              </div>
              
              <div className="flex items-start gap-3 p-4 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg">
                <CreditCard className="h-6 w-6 text-green-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-green-800 dark:text-green-200">7.5 Traitement des paiements</h3>
                  <p className="text-green-700 dark:text-green-300">Tous les paiements sont traités via <strong>Stripe</strong>, un processeur de paiement tiers sécurisé. BidVex ne stocke, ne possède ni n'a accès à aucune information complète de carte de crédit ou de compte bancaire.</p>
                </div>
              </div>
            </div>
          </section>

          {/* 8. Clause TEL QUEL */}
          <section id="as-is">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center text-red-600 text-sm font-bold">8</span>
              <AlertTriangle className="h-5 w-5 text-red-600" /> Clause « TEL QUEL / LÀ OÙ IL SE TROUVE »
            </h2>
            
            <div className="bg-red-50 dark:bg-red-950/30 border-2 border-red-300 dark:border-red-700 rounded-lg p-6">
              <p className="text-red-800 dark:text-red-200 font-medium uppercase text-sm leading-relaxed">
                VOUS ACCEPTEZ EXPRESSÉMENT QUE TOUS LES ARTICLES MIS EN VENTE SUR LA PLATEFORME SONT VENDUS « TEL QUEL, LÀ OÙ ILS SE TROUVENT », AVEC TOUS LES DÉFAUTS ET SANS AUCUNE GARANTIE DE QUELQUE NATURE QUE CE SOIT, EXPRESSE OU IMPLICITE, Y COMPRIS TOUTE GARANTIE DE QUALITÉ MARCHANDE OU D'ADÉQUATION À UN USAGE PARTICULIER. BIDVEX N'EST PAS RESPONSABLE DE L'ÉTAT, DE LA SÉCURITÉ, DE LA LÉGALITÉ OU DE L'EXACTITUDE DE TOUT ARTICLE OU DE TOUT LITIGE ENTRE UTILISATEURS.
              </p>
            </div>
          </section>

          {/* 9. Litiges */}
          <section id="disputes">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">9</span>
              <Scale className="h-5 w-5" /> Résolution des litiges
            </h2>
            
            <div className="space-y-4">
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold">9.1 Résolution directe</h3>
                <p>En cas de litige entre un acheteur et un vendeur, les parties conviennent de tenter d'abord de résoudre le problème directement et de bonne foi.</p>
              </div>
              
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold">9.2 Médiation par le support</h3>
                <p>Si les parties ne parviennent pas à résoudre le litige, elles peuvent contacter le support BidVex dans les <strong>sept (7) jours</strong> suivant la clôture de la transaction. BidVex peut, à sa seule discrétion, tenter de médier le litige, mais BidVex n'est pas obligé de le faire.</p>
              </div>
              
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold">9.3 Remboursements</h3>
                <p>Les remboursements, retours ou ajustements sont à la seule discrétion du vendeur, sauf si BidVex détermine qu'un article a été significativement mal représenté dans l'annonce.</p>
              </div>
            </div>
          </section>

          {/* 10. Propriété intellectuelle */}
          <section id="ip">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">10</span>
              Propriété intellectuelle
            </h2>
            
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 mb-4">
              <h3 className="font-semibold mb-2">10.1 Propriété</h3>
              <p>Tout le contenu et les matériaux sur la Plateforme, y compris le logo BidVex, le texte, les graphiques, les images, les vidéos, le code et les logiciels sont la propriété de BidVex Inc. ou de ses concédants de licence et sont protégés par le droit d'auteur, les marques de commerce et d'autres lois sur la propriété intellectuelle.</p>
            </div>
            
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
              <h3 className="font-semibold mb-2">10.2 Restrictions d'utilisation</h3>
              <ul className="list-disc pl-6 space-y-1">
                <li>Il est interdit aux utilisateurs de copier, reproduire, modifier, distribuer ou vendre tout contenu sans autorisation écrite préalable.</li>
                <li>L'utilisation de nos marques de commerce, logos ou image de marque sans autorisation expresse est interdite.</li>
                <li>Vous n'êtes pas autorisé à utiliser le « scraping », l'« exploration de données » ou des agents automatisés pour collecter des informations de la Plateforme.</li>
              </ul>
            </div>
          </section>

          {/* 11. Conduites interdites */}
          <section id="prohibited">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center text-red-600 text-sm font-bold">11</span>
              <Ban className="h-5 w-5 text-red-600" /> Conduites interdites
            </h2>
            
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <p className="text-red-800 dark:text-red-200 mb-3">Il est strictement interdit aux utilisateurs de s'engager dans les conduites suivantes :</p>
              <ul className="list-disc pl-6 space-y-1 text-red-700 dark:text-red-300">
                <li>S'engager dans la fraude, les enchères fictives ou toute forme de manipulation ou d'inflation artificielle des enchères;</li>
                <li>Harceler, menacer ou frauder d'autres utilisateurs ou employés de BidVex;</li>
                <li>Publier du pourriel, des virus ou du code malveillant qui pourrait nuire à la Plateforme ou aux utilisateurs;</li>
                <li>Contourner les frais de BidVex ou manipuler le processus d'enchères;</li>
                <li>Créer plusieurs comptes pour contourner les restrictions ou manipuler les enchères; ou</li>
                <li>S'engager dans toute conduite qui viole les lois ou réglementations applicables.</li>
              </ul>
              <p className="mt-3 text-red-800 dark:text-red-200 font-semibold">
                Les violations de cette section peuvent entraîner la suspension ou la résiliation immédiate de votre compte et peuvent entraîner des poursuites judiciaires.
              </p>
            </div>
          </section>

          {/* 12. Limitation de responsabilité */}
          <section id="liability">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">12</span>
              Limitation de responsabilité
            </h2>
            
            <div className="bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-lg p-4">
              <p className="text-sm uppercase leading-relaxed mb-3">
                DANS TOUTE LA MESURE PERMISE PAR LA LOI, BIDVEX FOURNIT LA PLATEFORME « TEL QUEL » ET « TEL QUE DISPONIBLE ». BIDVEX NE SERA PAS RESPONSABLE DE :
              </p>
              <ul className="list-disc pl-6 space-y-1 text-sm">
                <li>L'EXACTITUDE, L'EXHAUSTIVITÉ OU LA FIABILITÉ DES DESCRIPTIONS D'ARTICLES;</li>
                <li>LES ACTIONS, OMISSIONS OU CONDUITES DES ACHETEURS OU DES VENDEURS;</li>
                <li>TOUTE PERTE, DOMMAGE OU PRÉJUDICE DÉCOULANT DE TEMPS D'ARRÊT, D'ERREURS OU D'INTERRUPTIONS TECHNIQUES; OU</li>
                <li>TOUT DOMMAGE DIRECT, INDIRECT, ACCESSOIRE, CONSÉCUTIF, SPÉCIAL OU PUNITIF.</li>
              </ul>
              <p className="mt-3 text-sm font-semibold">
                NOTRE RESPONSABILITÉ GLOBALE MAXIMALE NE DÉPASSERA PAS LE TOTAL DES FRAIS QUE VOUS AVEZ PAYÉS À BIDVEX AU COURS DES DOUZE (12) MOIS PRÉCÉDANT LA RÉCLAMATION.
              </p>
            </div>
          </section>

          {/* 13. Résiliation */}
          <section id="termination">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">13</span>
              Suspension et résiliation
            </h2>
            
            <div className="grid gap-4">
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold mb-2">13.1 Droit de BidVex</h3>
                <p>BidVex se réserve le droit, à sa seule discrétion, de suspendre, de résilier ou de restreindre votre compte et votre accès à la Plateforme si vous violez ces Conditions ou si vous vous engagez dans une conduite préjudiciable à BidVex ou à ses utilisateurs.</p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold mb-2">13.2 Fermeture de compte par l'utilisateur</h3>
                <p>Vous pouvez fermer votre compte BidVex à tout moment. Cependant, la fermeture de votre compte ne vous libère pas des obligations en cours, y compris les enchères juridiquement contraignantes et les exigences de paiement.</p>
              </div>
            </div>
          </section>

          {/* 14. Modifications */}
          <section id="changes">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">14</span>
              Modifications des conditions générales
            </h2>
            <p>BidVex se réserve le droit de mettre à jour ou de modifier ces Conditions à tout moment. Les changements importants seront communiqués aux utilisateurs inscrits par courriel et par notifications sur la plateforme. Votre utilisation continue de la Plateforme après la date d'entrée en vigueur de tout changement constitue votre acceptation des nouvelles Conditions.</p>
          </section>

          {/* 15. Droit applicable */}
          <section id="governing">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">15</span>
              <Scale className="h-5 w-5" /> Droit applicable et juridiction
            </h2>
            <p>Les présentes Conditions et votre utilisation de la Plateforme sont régies et interprétées conformément aux lois de la <strong>province de Québec</strong> et aux lois fédérales du Canada qui s'y appliquent. Tout litige découlant de ces Conditions ou s'y rapportant sera résolu exclusivement devant les tribunaux de <strong>Montréal, Québec</strong>.</p>
          </section>

          {/* 16. Coordonnées */}
          <section id="contact" className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">16</span>
              Coordonnées
            </h2>
            <p className="font-semibold text-lg mb-4">BidVex — Service juridique et responsable de la protection des données</p>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Mail className="h-5 w-5 text-blue-600" />
                <span><strong>Courriel :</strong> support@bidvex.com</span>
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

export default TermsFR;
