import API_BASE from '../config';
import { useInfiniteQuery } from '@tanstack/react-query';
import axios from 'axios';

const API = API_BASE;

const fetchMarketplaceItems = async ({ pageParam, filters, limit }) => {
  const params = new URLSearchParams();

  if (filters.search) params.append('search', filters.search);
  if (filters.category) params.append('category', filters.category);
  if (filters.min_price) params.append('min_price', filters.min_price);
  if (filters.max_price) params.append('max_price', filters.max_price);
  if (filters.condition) params.append('condition', filters.condition);
  params.append('sort', filters.sort || '-promoted');
  params.append('limit', String(limit));
  params.append('track_impression', 'true');
  if (pageParam) params.append('cursor', pageParam);

  const { data } = await axios.get(`${API}/marketplace/items?${params.toString()}`, {
    timeout: 15000,
  });

  // If cache is still warming, retry after 2 seconds
  if (data.cache_warming) {
    await new Promise(r => setTimeout(r, 2000));
    const { data: retryData } = await axios.get(`${API}/marketplace/items?${params.toString()}`, {
      timeout: 15000,
    });
    return retryData;
  }

  return data;
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
