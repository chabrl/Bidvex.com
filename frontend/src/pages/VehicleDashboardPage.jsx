/**
 * iter413 — Vehicle Dashboard.
 * iter428 — My Vehicles module lit up as the first active section.
 *
 * Sections rendered:
 *   1. Breadcrumb + bilingual heading
 *   2. My Vehicles (ACTIVE) — <MyVehiclesModule />
 *   3. Coming soon strip — Sales & Performance / Settlements
 *      placeholders (deferred per PRD).
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Car, TrendingUp, Wallet } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from '../components/ui/breadcrumb';
import SEO from '../components/SEO';
import MyVehiclesModule from '../components/vehicles/MyVehiclesModule';
import SalesPerformanceModule from '../components/vehicles/SalesPerformanceModule';
import SettlementsModule from '../components/vehicles/SettlementsModule';

const VehicleDashboardPage = () => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').startsWith('fr');

  const T = {
    seoTitle:  isFr ? 'Tableau de bord Véhicules' : 'Vehicle Dashboard',
    seoDesc:   isFr
      ? "Votre tableau de bord pour les enchères, ventes et paiements de véhicules sur BidVex."
      : "Your hub for BidVex vehicle listings, sales, settlements, and payouts.",
    crumbHome: isFr ? 'Accueil' : 'Home',
    heading:   isFr ? 'Tableau de bord Véhicules' : 'Vehicle Dashboard',
    subheading: isFr
      ? "Gérez vos annonces de véhicules — modifiez, dupliquez ou retirez en un clic."
      : 'Manage your vehicle listings — edit, duplicate, or retire in a single click.',
    myVehiclesTitle: isFr ? 'Mes véhicules' : 'My Vehicles',
    myVehiclesDesc:  isFr
      ? 'Toutes vos annonces de véhicules, filtrables par statut.'
      : 'Every vehicle you have listed, filterable by status.',
    salesTitle: isFr ? 'Ventes et performance' : 'Sales & Performance',
    salesDesc:  isFr
      ? 'Vues, enchères, revenus et taux de conversion sur 30 / 60 / 90 jours.'
      : 'Views, bids, revenue, and conversion rate over the last 30 / 60 / 90 days.',
    settlementsTitle: isFr ? 'Règlements' : 'Settlements',
    settlementsDesc:  isFr
      ? "Enchères gagnées, prime d'acheteur et statut de paiement."
      : 'Won auctions, buyer premium, and payout status.',
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="vehicle-dashboard-page">
      <SEO title={T.seoTitle} description={T.seoDesc} path="/vehicle-dashboard" noindex />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb */}
        <Breadcrumb className="mb-6" data-testid="vehicle-dashboard-breadcrumb">
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink href="/">{T.crumbHome}</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{T.heading}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>

        {/* Heading */}
        <header className="mb-8 flex items-start gap-4">
          <div className="rounded-2xl p-3 bg-gradient-to-br from-blue-500 to-indigo-600 shadow-md">
            <Car className="h-8 w-8 text-white" />
          </div>
          <div>
            <h1
              className="text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-tight"
              data-testid="vehicle-dashboard-heading"
            >
              {T.heading}
            </h1>
            <p className="mt-1 text-slate-600 dark:text-slate-400">{T.subheading}</p>
          </div>
        </header>

        {/* Active module: My Vehicles */}
        <Card
          className="mb-8 border-blue-200/60 bg-gradient-to-br from-white to-blue-50/50 dark:from-slate-900 dark:to-slate-900/50 dark:border-slate-800"
          data-testid="vehicle-dashboard-my-vehicles-card"
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Car className="h-5 w-5 text-blue-600" />
              {T.myVehiclesTitle}
            </CardTitle>
            <p className="text-sm text-slate-500 dark:text-slate-400 pt-1">{T.myVehiclesDesc}</p>
          </CardHeader>
          <CardContent>
            <MyVehiclesModule />
          </CardContent>
        </Card>

        {/* iter432 — Sales & Performance module */}
        <Card
          className="mb-8 border-emerald-200/60 bg-gradient-to-br from-white to-emerald-50/40 dark:from-slate-900 dark:to-slate-900/50 dark:border-slate-800"
          data-testid="vehicle-dashboard-sales-performance-card"
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <TrendingUp className="h-5 w-5 text-emerald-600" />
              {T.salesTitle}
            </CardTitle>
            <p className="text-sm text-slate-500 dark:text-slate-400 pt-1">{T.salesDesc}</p>
          </CardHeader>
          <CardContent>
            <SalesPerformanceModule />
          </CardContent>
        </Card>

        {/* iter437 — Settlements module */}
        <Card
          className="mb-8 border-purple-200/60 bg-gradient-to-br from-white to-purple-50/40 dark:from-slate-900 dark:to-slate-900/50 dark:border-slate-800"
          data-testid="vehicle-dashboard-settlements-card"
        >
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Wallet className="h-5 w-5 text-purple-600" />
              {T.settlementsTitle}
            </CardTitle>
            <p className="text-sm text-slate-500 dark:text-slate-400 pt-1">{T.settlementsDesc}</p>
          </CardHeader>
          <CardContent>
            <SettlementsModule />
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default VehicleDashboardPage;
