"""
BidVex AI Guard - Fraud Detection Service
Analyzes auctions for suspicious activity using pattern detection and GPT-4
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Flag types and their configurations
FLAG_TYPES = {
    'bid_shilling': {
        'label': 'Bid Shilling',
        'severity': 'critical',
        'description': 'Suspected artificial price inflation'
    },
    'price_anomaly': {
        'label': 'Price Anomaly', 
        'severity': 'high',
        'description': 'Price significantly deviates from market value'
    },
    'account_risk': {
        'label': 'Account Risk',
        'severity': 'high', 
        'description': 'Suspicious account behavior patterns'
    },
    'rapid_bidding': {
        'label': 'Rapid Bidding',
        'severity': 'medium',
        'description': 'Unusually fast bidding patterns'
    },
    'ip_clustering': {
        'label': 'IP Clustering',
        'severity': 'critical',
        'description': 'Multiple accounts from same IP'
    },
    'new_account_high_bid': {
        'label': 'New Account High Bid',
        'severity': 'medium',
        'description': 'New account placing high-value bids'
    }
}

# Status configurations
FLAG_STATUSES = ['pending_review', 'under_investigation', 'cleared', 'confirmed_fraud']


class FraudDetectionService:
    """
    AI-powered fraud detection for vehicle auctions.
    Analyzes bidding patterns, account behavior, and pricing anomalies.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.gemini_key = os.environ.get('GEMINI_API_KEY')
        self._gemini_client = None

    @property
    def gemini_client(self):
        if self._gemini_client is None and self.gemini_key:
            from google import genai
            self._gemini_client = genai.Client(api_key=self.gemini_key)
        return self._gemini_client
        
    async def analyze_auction(self, auction_id: str) -> List[Dict[str, Any]]:
        """
        Perform comprehensive fraud analysis on a single auction.
        Returns list of detected flags.
        """
        flags = []
        
        # Get auction data
        auction = await self.db.vehicles.find_one({"id": auction_id}, {"_id": 0})
        if not auction:
            auction = await self.db.listings.find_one({"id": auction_id}, {"_id": 0})
        
        if not auction:
            return flags
            
        # Get all bids for this auction
        bids = await self.db.bids.find(
            {"listing_id": auction_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(1000)
        
        if not bids:
            bids = await self.db.lot_bids.find(
                {"auction_id": auction_id},
                {"_id": 0}
            ).sort("created_at", -1).to_list(1000)
        
        # Run all detection algorithms
        flags.extend(await self._detect_bid_shilling(auction, bids))
        flags.extend(await self._detect_price_anomaly(auction, bids))
        flags.extend(await self._detect_rapid_bidding(auction, bids))
        flags.extend(await self._detect_account_risks(auction, bids))
        
        return flags
    
    async def scan_all_auctions(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Scan all recent auctions for fraud patterns.
        Returns list of all detected flags.
        """
        all_flags = []
        # Note: hours_back parameter reserved for future filtering by created_at
        
        # Scan vehicle auctions
        vehicles = await self.db.vehicles.find(
            {"status": {"$in": ["active", "ending_soon"]}},
            {"_id": 0}
        ).to_list(500)
        
        for vehicle in vehicles:
            try:
                flags = await self.analyze_auction(vehicle.get("id"))
                all_flags.extend(flags)
            except Exception as e:
                logger.error(f"Error analyzing vehicle {vehicle.get('id')}: {e}")
        
        # Scan regular auctions
        listings = await self.db.listings.find(
            {"status": "active"},
            {"_id": 0}
        ).to_list(500)
        
        for listing in listings:
            try:
                flags = await self.analyze_auction(listing.get("id"))
                all_flags.extend(flags)
            except Exception as e:
                logger.error(f"Error analyzing listing {listing.get('id')}: {e}")
        
        # Detect cross-auction patterns (IP clustering, collusion)
        all_flags.extend(await self._detect_ip_clustering())
        all_flags.extend(await self._detect_collusion_patterns())
        
        return all_flags
    
    async def _detect_bid_shilling(
        self, 
        auction: Dict[str, Any], 
        bids: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect bid shilling - artificial price inflation by related accounts.
        """
        flags = []
        
        if len(bids) < 3:
            return flags
            
        seller_id = auction.get("seller_id")
        bidder_counts = defaultdict(int)
        bidder_amounts = defaultdict(list)
        
        for bid in bids:
            bidder_id = bid.get("bidder_id")
            bidder_counts[bidder_id] += 1
            bidder_amounts[bidder_id].append(bid.get("amount", 0))
        
        # Check for suspicious patterns
        for bidder_id, count in bidder_counts.items():
            if count < 2:
                continue
                
            # Get bidder info
            bidder = await self.db.users.find_one({"id": bidder_id}, {"_id": 0})
            if not bidder:
                continue
            
            # Pattern 1: Same bidder makes many small increment bids
            amounts = bidder_amounts[bidder_id]
            if len(amounts) >= 3:
                # Check if increments are suspiciously uniform
                increments = [amounts[i] - amounts[i+1] for i in range(len(amounts)-1)]
                avg_increment = sum(increments) / len(increments) if increments else 0
                
                # Small, uniform increments suggest automated bidding
                if avg_increment > 0 and avg_increment < 50 and max(increments) - min(increments) < 10:
                    confidence = min(0.9, 0.5 + (count * 0.1))
                    
                    # Get seller name safely
                    seller_doc = await self.db.users.find_one({"id": seller_id}) if seller_id else None
                    seller_name = seller_doc.get("name", "Unknown") if seller_doc else "Unknown"
                    
                    flags.append({
                        "id": f"flag-{auction.get('id')}-shill-{bidder_id[:8]}",
                        "auction_id": auction.get("id"),
                        "auction_title": auction.get("title", auction.get("year", "") + " " + auction.get("make", "") + " " + auction.get("model", "")),
                        "seller_id": seller_id,
                        "seller_name": seller_name,
                        "flag_type": "bid_shilling",
                        "confidence": confidence,
                        "reason": f"Bidder placed {count} bids with suspiciously uniform increments (avg ${avg_increment:.2f}). Pattern suggests automated price manipulation.",
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                        "status": "pending_review",
                        "bidder_id": bidder_id,
                        "bidder_name": bidder.get("name", "Unknown"),
                        "bid_count": count
                    })
        
        return flags
    
    async def _detect_price_anomaly(
        self,
        auction: Dict[str, Any],
        bids: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect price anomalies - bids significantly above/below market value.
        """
        flags = []
        
        # Get current price
        current_price = auction.get("current_bid", auction.get("current_price", auction.get("starting_price", 0)))
        starting_price = auction.get("starting_price", 0)
        
        if not current_price or current_price < 100:
            return flags
        
        # For vehicles, check against typical market values
        if auction.get("make") and auction.get("model"):
            year = auction.get("year", 2020)
            
            # Rough market value estimation based on vehicle type
            base_values = {
                "Toyota": 25000, "Honda": 24000, "Ford": 28000, "Chevrolet": 27000,
                "Tesla": 45000, "BMW": 40000, "Mercedes-Benz": 45000, "Audi": 38000,
                "Lexus": 35000, "Porsche": 60000
            }
            
            base_value = base_values.get(auction.get("make"), 25000)
            # Adjust for year (depreciation)
            current_year = datetime.now().year
            age = current_year - year
            estimated_value = base_value * (0.85 ** min(age, 10))  # 15% depreciation per year
            
            # Flag if price is way off
            price_ratio = current_price / estimated_value if estimated_value > 0 else 1
            
            if price_ratio < 0.4:  # 60% below estimated value
                flags.append({
                    "id": f"flag-{auction.get('id')}-price-low",
                    "auction_id": auction.get("id"),
                    "auction_title": f"{auction.get('year', '')} {auction.get('make', '')} {auction.get('model', '')}".strip(),
                    "seller_id": auction.get("seller_id"),
                    "seller_name": (await self._get_user_name(auction.get("seller_id"))),
                    "flag_type": "price_anomaly",
                    "confidence": min(0.95, 0.6 + (1 - price_ratio) * 0.5),
                    "reason": f"Starting price ${starting_price:,.0f} is {((1-price_ratio)*100):.0f}% below estimated market value of ${estimated_value:,.0f} for a {year} {auction.get('make')}. Possible bait pricing or suspicious listing.",
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending_review",
                    "estimated_value": estimated_value,
                    "actual_price": current_price
                })
            elif price_ratio > 2.5:  # 150% above estimated value
                flags.append({
                    "id": f"flag-{auction.get('id')}-price-high",
                    "auction_id": auction.get("id"),
                    "auction_title": f"{auction.get('year', '')} {auction.get('make', '')} {auction.get('model', '')}".strip(),
                    "seller_id": auction.get("seller_id"),
                    "seller_name": (await self._get_user_name(auction.get("seller_id"))),
                    "flag_type": "price_anomaly",
                    "confidence": min(0.9, 0.5 + (price_ratio - 2) * 0.2),
                    "reason": f"Current bid ${current_price:,.0f} is {((price_ratio-1)*100):.0f}% above estimated market value of ${estimated_value:,.0f}. Possible shill bidding or price manipulation.",
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending_review",
                    "estimated_value": estimated_value,
                    "actual_price": current_price
                })
        
        return flags
    
    async def _detect_rapid_bidding(
        self,
        auction: Dict[str, Any],
        bids: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect rapid bidding patterns that suggest automation or coordination.
        """
        flags = []
        
        if len(bids) < 5:
            return flags
        
        # Sort by time
        sorted_bids = sorted(bids, key=lambda x: x.get("created_at", ""))
        
        # Check bid timing
        rapid_sequences = []
        for i in range(len(sorted_bids) - 1):
            current_time = sorted_bids[i].get("created_at", "")
            next_time = sorted_bids[i + 1].get("created_at", "")
            
            try:
                if isinstance(current_time, str):
                    current_dt = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
                else:
                    current_dt = current_time
                    
                if isinstance(next_time, str):
                    next_dt = datetime.fromisoformat(next_time.replace("Z", "+00:00"))
                else:
                    next_dt = next_time
                
                time_diff = abs((next_dt - current_dt).total_seconds())
                
                # Flag if bids are less than 5 seconds apart
                if time_diff < 5:
                    rapid_sequences.append({
                        "bidder1": sorted_bids[i].get("bidder_id"),
                        "bidder2": sorted_bids[i + 1].get("bidder_id"),
                        "time_diff": time_diff
                    })
            except Exception as e:
                logger.debug(f"Error parsing bid times: {e}")
                continue
        
        # If there are multiple rapid sequences, flag it
        if len(rapid_sequences) >= 3:
            bidders_involved = set()
            for seq in rapid_sequences:
                bidders_involved.add(seq["bidder1"])
                bidders_involved.add(seq["bidder2"])
            
            flags.append({
                "id": f"flag-{auction.get('id')}-rapid",
                "auction_id": auction.get("id"),
                "auction_title": auction.get("title", f"{auction.get('year', '')} {auction.get('make', '')} {auction.get('model', '')}".strip()),
                "seller_id": auction.get("seller_id"),
                "seller_name": (await self._get_user_name(auction.get("seller_id"))),
                "flag_type": "rapid_bidding",
                "confidence": min(0.85, 0.5 + len(rapid_sequences) * 0.1),
                "reason": f"Detected {len(rapid_sequences)} bid sequences with less than 5 seconds between bids. {len(bidders_involved)} bidders involved. Pattern suggests coordinated or automated bidding.",
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending_review",
                "rapid_sequence_count": len(rapid_sequences),
                "bidders_involved": len(bidders_involved)
            })
        
        return flags
    
    async def _detect_account_risks(
        self,
        auction: Dict[str, Any],
        bids: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect account-based risks - new accounts, unverified users, etc.
        """
        flags = []
        
        for bid in bids:
            bidder_id = bid.get("bidder_id")
            if not bidder_id:
                continue
                
            bidder = await self.db.users.find_one({"id": bidder_id}, {"_id": 0})
            if not bidder:
                continue
            
            # Calculate account age
            created_at = bidder.get("created_at", "")
            try:
                if isinstance(created_at, str):
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                else:
                    created_dt = created_at
                account_age_days = (datetime.now(timezone.utc) - created_dt).days
            except Exception:
                account_age_days = 365  # Default to old account if can't parse
            
            bid_amount = bid.get("amount", 0)
            
            # Flag new accounts with high bids
            if account_age_days < 7 and bid_amount > 1000:
                flags.append({
                    "id": f"flag-{auction.get('id')}-newacct-{bidder_id[:8]}",
                    "auction_id": auction.get("id"),
                    "auction_title": auction.get("title", f"{auction.get('year', '')} {auction.get('make', '')} {auction.get('model', '')}".strip()),
                    "seller_id": auction.get("seller_id"),
                    "seller_name": (await self._get_user_name(auction.get("seller_id"))),
                    "flag_type": "new_account_high_bid",
                    "confidence": min(0.8, 0.5 + (bid_amount / 10000)),
                    "reason": f"Account created {account_age_days} days ago placed a ${bid_amount:,.0f} bid. New accounts bidding high amounts warrant review.",
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending_review",
                    "bidder_id": bidder_id,
                    "bidder_name": bidder.get("name", "Unknown"),
                    "account_age_days": account_age_days,
                    "bid_amount": bid_amount
                })
            
            # Flag unverified accounts bidding on high-value items
            if not bidder.get("phone_verified") and bid_amount > 5000:
                flags.append({
                    "id": f"flag-{auction.get('id')}-unverified-{bidder_id[:8]}",
                    "auction_id": auction.get("id"),
                    "auction_title": auction.get("title", f"{auction.get('year', '')} {auction.get('make', '')} {auction.get('model', '')}".strip()),
                    "seller_id": auction.get("seller_id"),
                    "seller_name": (await self._get_user_name(auction.get("seller_id"))),
                    "flag_type": "account_risk",
                    "confidence": 0.65,
                    "reason": f"Unverified account bidding ${bid_amount:,.0f} on high-value item. Phone verification not completed.",
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending_review",
                    "bidder_id": bidder_id,
                    "bidder_name": bidder.get("name", "Unknown"),
                    "phone_verified": False,
                    "bid_amount": bid_amount
                })
        
        return flags
    
    async def _detect_ip_clustering(self) -> List[Dict[str, Any]]:
        """
        Detect multiple accounts potentially from the same user via IP analysis.
        """
        flags = []
        
        # Get recent login sessions with IP info
        sessions = await self.db.user_sessions.find(
            {"created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()}},
            {"_id": 0}
        ).to_list(5000)
        
        # Group by IP
        ip_users = defaultdict(set)
        for session in sessions:
            ip = session.get("ip_address")
            user_id = session.get("user_id")
            if ip and user_id:
                ip_users[ip].add(user_id)
        
        # Flag IPs with multiple users who have bid on same auctions
        for ip, user_ids in ip_users.items():
            if len(user_ids) < 2:
                continue
            
            # Check if these users bid on same auctions
            user_list = list(user_ids)
            common_auctions = set()
            
            for user_id in user_list:
                user_bids = await self.db.bids.find(
                    {"bidder_id": user_id},
                    {"listing_id": 1}
                ).to_list(100)
                
                user_auctions = set(b.get("listing_id") for b in user_bids if b.get("listing_id"))
                
                if not common_auctions:
                    common_auctions = user_auctions
                else:
                    common_auctions = common_auctions.intersection(user_auctions)
            
            if common_auctions and len(user_ids) >= 2:
                user_names = []
                for uid in list(user_ids)[:5]:
                    name = await self._get_user_name(uid)
                    user_names.append(name)
                
                flags.append({
                    "id": f"flag-ip-cluster-{ip[:8] if ip else 'unknown'}",
                    "auction_id": list(common_auctions)[0] if common_auctions else None,
                    "auction_title": "Multiple Auctions Affected",
                    "seller_id": None,
                    "seller_name": "N/A",
                    "flag_type": "ip_clustering",
                    "confidence": min(0.95, 0.6 + len(user_ids) * 0.1),
                    "reason": f"{len(user_ids)} different accounts ({', '.join(user_names)}) accessed from same IP address and bid on {len(common_auctions)} common auctions. Possible bid manipulation ring.",
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending_review",
                    "ip_address": ip[:10] + "***" if ip else "Unknown",
                    "accounts_involved": len(user_ids),
                    "common_auctions": len(common_auctions)
                })
        
        return flags
    
    async def _detect_collusion_patterns(self) -> List[Dict[str, Any]]:
        """
        Detect potential collusion between buyers and sellers.
        """
        flags = []
        
        # Find buyer-seller pairs with multiple transactions
        completed_listings = await self.db.listings.find(
            {"status": {"$in": ["sold", "completed"]}},
            {"_id": 0}
        ).to_list(500)
        
        pair_transactions = defaultdict(list)
        
        for listing in completed_listings:
            seller_id = listing.get("seller_id")
            highest_bidder = listing.get("highest_bidder_id")
            
            if seller_id and highest_bidder:
                pair_key = f"{seller_id}|{highest_bidder}"
                pair_transactions[pair_key].append(listing)
        
        # Flag pairs with suspicious patterns
        for pair_key, transactions in pair_transactions.items():
            if len(transactions) >= 3:
                seller_id, buyer_id = pair_key.split("|")
                
                # Calculate average winning margin
                total_value = sum(t.get("current_price", 0) for t in transactions)
                
                flags.append({
                    "id": f"flag-collusion-{seller_id[:8]}-{buyer_id[:8]}",
                    "auction_id": transactions[0].get("id"),
                    "auction_title": f"Pattern across {len(transactions)} auctions",
                    "seller_id": seller_id,
                    "seller_name": (await self._get_user_name(seller_id)),
                    "flag_type": "bid_shilling",
                    "confidence": min(0.9, 0.5 + len(transactions) * 0.1),
                    "reason": f"Same buyer won {len(transactions)} auctions from this seller totaling ${total_value:,.0f}. Repeated transactions between same parties may indicate collusion.",
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "status": "pending_review",
                    "buyer_id": buyer_id,
                    "buyer_name": (await self._get_user_name(buyer_id)),
                    "transaction_count": len(transactions),
                    "total_value": total_value
                })
        
        return flags
    
    async def _get_user_name(self, user_id: Optional[str]) -> str:
        """Helper to get user name from ID."""
        if not user_id:
            return "Unknown"
        user = await self.db.users.find_one({"id": user_id}, {"name": 1})
        return user.get("name", "Unknown") if user else "Unknown"
    
    async def generate_fraud_summary(self, flag: Dict[str, Any]) -> str:
        """
        Use GPT-4 to generate a human-readable fraud summary.
        """
        if not self.gemini_client:
            return flag.get("reason", "No summary available")
        
        try:
            prompt = f"""Analyze this fraud flag and provide a summary:

Flag Type: {flag.get('flag_type')}
Confidence: {flag.get('confidence', 0) * 100:.0f}%
Auction: {flag.get('auction_title')}
Detection Reason: {flag.get('reason')}

Additional Data:
- Seller: {flag.get('seller_name')}
- Detected: {flag.get('detected_at')}

Provide a brief fraud analysis summary with risk assessment and recommended action. Keep under 150 words. Be specific and actionable."""

            response = self.gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
                config={
                    "system_instruction": "You are an expert fraud analyst for a vehicle auction platform. Analyze the provided fraud flag data and generate a concise, professional summary explaining the suspicious pattern, potential risks, and recommended actions.",
                    "temperature": 0.3,
                    "max_output_tokens": 256,
                }
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating fraud summary: {e}")
            return flag.get("reason", "No summary available")
    
    async def get_flagged_auctions(
        self,
        status: Optional[str] = None,
        flag_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get flagged auctions from database with optional filters.
        """
        query = {}
        if status:
            query["status"] = status
        if flag_type:
            query["flag_type"] = flag_type
        
        flags = await self.db.fraud_flags.find(
            query,
            {"_id": 0}
        ).sort("detected_at", -1).limit(limit).to_list(limit)
        
        return flags
    
    async def save_flag(self, flag: Dict[str, Any]) -> bool:
        """
        Save a fraud flag to the database.
        Sends an email alert to info@bidvex.com when confidence >= 0.90.
        """
        try:
            # Use upsert to avoid duplicates
            await self.db.fraud_flags.update_one(
                {"id": flag.get("id")},
                {"$set": flag},
                upsert=True
            )
            # Trigger email alert for high-risk flags (>= 90%)
            confidence = flag.get("confidence", 0)
            if confidence >= 0.90:
                asyncio.ensure_future(self._send_risk_alert(flag))
            return True
        except Exception as e:
            logger.error(f"Error saving fraud flag: {e}")
            return False

    async def _send_risk_alert(self, flag: Dict[str, Any]):
        """Send a high-risk alert email via SendGrid to info@bidvex.com."""
        try:
            api_key = os.environ.get("SENDGRID_API_KEY", "")
            if not api_key or api_key.startswith("SG.your"):
                logger.info("SendGrid not configured — skipping risk alert email")
                return

            from_email_addr = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com")
            from_name = os.environ.get("SENDGRID_FROM_NAME", "BidVex")
            to_email = os.environ.get("RISK_ALERT_EMAIL", "info@bidvex.com")

            conf_pct = round((flag.get("confidence", 0)) * 100)
            flag_type = (flag.get("flag_type", "unknown")).replace("_", " ").title()
            severity = (flag.get("severity", "high")).upper()
            auction_title = flag.get("auction_title", "Unknown Auction")
            seller = flag.get("seller_name", "Unknown")
            reason = flag.get("reason", "No details available")
            flag_id = flag.get("id", "N/A")
            detected = flag.get("detected_at", datetime.now(timezone.utc).isoformat())

            subject = f"[BidVex ALERT] {severity} Risk Flag — {conf_pct}% Confidence — {flag_type}"

            html = f"""
            <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden">
              <div style="background:linear-gradient(135deg,#dc2626,#ea580c);padding:24px 28px;color:#fff">
                <h1 style="margin:0;font-size:20px">High-Risk Flag Detected</h1>
                <p style="margin:6px 0 0;opacity:0.9;font-size:14px">Confidence: {conf_pct}% &bull; Severity: {severity}</p>
              </div>
              <div style="padding:24px 28px">
                <table style="width:100%;border-collapse:collapse;font-size:14px">
                  <tr><td style="padding:8px 0;color:#64748b;width:130px">Flag Type</td><td style="padding:8px 0;font-weight:600">{flag_type}</td></tr>
                  <tr><td style="padding:8px 0;color:#64748b">Auction</td><td style="padding:8px 0;font-weight:600">{auction_title}</td></tr>
                  <tr><td style="padding:8px 0;color:#64748b">Seller</td><td style="padding:8px 0">{seller}</td></tr>
                  <tr><td style="padding:8px 0;color:#64748b">Reason</td><td style="padding:8px 0">{reason}</td></tr>
                  <tr><td style="padding:8px 0;color:#64748b">Flag ID</td><td style="padding:8px 0;font-family:monospace;font-size:12px">{flag_id}</td></tr>
                  <tr><td style="padding:8px 0;color:#64748b">Detected</td><td style="padding:8px 0">{detected}</td></tr>
                </table>
                <div style="margin-top:20px;padding:14px;background:#fef2f2;border-radius:8px;border-left:4px solid #dc2626">
                  <p style="margin:0;font-size:13px;color:#991b1b"><strong>Action Required:</strong> Review this flag in the Admin Panel under Vehicles &rarr; Risk Monitoring. Clear if it is a false positive, or escalate to investigation.</p>
                </div>
              </div>
              <div style="padding:16px 28px;background:#f8fafc;border-top:1px solid #e2e8f0;text-align:center">
                <p style="margin:0;font-size:12px;color:#94a3b8">BidVex AI Guard &bull; Automated Risk Alert</p>
              </div>
            </div>"""

            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            sg = sendgrid.SendGridAPIClient(api_key=api_key)
            mail = Mail(
                from_email=Email(from_email_addr, from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html),
            )
            sg.client.mail.send.post(request_body=mail.get())
            logger.info(f"Risk alert email sent to {to_email} for flag {flag_id} ({conf_pct}% confidence)")

            # Log the alert in DB
            await self.db.admin_logs.insert_one({
                "id": f"risk-alert-{flag_id}",
                "admin_id": "SYSTEM",
                "admin_email": "system@bidvex.com",
                "action": "risk_alert_email_sent",
                "target_type": "fraud_flag",
                "target_id": flag_id,
                "details": f"High-risk alert ({conf_pct}%) sent to {to_email}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning(f"Failed to send risk alert email: {e}")
    
    async def update_flag_status(
        self,
        flag_id: str,
        new_status: str,
        admin_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update the status of a fraud flag.
        """
        if new_status not in FLAG_STATUSES:
            return False
        
        try:
            update_data = {
                "status": new_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": admin_id
            }
            if notes:
                update_data["admin_notes"] = notes
            
            result = await self.db.fraud_flags.update_one(
                {"id": flag_id},
                {"$set": update_data}
            )
            
            # Log the action
            await self.db.admin_logs.insert_one({
                "id": f"log-{datetime.now().timestamp()}",
                "action": "fraud_flag_update",
                "admin_id": admin_id,
                "flag_id": flag_id,
                "new_status": new_status,
                "notes": notes,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating flag status: {e}")
            return False
    
    async def suspend_auction(self, auction_id: str, admin_id: str, reason: str) -> bool:
        """
        Suspend an auction due to fraud concerns.
        """
        try:
            # Try vehicles collection first
            result = await self.db.vehicles.update_one(
                {"id": auction_id},
                {
                    "$set": {
                        "status": "suspended",
                        "suspended_at": datetime.now(timezone.utc).isoformat(),
                        "suspended_by": admin_id,
                        "suspension_reason": reason
                    }
                }
            )
            
            if result.modified_count == 0:
                # Try listings collection
                result = await self.db.listings.update_one(
                    {"id": auction_id},
                    {
                        "$set": {
                            "status": "suspended",
                            "suspended_at": datetime.now(timezone.utc).isoformat(),
                            "suspended_by": admin_id,
                            "suspension_reason": reason
                        }
                    }
                )
            
            # Log the action
            await self.db.admin_logs.insert_one({
                "id": f"log-{datetime.now().timestamp()}",
                "action": "auction_suspended",
                "admin_id": admin_id,
                "auction_id": auction_id,
                "reason": reason,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error suspending auction: {e}")
            return False


# Singleton instance
_fraud_service = None

def get_fraud_detection_service(db: AsyncIOMotorDatabase) -> FraudDetectionService:
    """Get or create the fraud detection service instance."""
    global _fraud_service
    if _fraud_service is None:
        _fraud_service = FraudDetectionService(db)
    return _fraud_service
