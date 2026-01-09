"""
BidVex Fee & Cost Calculation Engine
Handles buyer premiums, seller commissions, taxes, and subscription-based discounts
Updated: Percentage-based fees with NO maximum cap
"""

from typing import Dict, Tuple
from decimal import Decimal

# Global fee constants - No cap, percentage-based
DEFAULT_BUYER_PREMIUM = Decimal("0.05")  # 5%
DEFAULT_SELLER_COMMISSION = Decimal("0.04")  # 4%

# Subscription tier fee structure - Updated for yearly billing
# Free: 4% Seller / 5% Buyer
# Premium: 2.5% Seller / 3.5% Buyer (1.5% reduction)
# VIP: 2% Seller / 3% Buyer (2% reduction)
SUBSCRIPTION_FEES = {
    "free": {
        "buyer_premium": Decimal("0.05"),  # 5%
        "seller_commission": Decimal("0.04")  # 4%
    },
    "starter": {
        "buyer_premium": Decimal("0.05"),  # 5%
        "seller_commission": Decimal("0.04")  # 4%
    },
    "premium": {
        "buyer_premium": Decimal("0.035"),  # 3.5% (1.5% discount)
        "seller_commission": Decimal("0.025")  # 2.5% (1.5% discount)
    },
    "vip": {
        "buyer_premium": Decimal("0.03"),  # 3.0% (2% discount)
        "seller_commission": Decimal("0.02")  # 2.0% (2% discount)
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
        include_tax: bool = True,
        seller_is_business: bool = False
    ) -> Dict:
        """
        Calculate buyer's total out-of-pocket cost
        
        CRITICAL TAX LOGIC:
        - Individual Sellers (seller_is_business=False): 
          * NO tax on hammer price (individuals cannot collect tax)
          * Tax ONLY on buyer premium (BidVex is a business)
        - Business Sellers (seller_is_business=True):
          * Tax on hammer price (collected by seller via BidVex)
          * Tax on buyer premium (BidVex's fee)
        
        Returns:
            {
                "hammer_price": Decimal,
                "buyer_premium": Decimal,
                "buyer_premium_percent": Decimal,
                "subtotal": Decimal,
                "tax": Decimal,
                "tax_on_hammer": Decimal,
                "tax_on_premium": Decimal,
                "tax_breakdown": Dict,
                "total": Decimal,
                "seller_type": str
            }
        """
        hammer_price = Decimal(str(hammer_price))
        buyer_premium_rate = FeeCalculator.get_buyer_premium(buyer_tier)
        
        # Calculate buyer premium
        buyer_premium = hammer_price * buyer_premium_rate
        subtotal = hammer_price + buyer_premium
        
        # Initialize tax variables
        tax_on_hammer = Decimal("0")
        tax_on_premium = Decimal("0")
        tax_amount = Decimal("0")
        tax_breakdown = {}
        
        if include_tax:
            tax_rates = TAX_RATES.get(region, TAX_RATES["QC"])
            
            # CRITICAL: Tax logic based on seller type
            if seller_is_business:
                # Business Seller: Tax on BOTH hammer price and premium
                taxable_amount = subtotal
            else:
                # Individual Seller: Tax ONLY on buyer premium (hammer price is tax-free)
                taxable_amount = buyer_premium
            
            # Calculate taxes
            if "gst" in tax_rates and "qst" in tax_rates:
                # Quebec: GST on taxable amount, QST on taxable amount + GST
                gst = taxable_amount * tax_rates["gst"]
                qst = (taxable_amount + gst) * tax_rates["qst"]
                tax_amount = gst + qst
                
                # Break down tax between hammer and premium
                if seller_is_business:
                    # Tax applied to full subtotal
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    # All tax is on premium only
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "gst": float(gst),
                    "qst": float(qst),
                    "gst_rate": float(tax_rates["gst"]),
                    "qst_rate": float(tax_rates["qst"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
            elif "hst" in tax_rates:
                # Ontario: HST on taxable amount
                hst = taxable_amount * tax_rates["hst"]
                tax_amount = hst
                
                if seller_is_business:
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "hst": float(hst),
                    "hst_rate": float(tax_rates["hst"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
            elif "gst" in tax_rates and "pst" in tax_rates:
                # BC: GST + PST on taxable amount
                gst = taxable_amount * tax_rates["gst"]
                pst = taxable_amount * tax_rates["pst"]
                tax_amount = gst + pst
                
                if seller_is_business:
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "gst": float(gst),
                    "pst": float(pst),
                    "gst_rate": float(tax_rates["gst"]),
                    "pst_rate": float(tax_rates["pst"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
            elif "gst" in tax_rates:
                # Alberta: GST only on taxable amount
                gst = taxable_amount * tax_rates["gst"]
                tax_amount = gst
                
                if seller_is_business:
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "gst": float(gst),
                    "gst_rate": float(tax_rates["gst"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
            elif "vat" in tax_rates:
                # EU: VAT on taxable amount
                vat = taxable_amount * tax_rates["vat"]
                tax_amount = vat
                
                if seller_is_business:
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "vat": float(vat),
                    "vat_rate": float(tax_rates["vat"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
        
        total = subtotal + tax_amount
        
        # Calculate savings for individual seller
        savings = Decimal("0")
        if not seller_is_business and include_tax:
            # Calculate what tax WOULD have been on hammer price
            tax_rates_data = TAX_RATES.get(region, TAX_RATES["QC"])
            if "gst" in tax_rates_data and "qst" in tax_rates_data:
                would_be_gst = hammer_price * tax_rates_data["gst"]
                would_be_qst = (hammer_price + would_be_gst) * tax_rates_data["qst"]
                savings = would_be_gst + would_be_qst
        
        return {
            "hammer_price": float(hammer_price),
            "buyer_premium": float(buyer_premium),
            "buyer_premium_percent": float(buyer_premium_rate * 100),
            "subtotal": float(subtotal),
            "tax": float(tax_amount),
            "tax_on_hammer": float(tax_on_hammer),
            "tax_on_premium": float(tax_on_premium),
            "tax_breakdown": tax_breakdown,
            "total": float(total),
            "region": region,
            "tier": buyer_tier,
            "seller_type": "business" if seller_is_business else "individual",
            "tax_savings": float(savings) if savings > 0 else 0
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
        region: str = "QC",
        seller_is_business: bool = False
    ) -> Dict:
        """
        Calculate complete transaction breakdown for buyer and seller
        """
        buyer_calc = FeeCalculator.calculate_buyer_total(
            hammer_price, buyer_tier, region, True, seller_is_business
        )
        seller_calc = FeeCalculator.calculate_seller_net(
            hammer_price, seller_tier
        )
        
        return {
            "hammer_price": float(hammer_price),
            "buyer": buyer_calc,
            "seller": seller_calc,
            "platform_revenue": buyer_calc["buyer_premium"] + seller_calc["seller_commission"],
            "seller_type": "business" if seller_is_business else "individual"
        }


# Helper function for quick calculations
def calculate_buyer_total(amount: float, tier: str = "free", region: str = "QC", seller_is_business: bool = False) -> Dict:
    """Quick helper to calculate buyer total"""
    return FeeCalculator.calculate_buyer_total(Decimal(str(amount)), tier, region, True, seller_is_business)


def calculate_seller_net(amount: float, tier: str = "free") -> Dict:
    """Quick helper to calculate seller net"""
    return FeeCalculator.calculate_seller_net(Decimal(str(amount)), tier)
