import API_BASE from '../config';
import { useInfiniteQuery } from '@tanstack/react-query';
import axios from 'axios';

const API = API_BASE;

const fetchMarketplaceItems = async ({ pageParam, filters, limit }) => {
  const params = new URLSearchParams();

  if (filters.search) params.append('search', filters.search);
  if (filters.category) params.append('category', filters.category);
  if (filters.categories) params.append('categories', filters.categories);
  if (filters.regions) params.append('regions', filters.regions);
  // iter217 Phase 4 — Province (single) from FilterBar top dropdown
  if (filters.province) params.append('province', filters.province);
  if (filters.cities) params.append('cities', filters.cities);
  if (filters.seller_id) params.append('seller_id', filters.seller_id);
  if (filters.min_price) params.append('min_price', filters.min_price);
  if (filters.max_price) params.append('max_price', filters.max_price);
  if (filters.condition) params.append('condition', filters.condition);
  if (filters.zero_fee_only === 'true' || filters.zero_fee_only === true) params.append('zero_fee_only', 'true');
  // iter217 Phase 4 — Top-bar pill filters
  if (filters.private_sales_only) params.append('private_sales_only', 'true');
  if (filters.partner_only) params.append('partner_only', 'true');
  if (filters.lots_auction) params.append('lots_auction_only', 'true');
  if (filters.no_taxes) params.append('no_taxes', 'true');
  if (filters.tax_status) params.append('tax_status', filters.tax_status);
  if (filters.buyer_province) params.append('buyer_province', filters.buyer_province);
  params.append('sort', filters.sort || 'nearby_first');
  params.append('limit', String(limit));
  params.append('track_impression', 'true');
  if (pageParam) params.append('cursor', pageParam);

  const { data } = await axios.get(`${API}/marketplace/items?${params.toString()}`, {
    timeout: 15000,
  });

  // iter220 Task 1 — Hydration Ghost Fix (FE side).
  // If the backend reports the cache is still warming, retry with exponential
  // backoff up to 3 times (1s → 2s → 4s). The previous single-retry version
  // could return empty data when the cache took longer than 2s to build —
  // leaving the buyer staring at "No items found" even when 5+ listings existed
  // (the filter-counts endpoint hits a different cache so it would correctly
  // report 5). This loop matches the new backend behaviour that inline-builds
  // the cache when cold; warming is now only seen during very heavy load.
  let attempt = 0;
  let resp = data;
  while (resp?.cache_warming && attempt < 3) {
    await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, attempt)));
    const { data: retryData } = await axios.get(`${API}/marketplace/items?${params.toString()}`, {
      timeout: 15000,
    });
    resp = retryData;
    attempt += 1;
  }
  return resp;
};

export const useMarketplaceItems = (filters, limit = 24) => {
  return useInfiniteQuery({
    queryKey: ['marketplace-items', filters, limit],
    queryFn: ({ pageParam }) => fetchMarketplaceItems({ pageParam, filters, limit }),
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.next_cursor : undefined,
    initialPageParam: undefined,
    staleTime: 30 * 1000,
  });
};
