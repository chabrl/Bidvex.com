import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldAlert, LogOut } from 'lucide-react';

export const IMPERSONATION_KEY = 'bidvex_impersonation';
export const ADMIN_BACKUP_TOKEN_KEY = 'bidvex_admin_backup_token';
export const ADMIN_BACKUP_REFRESH_KEY = 'bidvex_admin_backup_refresh';

export const exitImpersonation = () => {
  const adminTok = localStorage.getItem(ADMIN_BACKUP_TOKEN_KEY);
  const adminRefresh = localStorage.getItem(ADMIN_BACKUP_REFRESH_KEY);
  if (adminTok) localStorage.setItem('token', adminTok);
  if (adminRefresh) localStorage.setItem('refresh_token', adminRefresh);
  localStorage.removeItem(ADMIN_BACKUP_TOKEN_KEY);
  localStorage.removeItem(ADMIN_BACKUP_REFRESH_KEY);
  localStorage.removeItem(IMPERSONATION_KEY);
  window.location.href = '/admin';
};

const ImpersonationBanner = () => {
  const { i18n } = useTranslation();
  const [info, setInfo] = useState(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(IMPERSONATION_KEY);
      if (raw) setInfo(JSON.parse(raw));
    } catch (_) { /* corrupt entry — ignore */ }
  }, []);

  if (!info) return null;
  const fr = (i18n.language || 'en').startsWith('fr');
  const who = info.target_name || info.target_email || 'user';

  return (
    <div
      data-testid="impersonation-banner"
      className="sticky top-0 z-[100] flex flex-wrap items-center justify-center gap-3 bg-red-600 px-4 py-2 text-white shadow-lg"
    >
      <ShieldAlert className="h-4 w-4 shrink-0" />
      <span className="text-sm font-semibold" data-testid="impersonation-banner-text">
        {fr
          ? `MODE ADMIN — Vous êtes connecté en tant que ${who} (${info.target_email}). Toutes les actions sont journalisées.`
          : `ADMIN MODE — You are logged in as ${who} (${info.target_email}). All actions are logged.`}
      </span>
      <button
        onClick={exitImpersonation}
        data-testid="exit-impersonation-btn"
        className="flex items-center gap-1 rounded-full bg-white px-3 py-1 text-xs font-bold text-red-700 transition-opacity hover:opacity-85"
      >
        <LogOut className="h-3 w-3" />
        {fr ? "Quitter l'usurpation" : 'Exit impersonation'}
      </button>
    </div>
  );
};

export default ImpersonationBanner;
