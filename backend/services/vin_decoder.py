"""
VIN Decoder Service using NHTSA vPIC API
Free, official US government API for vehicle identification
https://vpic.nhtsa.dot.gov/api/
"""

import aiohttp
import asyncio
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

NHTSA_API_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"


class VINDecoderService:
    """Service to decode VIN using NHTSA API"""
    
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)
    
    async def decode_vin(self, vin: str) -> Dict[str, Any]:
        """
        Decode a VIN using NHTSA vPIC API
        Returns decoded vehicle information
        """
        if not vin or len(vin) != 17:
            return {"success": False, "error": "Invalid VIN format"}
        
        vin = vin.upper()
        url = f"{NHTSA_API_BASE}/decodevinvalues/{vin}?format=json"
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"NHTSA API returned status {response.status}")
                        return {"success": False, "error": f"API returned status {response.status}"}
                    
                    data = await response.json()
                    
                    if not data.get("Results") or len(data["Results"]) == 0:
                        return {"success": False, "error": "No results from VIN decode"}
                    
                    result = data["Results"][0]
                    
                    # Check for errors
                    error_code = result.get("ErrorCode", "")
                    if error_code and error_code != "0":
                        error_text = result.get("ErrorText", "Unknown error")
                        logger.warning(f"VIN decode warning: {error_text}")
                    
                    # Extract and normalize data
                    decoded = self._normalize_result(result, vin)
                    return {"success": True, "data": decoded}
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout decoding VIN {vin}")
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            logger.error(f"Error decoding VIN {vin}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _normalize_result(self, result: Dict[str, Any], vin: str) -> Dict[str, Any]:
        """Normalize NHTSA API response to our format"""
        
        # Helper to get non-empty value
        def get_val(key: str) -> Optional[str]:
            val = result.get(key, "")
            return val if val and val.strip() and val.lower() != "not applicable" else None
        
        def get_int(key: str) -> Optional[int]:
            val = get_val(key)
            if val:
                try:
                    # Handle values like "4" or "4 cyl"
                    return int(''.join(filter(str.isdigit, val.split()[0])))
                except:
                    return None
            return None
        
        def get_float(key: str) -> Optional[float]:
            val = get_val(key)
            if val:
                try:
                    return float(''.join(c for c in val if c.isdigit() or c == '.'))
                except:
                    return None
            return None
        
        # Map body type
        body_type_map = {
            "sedan": "sedan",
            "coupe": "coupe",
            "hatchback": "hatchback",
            "suv": "suv",
            "sport utility vehicle": "suv",
            "crossover": "crossover",
            "truck": "truck",
            "pickup": "truck",
            "van": "van",
            "minivan": "minivan",
            "wagon": "wagon",
            "convertible": "convertible",
            "motorcycle": "motorcycle",
        }
        
        raw_body = (get_val("BodyClass") or "").lower()
        body_type = "other"
        for key, val in body_type_map.items():
            if key in raw_body:
                body_type = val
                break
        
        # Map fuel type
        fuel_type_map = {
            "gasoline": "gasoline",
            "diesel": "diesel",
            "electric": "electric",
            "hybrid": "hybrid",
            "plug-in hybrid": "plugin_hybrid",
            "hydrogen": "hydrogen",
            "flexible fuel": "flex_fuel",
            "propane": "propane",
        }
        
        raw_fuel = (get_val("FuelTypePrimary") or "").lower()
        fuel_type = "other"
        for key, val in fuel_type_map.items():
            if key in raw_fuel:
                fuel_type = val
                break
        
        # Map transmission
        trans_map = {
            "automatic": "automatic",
            "manual": "manual",
            "cvt": "cvt",
            "dct": "dct",
            "dual clutch": "dct",
        }
        
        raw_trans = (get_val("TransmissionStyle") or "").lower()
        transmission = "other"
        for key, val in trans_map.items():
            if key in raw_trans:
                transmission = val
                break
        
        # Map drivetrain
        drive_map = {
            "fwd": "fwd",
            "front wheel": "fwd",
            "rwd": "rwd",
            "rear wheel": "rwd",
            "awd": "awd",
            "all wheel": "awd",
            "4wd": "4wd",
            "four wheel": "4wd",
            "4x4": "4wd",
        }
        
        raw_drive = (get_val("DriveType") or "").lower()
        drivetrain = "other"
        for key, val in drive_map.items():
            if key in raw_drive:
                drivetrain = val
                break
        
        return {
            "vin": vin,
            "year": get_int("ModelYear"),
            "make": get_val("Make"),
            "model": get_val("Model"),
            "trim": get_val("Trim"),
            "body_type": body_type,
            "body_class_raw": get_val("BodyClass"),
            
            # Engine
            "engine_size": get_val("DisplacementL"),
            "cylinders": get_int("EngineCylinders"),
            "horsepower": get_int("EngineHP"),
            "engine_model": get_val("EngineModel"),
            "engine_config": get_val("EngineConfiguration"),
            
            # Transmission & Drivetrain
            "transmission": transmission,
            "transmission_raw": get_val("TransmissionStyle"),
            "transmission_speeds": get_int("TransmissionSpeeds"),
            "drivetrain": drivetrain,
            "drivetrain_raw": get_val("DriveType"),
            
            # Fuel
            "fuel_type": fuel_type,
            "fuel_type_raw": get_val("FuelTypePrimary"),
            "fuel_type_secondary": get_val("FuelTypeSecondary"),
            
            # Physical
            "doors": get_int("Doors"),
            "gvwr": get_val("GVWR"),
            "curb_weight": get_val("CurbWeightLB"),
            
            # Safety
            "airbag_locations": get_val("AirBagLocFront"),
            "abs": get_val("ABS"),
            "traction_control": get_val("TractionControl"),
            "esc": get_val("ESC"),
            
            # Manufacturer
            "manufacturer": get_val("Manufacturer"),
            "plant_city": get_val("PlantCity"),
            "plant_state": get_val("PlantState"),
            "plant_country": get_val("PlantCountry"),
            
            # Series
            "series": get_val("Series"),
            "vehicle_type": get_val("VehicleType"),
            
            # Raw data for reference
            "raw_error_code": result.get("ErrorCode", ""),
            "raw_error_text": result.get("ErrorText", ""),
        }
    
    async def validate_vin_checksum(self, vin: str) -> bool:
        """
        Validate VIN checksum (position 9)
        Returns True if valid, False otherwise
        """
        if not vin or len(vin) != 17:
            return False
        
        vin = vin.upper()
        
        # Transliteration values
        trans = {
            'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
            'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'P': 7, 'R': 9,
            'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9,
        }
        
        # Position weights
        weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
        
        total = 0
        for i, char in enumerate(vin):
            if char.isdigit():
                value = int(char)
            elif char in trans:
                value = trans[char]
            else:
                return False
            total += value * weights[i]
        
        check_digit = total % 11
        expected = 'X' if check_digit == 10 else str(check_digit)
        
        return vin[8] == expected


# Singleton instance
vin_decoder_service = VINDecoderService()


async def decode_vin(vin: str) -> Dict[str, Any]:
    """Convenience function to decode VIN"""
    return await vin_decoder_service.decode_vin(vin)


async def validate_vin(vin: str) -> bool:
    """Convenience function to validate VIN checksum"""
    return await vin_decoder_service.validate_vin_checksum(vin)
