# BidVex — Auction Marketplace PRD

## Latest: FilterBar Rebuild (April 20, 2026)

### Marketplace Filter Bar — Full Responsive Rebuild - DONE
- Created `FilterBar/FilterBar.js` component with 4 toggle pills (Private Sales, 0% Buyer Fee, Lots Auction, No Taxes) + search + 4 dropdowns (Province, Category, Condition, Sort)
- Desktop: all elements in one wrapping row, no horizontal overflow
- Mobile (<768px): collapsed panel with Filters toggle button, 2-column dropdown grid
- Dark mode support via `.dark` CSS selectors
- Bilingual EN/FR via i18n
- `pageContext="lots"` hides Lots Auction pill and pre-activates it
- Wired into both `/items` (FlattenedMarketplace) and `/lots` (LotsMarketplacePage)
- Backend: added `province`, `no_taxes`, `most_bids` sort to marketplace API

## Backlog
- (P2) Post-launch monitoring & alerting
- (Enhancement) Dispute resolution workflow
