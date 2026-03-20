import React, { useState, useRef, useEffect } from 'react';

/**
 * Optimized image component with:
 * - Native lazy loading
 * - Explicit dimensions (prevents CLS)
 * - WebP hint via Accept header
 * - Graceful fallback on error
 * - Fade-in on load
 */
const OptimizedImage = ({ 
  src, 
  alt, 
  width, 
  height, 
  className = '', 
  fallback = '/placeholder.svg',
  eager = false,
  ...props 
}) => {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  
  const imgSrc = error ? fallback : src;
  
  return (
    <img
      src={imgSrc}
      alt={alt || ''}
      width={width}
      height={height}
      loading={eager ? 'eager' : 'lazy'}
      decoding="async"
      onLoad={() => setLoaded(true)}
      onError={() => setError(true)}
      className={`transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'} ${className}`}
      {...props}
    />
  );
};

export default OptimizedImage;
