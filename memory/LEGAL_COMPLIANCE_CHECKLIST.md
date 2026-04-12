# BidVex Legal Compliance Checklist — April 12, 2026

## SECTION 1: Vehicle Auctions — OPC Intermediary Model

| # | Item | File(s) | EN | FR | Status |
|---|------|---------|----|----|--------|
| 1.1 | OPC permit fields in user schema | `backend/routes/auth.py` | N/A | N/A | DONE |
| 1.1 | Vehicle listing OPC gate (403) | `backend/routes/listings.py:154` | Bilingual error | Bilingual error | DONE |
| 1.1 | Admin OPC verification endpoint | `backend/routes/admin_ops.py:1015+` | N/A | N/A | DONE |
| 1.1 | Audit log for blocked attempts | `backend/routes/listings.py:164` | N/A | N/A | DONE |
| 1.2 | Vehicle Seller page bilingual header | `frontend/src/pages/vehicles/SellerRegistrationPage.js` | DONE | DONE | DONE |
| 1.2 | Non-dismissible disclaimer box | `frontend/src/pages/vehicles/SellerRegistrationPage.js` | DONE | DONE | DONE |
| 1.2 | OPC permit field with bilingual helper | `frontend/src/pages/vehicles/SellerRegistrationPage.js` | DONE | DONE | DONE |
| 1.3 | Vehicle payment flow (2.5% fee) | — | — | — | BACKLOG |
| 1.4 | Privacy Policy: Vehicle Auctions section | `frontend/src/pages/LegalPage.js`, `frontend/src/components/legal/PrivacyEN.jsx` | DONE | DONE | DONE |
| 1.4 | Terms: Vehicle Auctions section | `frontend/src/pages/LegalPage.js`, `frontend/src/components/legal/TermsEN.jsx` | DONE | DONE | DONE |

## SECTION 2: Law 25 — AI Disclosure

| # | Item | File(s) | EN | FR | Status |
|---|------|---------|----|----|--------|
| 2.1 | AI disclosure checkbox (registration) | `frontend/src/pages/AuthPage.js` | DONE | DONE | DONE |
| 2.1 | Backend validation of ai_disclosure_consent | `backend/routes/auth.py:154`, `backend/shared.py:293` | Bilingual error | Bilingual error | DONE |
| 2.1 | Store ai_consent_timestamp + ai_consent_ip | `backend/routes/auth.py:229` | N/A | N/A | DONE |
| 2.2 | Privacy Policy: AI section | `frontend/src/pages/LegalPage.js`, `frontend/src/components/legal/LegalComplianceSections.js` | DONE | DONE | DONE |

## SECTION 3: Cross-Border Compliance

| # | Item | File(s) | EN | FR | Status |
|---|------|---------|----|----|--------|
| 3 | Terms: Cross-Border section | `frontend/src/pages/LegalPage.js`, `frontend/src/components/legal/LegalComplianceSections.js` | DONE | DONE | DONE |
| 3 | CBSA, RIV, CFIA, CBP, SAAQ, RDPRM listed | `LegalComplianceSections.js:CrossBorderLegalSection` | DONE | DONE | DONE |

## SECTION 4: CFIA Soil Rule Banner

| # | Item | File(s) | EN | FR | Status |
|---|------|---------|----|----|--------|
| 4 | CFIASoilBanner component | `frontend/src/components/legal/LegalComplianceSections.js` | DONE | DONE | DONE |
| 4 | CFIASoilCheckbox component | `frontend/src/components/legal/LegalComplianceSections.js` | DONE | DONE | DONE |
| 4 | Trigger on heavy equipment categories | `frontend/src/pages/CreateListingPage.js:24` | EN+FR cats | EN+FR cats | DONE |
| 4 | cfia_soil_declaration DB field | `backend/models/auction_models.py:46` | N/A | N/A | DONE |

## SECTION 5: Cross-Border Advisory

| # | Item | File(s) | EN | FR | Status |
|---|------|---------|----|----|--------|
| 5 | CrossBorderAdvisoryPanel component | `frontend/src/components/legal/LegalComplianceSections.js` | DONE | DONE | DONE |
| 5 | CrossBorderBidModal component | `frontend/src/components/legal/LegalComplianceSections.js` | DONE | DONE | DONE |
| 5 | cross_border_disclosure_accepted field | `backend/models/auction_models.py:92` | N/A | N/A | DONE |
| 5 | Wire modal into bid flow | — | — | — | BACKLOG |

## SECTION 6: Intermediary Language Audit

| # | Item | File(s) | EN | FR | Status |
|---|------|---------|----|----|--------|
| 6.1 | Global find & replace scan | All .js/.jsx/.py/.html | N/A | N/A | DONE (no violations found) |
| 6.2 | Dealer Onboarding Agreement checkbox | `frontend/src/pages/vehicles/SellerRegistrationPage.js` | DONE | DONE | DONE |

## MODIFIED FILES

| File | Changes |
|------|---------|
| `backend/shared.py` | Added `ai_disclosure_consent` to `UserCreate` |
| `backend/routes/auth.py` | AI consent validation + storage in registration |
| `backend/routes/listings.py` | OPC verification gate for vehicle categories |
| `backend/routes/admin_ops.py` | Added OPC verification admin endpoint |
| `backend/models/auction_models.py` | Added `cfia_soil_declaration`, `cross_border_disclosure_accepted` |
| `frontend/src/pages/AuthPage.js` | AI disclosure checkbox (bilingual) |
| `frontend/src/pages/LegalPage.js` | Injected all 3 bilingual legal sections |
| `frontend/src/components/legal/LegalComplianceSections.js` | NEW — all bilingual legal components |
| `frontend/src/components/legal/PrivacyEN.jsx` | Added AI + Vehicle sections |
| `frontend/src/components/legal/PrivacyFR.jsx` | Added AI + Vehicle sections |
| `frontend/src/components/legal/TermsEN.jsx` | Added Cross-Border + Vehicle sections |
| `frontend/src/components/legal/TermsFR.jsx` | Added Cross-Border + Vehicle sections |
| `frontend/src/pages/vehicles/SellerRegistrationPage.js` | Full bilingual rewrite |
| `frontend/src/pages/CreateListingPage.js` | CFIA banner + checkbox |
