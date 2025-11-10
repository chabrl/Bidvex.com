"""
IP Geolocation and Currency Enforcement Service for BidVex
Uses ipapi.co for IP geolocation with fallback to ip-api.com
"""

import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class GeolocationService:
    """
    Handles IP geolocation and location confidence scoring
    """
    
    def __init__(self):
        self.primary_api = "https://ipapi.co/{ip}/json/"
        self.fallback_api = "http://ip-api.com/json/{ip}"
        
    async def get_location_from_ip(self, ip_address: str) -> Dict[str, Any]:
        """
        Get location data from IP address
        
        Returns:
            {
                "country_code": "CA",
                "country_name": "Canada",
                "region": "Ontario",
                "city": "Toronto",
                "latitude": 43.7,
                "longitude": -79.4,
                "confidence": "high|medium|low",
                "is_vpn_proxy": False,
                "is_hosting": False,
                "provider": "ipapi.co|ip-api.com"
            }
        """
        
        # Try primary API first (ipapi.co)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.primary_api.format(ip=ip_address))
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check for error in response
                    if data.get('error'):
                        logger.warning(f"ipapi.co error: {data.get('reason')}")
                        return await self._fallback_api(ip_address)
                    
                    return {
                        "country_code": data.get('country_code', 'UNKNOWN'),
                        "country_name": data.get('country_name', 'Unknown'),
                        "region": data.get('region', ''),
                        "city": data.get('city', ''),
                        "latitude": data.get('latitude'),
                        "longitude": data.get('longitude'),
                        "confidence": self._calculate_confidence(data),
                        "is_vpn_proxy": data.get('threat', {}).get('is_proxy', False) if isinstance(data.get('threat'), dict) else False,
                        "is_hosting": data.get('threat', {}).get('is_datacenter', False) if isinstance(data.get('threat'), dict) else False,
                        "provider": "ipapi.co",
                        "raw_data": data
                    }
        except Exception as e:
            logger.error(f"Primary geolocation API failed: {str(e)}")
        
        # Fallback to ip-api.com
        return await self._fallback_api(ip_address)
    
    async def _fallback_api(self, ip_address: str) -> Dict[str, Any]:
        """Fallback to ip-api.com"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.fallback_api.format(ip=ip_address))
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('status') == 'fail':
                        logger.error(f"ip-api.com failed: {data.get('message')}")
                        return self._default_location()
                    
                    return {
                        "country_code": data.get('countryCode', 'UNKNOWN'),
                        "country_name": data.get('country', 'Unknown'),
                        "region": data.get('regionName', ''),
                        "city": data.get('city', ''),
                        "latitude": data.get('lat'),
                        "longitude": data.get('lon'),
                        "confidence": "medium",
                        "is_vpn_proxy": data.get('proxy', False),
                        "is_hosting": data.get('hosting', False),
                        "provider": "ip-api.com",
                        "raw_data": data
                    }
        except Exception as e:
            logger.error(f"Fallback geolocation API failed: {str(e)}")
        
        return self._default_location()
    
    def _calculate_confidence(self, data: Dict) -> str:
        """Calculate confidence level based on response data"""
        if not data.get('country_code'):
            return "low"
        
        # High confidence if we have detailed location data
        if data.get('city') and data.get('region'):
            return "high"
        elif data.get('region'):
            return "medium"
        else:
            return "low"
    
    def _default_location(self) -> Dict[str, Any]:
        """Return default location when APIs fail"""
        return {
            "country_code": "UNKNOWN",
            "country_name": "Unknown",
            "region": "",
            "city": "",
            "latitude": None,
            "longitude": None,
            "confidence": "low",
            "is_vpn_proxy": False,
            "is_hosting": False,
            "provider": "default",
            "raw_data": {}
        }
    
    def calculate_location_confidence(
        self,
        ip_location: Dict[str, Any],
        timezone: Optional[str] = None,
        browser_locale: Optional[str] = None,
        billing_country: Optional[str] = None,
        shipping_country: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate location confidence score using multiple signals
        
        Returns:
            {
                "confidence_score": 0-100,
                "confidence_level": "high|medium|low",
                "signals": {...},
                "risk_flags": [...]
            }
        """
        
        signals = {
            "ip_country": ip_location.get('country_code'),
            "ip_confidence": ip_location.get('confidence'),
            "timezone": timezone,
            "browser_locale": browser_locale,
            "billing_country": billing_country,
            "shipping_country": shipping_country,
            "is_vpn_proxy": ip_location.get('is_vpn_proxy'),
            "is_hosting": ip_location.get('is_hosting')
        }
        
        score = 0
        risk_flags = []
        
        # IP location (primary signal) - 40 points
        if ip_location.get('confidence') == 'high':
            score += 40
        elif ip_location.get('confidence') == 'medium':
            score += 25
        else:
            score += 10
        
        # VPN/Proxy detection - deduct points
        if ip_location.get('is_vpn_proxy') or ip_location.get('is_hosting'):
            score -= 20
            risk_flags.append("vpn_or_proxy_detected")
        
        # Timezone match - 20 points
        if timezone:
            timezone_country = self._timezone_to_country(timezone)
            if timezone_country == ip_location.get('country_code'):
                score += 20
            else:
                risk_flags.append("timezone_mismatch")
        
        # Browser locale - 15 points
        if browser_locale:
            locale_country = self._locale_to_country(browser_locale)
            if locale_country == ip_location.get('country_code'):
                score += 15
            else:
                risk_flags.append("locale_mismatch")
        
        # Billing address - 15 points
        if billing_country and billing_country == ip_location.get('country_code'):
            score += 15
        elif billing_country:
            risk_flags.append("billing_address_mismatch")
        
        # Shipping address - 10 points
        if shipping_country and shipping_country == ip_location.get('country_code'):
            score += 10
        elif shipping_country:
            risk_flags.append("shipping_address_mismatch")
        
        # Normalize score to 0-100
        score = max(0, min(100, score))
        
        # Determine confidence level
        if score >= 70:
            confidence_level = "high"
        elif score >= 40:
            confidence_level = "medium"
        else:
            confidence_level = "low"
        
        return {
            "confidence_score": score,
            "confidence_level": confidence_level,
            "signals": signals,
            "risk_flags": risk_flags
        }
    
    def _timezone_to_country(self, timezone: str) -> Optional[str]:
        """Map timezone to country code"""
        timezone_map = {
            "America/Toronto": "CA",
            "America/Montreal": "CA",
            "America/Vancouver": "CA",
            "America/Edmonton": "CA",
            "America/Winnipeg": "CA",
            "America/Halifax": "CA",
            "America/New_York": "US",
            "America/Chicago": "US",
            "America/Denver": "US",
            "America/Los_Angeles": "US",
            "America/Phoenix": "US",
            "America/Anchorage": "US",
        }
        return timezone_map.get(timezone)
    
    def _locale_to_country(self, locale: str) -> Optional[str]:
        """Extract country from browser locale (e.g., en-CA, en-US, fr-CA)"""
        if '-' in locale:
            parts = locale.split('-')
            return parts[-1].upper()
        return None
    
    def determine_enforced_currency(
        self,
        ip_location: Dict[str, Any],
        confidence_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine enforced currency and whether to lock it
        
        Returns:
            {
                "enforced_currency": "CAD|USD",
                "currency_locked": True|False,
                "reason": "...",
                "appeal_eligible": True|False
            }
        """
        
        country_code = ip_location.get('country_code')
        confidence_score = confidence_data.get('confidence_score')
        risk_flags = confidence_data.get('risk_flags', [])
        
        # Default enforcement rules
        enforced_currency = "CAD"  # Default to CAD
        currency_locked = False
        reason = ""
        appeal_eligible = False
        
        # Determine currency based on country
        if country_code == "CA":
            enforced_currency = "CAD"
            reason = "Location detected as Canada"
        elif country_code == "US":
            enforced_currency = "USD"
            reason = "Location detected as United States"
        else:
            # Other countries default to CAD for now
            enforced_currency = "CAD"
            reason = "Default currency (international location)"
        
        # Lock currency if confidence is high OR risk flags present
        if confidence_score >= 70:
            currency_locked = True
            reason += " (high confidence)"
            appeal_eligible = True
        elif len(risk_flags) > 0:
            currency_locked = True
            reason += " (risk flags detected)"
            appeal_eligible = True
        elif confidence_score >= 40:
            # Medium confidence - suggest but don't lock
            currency_locked = False
            reason += " (medium confidence - you can change if needed)"
            appeal_eligible = False
        
        return {
            "enforced_currency": enforced_currency,
            "currency_locked": currency_locked,
            "reason": reason,
            "appeal_eligible": appeal_eligible
        }


# Global instance
geolocation_service = GeolocationService()
