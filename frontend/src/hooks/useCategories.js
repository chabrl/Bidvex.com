import API_BASE from '../config';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

const API = `${API_BASE}/api`;

const fetchCategories = async () => {
  const { data } = await axios.get(`${API}/categories`);
  return data;
};

export const useCategories = () => {
  return useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
};
