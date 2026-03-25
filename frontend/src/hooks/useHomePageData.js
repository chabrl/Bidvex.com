import API_BASE from '../config';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

const API = API_BASE;

const fetcher = (url) => axios.get(url).then((r) => r.data);

export const useTopSellers = (limit = 8) =>
  useQuery({
    queryKey: ['top-sellers', limit],
    queryFn: () => fetcher(`${API}/stats/top-sellers?limit=${limit}`),
    staleTime: 60 * 1000,
  });

export const useHotItems = (limit = 6) =>
  useQuery({
    queryKey: ['hot-items', limit],
    queryFn: () => fetcher(`${API}/stats/hot-items?limit=${limit}`),
    staleTime: 60 * 1000,
  });

export const useEndingSoon = (limit = 12) =>
  useQuery({
    queryKey: ['ending-soon', limit],
    queryFn: () => fetcher(`${API}/carousel/ending-soon?limit=${limit}`),
    staleTime: 30 * 1000,
  });

export const useFeatured = (limit = 12) =>
  useQuery({
    queryKey: ['featured', limit],
    queryFn: () => fetcher(`${API}/carousel/featured?limit=${limit}`),
    staleTime: 60 * 1000,
  });

export const useNewListings = (limit = 12) =>
  useQuery({
    queryKey: ['new-listings', limit],
    queryFn: () => fetcher(`${API}/carousel/new-listings?limit=${limit}`),
    staleTime: 60 * 1000,
  });

export const useRecentlySold = (limit = 12) =>
  useQuery({
    queryKey: ['recently-sold', limit],
    queryFn: () => fetcher(`${API}/carousel/recently-sold?limit=${limit}`),
    staleTime: 60 * 1000,
  });
