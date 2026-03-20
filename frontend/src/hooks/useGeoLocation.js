import { useState, useEffect } from 'react';

const STORAGE_KEY = 'bidvex_geo_location';
const GEO_API_URL = 'https://ip-api.com/json/?fields=status,country,countryCode,region,regionName,city';

/**
 * useGeoLocation — Non-blocking IP-based location detection hook.
 * Returns { country, region, city, loading } based on the user's IP.
 * Caches result in sessionStorage to avoid repeat API calls.
 * Falls back gracefully on error (returns empty strings).
 */
const useGeoLocation = () => {
  const [geo, setGeo] = useState({ country: '', region: '', city: '', loading: true });

  useEffect(() => {
    // Check session cache first
    const cached = sessionStorage.getItem(STORAGE_KEY);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        setGeo({ ...parsed, loading: false });
        return;
      } catch {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    fetch(GEO_API_URL, { signal: controller.signal })
      .then(res => res.json())
      .then(data => {
        clearTimeout(timeout);
        if (data.status === 'success') {
          // Map ip-api country codes to our location data keys
          const countryCode = data.countryCode === 'CA' ? 'CA' : data.countryCode === 'US' ? 'US' : '';
          const result = {
            country: countryCode,
            region: data.region || '', // ISO code (e.g., "QC", "NY")
            city: data.city || '',
          };
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify(result));
          setGeo({ ...result, loading: false });
        } else {
          setGeo({ country: '', region: '', city: '', loading: false });
        }
      })
      .catch(() => {
        clearTimeout(timeout);
        setGeo({ country: '', region: '', city: '', loading: false });
      });

    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  return geo;
};

export default useGeoLocation;
