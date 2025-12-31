"""
BidVex Fee & Cost Calculation Engine
Handles buyer premiums, seller commissions, taxes, and subscription-based discounts
"""

from typing import Dict, Tuple
from decimal import Decimal

# Global fee constants
DEFAULT_BUYER_PREMIUM = Decimal("0.05")  # 5%
DEFAULT_SELLER_COMMISSION = Decimal("0.045")  # 4.5%

# Subscription tier fee structure
SUBSCRIPTION_FEES = {
    "free": {
        "buyer_premium": Decimal("0.05"),  # 5%
        "seller_commission": Decimal("0.045")  # 4.5%
    },
    "starter": {
        "buyer_premium": Decimal("0.05"),  # 5%
        "seller_commission": Decimal("0.045")  # 4.5%
    },
    "premium": {
        "buyer_premium": Decimal("0.05"),  # 5%
        "seller_commission": Decimal("0.04")  # 4.0% (0.5% discount)
    },
    "vip": {
        "buyer_premium": Decimal("0.04"),  # 4.0%
        "seller_commission": Decimal("0.04")  # 4.0%
    }
}

# Tax rates by region
TAX_RATES = {
    "QC": {
        "gst": Decimal("0.05"),  # 5% GST
        "qst": Decimal("0.09975"),  # 9.975% QST
        "name": "Quebec (GST + QST)"
    },
    "ON": {
        "hst": Decimal("0.13"),  # 13% HST
        "name": "Ontario (HST)"
    },
    "BC": {
        "gst": Decimal("0.05"),  # 5% GST
        "pst": Decimal("0.07"),  # 7% PST
        "name": "British Columbia (GST + PST)"
    },
    "AB": {
        "gst": Decimal("0.05"),  # 5% GST only
        "name": "Alberta (GST)"
    },
    "EU": {
        "vat": Decimal("0.20"),  # 20% VAT (varies by country)
        "name": "European Union (VAT)"
    },
    "US": {
        "sales_tax": Decimal("0.00"),  # Varies by state
        "name": "United States"
    }
}


class FeeCalculator:
    """Calculate all fees, taxes, and net amounts for BidVex transactions"""
    
    @staticmethod
    def get_buyer_premium(subscription_tier: str) -> Decimal:
        """Get buyer premium percentage based on subscription tier"""
        tier = subscription_tier.lower() if subscription_tier else "free"
        return SUBSCRIPTION_FEES.get(tier, SUBSCRIPTION_FEES["free"])["buyer_premium"]
    
    @staticmethod
    def get_seller_commission(subscription_tier: str) -> Decimal:
        """Get seller commission percentage based on subscription tier"""
        tier = subscription_tier.lower() if subscription_tier else "free"
        return SUBSCRIPTION_FEES.get(tier, SUBSCRIPTION_FEES["free"])["seller_commission"]
    
    @staticmethod
    def calculate_buyer_total(
        hammer_price: Decimal,
        buyer_tier: str = "free",
        region: str = "QC",
        include_tax: bool = True
    ) -> Dict:
        """
        Calculate buyer's total out-of-pocket cost
        
        Returns:
            {
                "hammer_price": Decimal,
                "buyer_premium": Decimal,
                "buyer_premium_percent": Decimal,
                "subtotal": Decimal,
                "tax": Decimal,
                "tax_breakdown": Dict,
                "total": Decimal
            }
        """
        hammer_price = Decimal(str(hammer_price))
        buyer_premium_rate = FeeCalculator.get_buyer_premium(buyer_tier)
        
        # Calculate buyer premium
        buyer_premium = hammer_price * buyer_premium_rate
        subtotal = hammer_price + buyer_premium
        
        # Calculate tax
        tax_amount = Decimal("0")
        tax_breakdown = {}
        
        if include_tax:
            tax_rates = TAX_RATES.get(region, TAX_RATES["QC"])
            
            if "gst" in tax_rates and "qst" in tax_rates:
                # Quebec: GST on subtotal, QST on subtotal + GST
                gst = subtotal * tax_rates["gst"]
                qst = (subtotal + gst) * tax_rates["qst"]
                tax_amount = gst + qst
                tax_breakdown = {
                    "gst": float(gst),
                    "qst": float(qst),
                    "gst_rate": float(tax_rates["gst"]),
                    "qst_rate": float(tax_rates["qst"])
                }
            elif "hst" in tax_rates:
                # Ontario: HST on subtotal
                hst = subtotal * tax_rates["hst"]
                tax_amount = hst
                tax_breakdown = {
                    "hst": float(hst),
                    "hst_rate": float(tax_rates["hst"])
                }
            elif "gst" in tax_rates and "pst" in tax_rates:
                # BC: GST + PST on subtotal
                gst = subtotal * tax_rates["gst"]
                pst = subtotal * tax_rates["pst"]
                tax_amount = gst + pst
                tax_breakdown = {
                    "gst": float(gst),
                    "pst": float(pst),
                    "gst_rate": float(tax_rates["gst"]),
                    "pst_rate": float(tax_rates["pst"])
                }
            elif "gst" in tax_rates:
                # Alberta: GST only
                gst = subtotal * tax_rates["gst"]
                tax_amount = gst
                tax_breakdown = {
                    "gst": float(gst),
                    "gst_rate": float(tax_rates["gst"])
                }
            elif "vat" in tax_rates:
                # EU: VAT on subtotal
                vat = subtotal * tax_rates["vat"]
                tax_amount = vat
                tax_breakdown = {
                    "vat": float(vat),
                    "vat_rate": float(tax_rates["vat"])
                }
        
        total = subtotal + tax_amount
        
        return {
            "hammer_price": float(hammer_price),
            "buyer_premium": float(buyer_premium),
            "buyer_premium_percent": float(buyer_premium_rate * 100),
            "subtotal": float(subtotal),
            "tax": float(tax_amount),
            "tax_breakdown": tax_breakdown,
            "total": float(total),
            "region": region,
            "tier": buyer_tier
        }
    
    @staticmethod
    def calculate_seller_net(
        hammer_price: Decimal,
        seller_tier: str = "free"
    ) -> Dict:
        """
        Calculate seller's net payout after commission
        
        Returns:
            {
                "hammer_price": Decimal,
                "seller_commission": Decimal,
                "seller_commission_percent": Decimal,
                "net_payout": Decimal
            }
        """
        hammer_price = Decimal(str(hammer_price))
        commission_rate = FeeCalculator.get_seller_commission(seller_tier)
        
        # Calculate commission
        commission = hammer_price * commission_rate
        net_payout = hammer_price - commission
        
        return {
            "hammer_price": float(hammer_price),
            "seller_commission": float(commission),
            "seller_commission_percent": float(commission_rate * 100),
            "net_payout": float(net_payout),
            "tier": seller_tier
        }
    
    @staticmethod
    def calculate_full_transaction(
        hammer_price: Decimal,
        buyer_tier: str = "free",
        seller_tier: str = "free",
        region: str = "QC"
    ) -> Dict:
        """
        Calculate complete transaction breakdown for buyer and seller
        """
        buyer_calc = FeeCalculator.calculate_buyer_total(
            hammer_price, buyer_tier, region
        )
        seller_calc = FeeCalculator.calculate_seller_net(
            hammer_price, seller_tier
        )
        
        return {
            "hammer_price": float(hammer_price),
            "buyer": buyer_calc,
            "seller": seller_calc,
            "platform_revenue": buyer_calc["buyer_premium"] + seller_calc["seller_commission"]
        }


# Helper function for quick calculations
def calculate_buyer_total(amount: float, tier: str = "free", region: str = "QC") -> Dict:
    """Quick helper to calculate buyer total"""
    return FeeCalculator.calculate_buyer_total(Decimal(str(amount)), tier, region)


def calculate_seller_net(amount: float, tier: str = "free") -> Dict:
    """Quick helper to calculate seller net"""
    return FeeCalculator.calculate_seller_net(Decimal(str(amount)), tier)
