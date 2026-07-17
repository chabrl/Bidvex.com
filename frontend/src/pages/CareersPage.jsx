/**
 * iter318 — BidVex Careers public page (/careers).
 *
 * Always-bilingual (EN + FR simultaneous per Bill 96). Pulls live job
 * list from GET /api/careers/jobs and renders a hero + grid of openings.
 *
 * Clicking a job card opens the detail-and-apply page at
 * /careers/:job_id (CareersJobDetailPage.jsx).
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';

import { Loader2, Briefcase, MapPin, DollarSign, ArrowRight } from 'lucide-react';

import API_BASE from '../config';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { LangLink } from '../components/LangLink';

export default function CareersPage() {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/careers/jobs`);
        if (!cancelled) setJobs(r.data?.items || []);
      } catch (e) {
        if (!cancelled) {
          setError(e?.response?.data?.detail || e?.message);
          setJobs([]);
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="bg-white" data-testid="careers-page">
      {/* ─── Hero ─── */}
      <section className="bg-slate-900 py-20 px-4 text-center" data-testid="careers-hero">
        <div className="max-w-3xl mx-auto">
          <div className="text-sky-400 text-sm font-bold uppercase tracking-widest mb-4">
            BidVex Careers / Carrières BidVex
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-white mb-3">
            Work With the Future of Liquidation
          </h1>
          <h2 className="text-2xl sm:text-3xl font-bold text-sky-300 mb-6">
            Travaillez avec l&apos;avenir de la liquidation
          </h2>
          <p className="text-gray-300 text-lg max-w-2xl mx-auto mb-2">
            Independent contractor roles for appraisers, auctioneers, and liquidators
            across Canada. Earn 5% to 20% commission on every transaction you bring
            to the platform.
          </p>
          <p className="text-gray-400 text-base max-w-2xl mx-auto mb-10 italic">
            Rôles de contractant indépendant pour évaluateurs, encanteurs et
            liquidateurs partout au Canada.
          </p>
          <a
            href="#openings"
            className="inline-flex items-center gap-2 bg-sky-500 hover:bg-sky-400 text-white font-bold py-4 px-10 rounded-xl text-lg transition-colors"
            data-testid="hero-cta-openings"
          >
            View Open Positions / Voir les postes <ArrowRight className="h-5 w-5" />
          </a>
        </div>
      </section>

      {/* ─── Openings grid ─── */}
      <section id="openings" className="max-w-6xl mx-auto py-16 px-4" data-testid="openings-section">
        <header className="mb-8">
          <h2 className="text-3xl font-bold text-slate-900">Open Positions</h2>
          <h3 className="text-lg font-semibold text-slate-600">Postes ouverts</h3>
        </header>

        {jobs === null && (
          <div className="flex justify-center py-16" data-testid="openings-loading">
            <Loader2 className="h-8 w-8 animate-spin text-sky-600" />
          </div>
        )}

        {jobs !== null && jobs.length === 0 && !error && (
          <Card className="border-2 border-dashed border-slate-200" data-testid="openings-empty">
            <CardContent className="p-12 text-center">
              <Briefcase className="h-12 w-12 mx-auto text-slate-300 mb-4" />
              <p className="text-lg text-slate-700">
                No openings at this time. Check back soon.
              </p>
              <p className="text-base text-slate-500 italic mt-1">
                Aucun poste disponible pour le moment.
              </p>
            </CardContent>
          </Card>
        )}

        {error && (
          <Card className="border-2 border-rose-200 bg-rose-50" data-testid="openings-error">
            <CardContent className="p-6 text-rose-800">
              {typeof error === 'string' ? error : 'Unable to load openings.'}
            </CardContent>
          </Card>
        )}

        {jobs && jobs.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5" data-testid="openings-grid">
            {jobs.map((job) => (
              <LangLink
                to={`/careers/${job.id}`}
                key={job.id}
                className="block"
                data-testid={`job-card-${job.id}`}
              >
                <Card className="hover:border-sky-400 hover:shadow-lg transition-all h-full">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="min-w-0">
                        <h3 className="text-lg font-bold text-slate-900" data-testid="job-card-title">
                          {job.title}
                        </h3>
                        {job.title_fr && (
                          <p className="text-sm text-slate-500 italic mt-0.5" data-testid="job-card-title-fr">
                            {job.title_fr}
                          </p>
                        )}
                      </div>
                      <Badge className="bg-sky-100 text-sky-800 hover:bg-sky-100 shrink-0">
                        {job.department || 'Operations'}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600 mt-3">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3.5 w-3.5" />
                        {job.location || 'National'}
                      </span>
                      {job.commission_range && (
                        <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                          <DollarSign className="h-3.5 w-3.5" />
                          {job.commission_range}
                        </span>
                      )}
                    </div>
                    <div className="mt-5">
                      <Button
                        variant="outline"
                        className="w-full justify-between border-sky-300 hover:bg-sky-50"
                        data-testid="job-card-cta"
                      >
                        <span>View &amp; Apply / Voir et postuler</span>
                        <ArrowRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </LangLink>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
