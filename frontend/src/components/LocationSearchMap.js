import React, { useState, useCallback, useEffect } from 'react';
import { GoogleMap, useLoadScript, Marker, Circle } from '@react-google-maps/api';
import { Button } from './ui/button';
import { Slider } from './ui/slider';
import { Card } from './ui/card';
import { MapPin, Navigation } from 'lucide-react';

const libraries = ['places'];
const mapContainerStyle = {
  width: '100%',
  height: '400px',
};

const LocationSearchMap = ({ onLocationSearch }) => {
  const [map, setMap] = useState(null);
  const [center, setCenter] = useState({ lat: 40.7128, lng: -74.0060 }); // Default: NYC
  const [radius, setRadius] = useState(50); // km
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [apiKey, setApiKey] = useState('');

  useEffect(() => {
    // Fetch Google Maps API key from backend
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/config/google-maps-key`)
      .then(res => res.json())
      .then(data => setApiKey(data.api_key))
      .catch(err => console.error('Failed to fetch API key:', err));
  }, []);

  const { isLoaded, loadError } = useLoadScript({
    googleMapsApiKey: apiKey,
    libraries,
  });

  const onLoad = useCallback((map) => {
    setMap(map);
  }, []);

  const handleMapClick = useCallback((e) => {
    const location = {
      lat: e.latLng.lat(),
      lng: e.latLng.lng(),
    };
    setSelectedLocation(location);
    setCenter(location);
  }, []);

  const handleUseMyLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const location = {
            lat: position.coords.latitude,
            lng: position.coords.longitude,
          };
          setSelectedLocation(location);
          setCenter(location);
        },
        (error) => {
          console.error('Geolocation error:', error);
          alert('Unable to get your location');
        }
      );
    } else {
      alert('Geolocation is not supported by your browser');
    }
  };

  const handleSearch = () => {
    if (selectedLocation) {
      onLocationSearch({
        latitude: selectedLocation.lat,
        longitude: selectedLocation.lng,
        radius_km: radius,
      });
    }
  };

  if (loadError) return <div>Error loading maps</div>;
  if (!isLoaded || !apiKey) return <div>Loading maps...</div>;

  return (
    <Card className=\"p-4 space-y-4\">
      <div className=\"flex items-center justify-between\">
        <h3 className=\"font-semibold\">Search by Location</h3>
        <Button
          variant=\"outline\"
          size=\"sm\"
          onClick={handleUseMyLocation}
          data-testid=\"use-my-location-btn\"
        >
          <Navigation className=\"mr-2 h-4 w-4\" />
          Use My Location
        </Button>
      </div>

      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        zoom={10}
        center={center}
        onLoad={onLoad}
        onClick={handleMapClick}
        options={{
          streetViewControl: false,
          mapTypeControl: false,
        }}
      >
        {selectedLocation && (
          <>
            <Marker position={selectedLocation} />
            <Circle
              center={selectedLocation}
              radius={radius * 1000} // Convert km to meters
              options={{
                strokeColor: '#30C7B5',
                strokeOpacity: 0.8,
                strokeWeight: 2,
                fillColor: '#30C7B5',
                fillOpacity: 0.2,
              }}
            />
          </>
        )}
      </GoogleMap>

      <div className=\"space-y-2\">
        <div className=\"flex items-center justify-between\">
          <label className=\"text-sm font-medium\">Search Radius</label>
          <span className=\"text-sm text-muted-foreground\">{radius} km</span>
        </div>
        <Slider
          value={[radius]}
          onValueChange={(value) => setRadius(value[0])}
          min={1}
          max={200}
          step={1}
          className=\"w-full\"
        />
        <div className=\"flex gap-2 text-xs text-muted-foreground\">
          <button onClick={() => setRadius(5)} className=\"hover:text-primary\">5km</button>
          <button onClick={() => setRadius(10)} className=\"hover:text-primary\">10km</button>
          <button onClick={() => setRadius(50)} className=\"hover:text-primary\">50km</button>
          <button onClick={() => setRadius(100)} className=\"hover:text-primary\">100km</button>
        </div>
      </div>

      <Button
        onClick={handleSearch}
        disabled={!selectedLocation}
        className=\"w-full gradient-button text-white border-0\"
        data-testid=\"search-location-btn\"
      >
        <MapPin className=\"mr-2 h-4 w-4\" />
        Search Listings in This Area
      </Button>

      {selectedLocation && (
        <p className=\"text-xs text-muted-foreground text-center\">
          Searching near: {selectedLocation.lat.toFixed(4)}, {selectedLocation.lng.toFixed(4)}
        </p>
      )}
    </Card>
  );
};

export default LocationSearchMap;
