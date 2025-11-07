"""
Mock Email Service for BidVex Invoice System
Logs email operations instead of sending real emails
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class MockEmailService:
    """
    Mock email service that logs email operations to console and database
    Replace with SendGrid when API key is provided
    """
    
    def __init__(self, db=None):
        self.db = db
        self.sent_emails = []
    
    async def send_buyer_invoice_email(
        self,
        recipient_email: str,
        recipient_name: str,
        auction_title: str,
        invoice_number: str,
        total_due: float,
        paddle_number: int,
        pdf_paths: Dict[str, str],
        lang: str = "en"
    ) -> bool:
        """
        Send email to buyer with invoice PDFs
        
        Args:
            recipient_email: Buyer's email
            recipient_name: Buyer's name
            auction_title: Auction title
            invoice_number: Invoice number
            total_due: Total amount due
            paddle_number: Buyer's paddle number
            pdf_paths: Dict of PDF paths {'lots_won': path, 'payment_letter': path}
            lang: Language code ('en' or 'fr')
        
        Returns:
            True if email logged successfully
        """
        
        # Email subject
        subject = {
            "en": f"Your Auction Invoice #{invoice_number} - Payment Required",
            "fr": f"Votre facture d'enchère #{invoice_number} - Paiement requis"
        }.get(lang, f"Your Auction Invoice #{invoice_number} - Payment Required")
        
        # Email body
        body = self._generate_buyer_email_body(
            recipient_name, auction_title, invoice_number,
            total_due, paddle_number, lang
        )
        
        # Log email
        email_log = {
            "type": "buyer_invoice",
            "recipient": recipient_email,
            "subject": subject,
            "body": body,
            "attachments": list(pdf_paths.values()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "auction_title": auction_title,
            "invoice_number": invoice_number,
            "status": "mock_sent"
        }
        
        self.sent_emails.append(email_log)
        
        # Log to database
        if self.db is not None:
            await self.db.email_logs.insert_one(email_log)
        
        # Log to console
        logger.info(f"📧 [MOCK EMAIL] Buyer Invoice")
        logger.info(f"   To: {recipient_email}")
        logger.info(f"   Subject: {subject}")
        logger.info(f"   Attachments: {len(pdf_paths)} PDFs")
        logger.info(f"   Invoice: {invoice_number}")
        logger.info(f"   Total Due: ${total_due:.2f} CAD")
        logger.info(f"---")
        
        return True
    
    async def send_seller_documents_email(
        self,
        recipient_email: str,
        recipient_name: str,
        auction_title: str,
        total_hammer: float,
        lots_sold: int,
        net_payout: float,
        pdf_paths: Dict[str, str],
        lang: str = "en"
    ) -> bool:
        """
        Send email to seller with auction documents
        
        Args:
            recipient_email: Seller's email
            recipient_name: Seller's name
            auction_title: Auction title
            total_hammer: Total hammer value
            lots_sold: Number of lots sold
            net_payout: Net payout amount
            pdf_paths: Dict of PDF paths {'statement': path, 'receipt': path, 'commission': path}
            lang: Language code ('en' or 'fr')
        
        Returns:
            True if email logged successfully
        """
        
        # Email subject
        subject = {
            "en": f"Your Auction Results - {auction_title}",
            "fr": f"Vos résultats d'enchère - {auction_title}"
        }.get(lang, f"Your Auction Results - {auction_title}")
        
        # Email body
        body = self._generate_seller_email_body(
            recipient_name, auction_title, total_hammer,
            lots_sold, net_payout, lang
        )
        
        # Log email
        email_log = {
            "type": "seller_documents",
            "recipient": recipient_email,
            "subject": subject,
            "body": body,
            "attachments": list(pdf_paths.values()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "auction_title": auction_title,
            "total_hammer": total_hammer,
            "lots_sold": lots_sold,
            "net_payout": net_payout,
            "status": "mock_sent"
        }
        
        self.sent_emails.append(email_log)
        
        # Log to database
        if self.db is not None:
            await self.db.email_logs.insert_one(email_log)
        
        # Log to console
        logger.info(f"📧 [MOCK EMAIL] Seller Documents")
        logger.info(f"   To: {recipient_email}")
        logger.info(f"   Subject: {subject}")
        logger.info(f"   Attachments: {len(pdf_paths)} PDFs")
        logger.info(f"   Auction: {auction_title}")
        logger.info(f"   Lots Sold: {lots_sold}")
        logger.info(f"   Net Payout: ${net_payout:.2f} CAD")
        logger.info(f"---")
        
        return True
    
    def _generate_buyer_email_body(
        self,
        name: str,
        auction_title: str,
        invoice_number: str,
        total_due: float,
        paddle_number: int,
        lang: str = "en"
    ) -> str:
        """Generate buyer email body"""
        
        if lang == "fr":
            return f"""
Cher {name.split()[0]},

Félicitations pour vos enchères réussies!

Vous avez remporté des lots lors de l'enchère "{auction_title}".

DÉTAILS DE PAIEMENT:
- Numéro de facture: {invoice_number}
- Numéro de palette: {paddle_number}
- Montant total dû: ${total_due:.2f} CAD

PAIEMENT REQUIS EN DEUX PARTIES:
Veuillez consulter vos documents joints pour les instructions de paiement détaillées.

Si vous avez des questions, n'hésitez pas à nous contacter.

Cordialement,
L'équipe BidVex
support@bidvex.com
"""
        
        return f"""
Dear {name.split()[0]},

Congratulations on your successful bids!

You have won lots at the "{auction_title}" auction.

PAYMENT DETAILS:
- Invoice Number: {invoice_number}
- Paddle Number: {paddle_number}
- Total Amount Due: ${total_due:.2f} CAD

TWO-PART PAYMENT REQUIRED:
Please refer to your attached documents for detailed payment instructions.

If you have any questions, please don't hesitate to contact us.

Sincerely,
The BidVex Team
support@bidvex.com
"""
    
    def _generate_seller_email_body(
        self,
        name: str,
        auction_title: str,
        total_hammer: float,
        lots_sold: int,
        net_payout: float,
        lang: str = "en"
    ) -> str:
        """Generate seller email body"""
        
        if lang == "fr":
            return f"""
Cher {name.split()[0]},

Votre enchère "{auction_title}" est maintenant terminée.

RÉSULTATS DE L'ENCHÈRE:
- Lots vendus: {lots_sold}
- Valeur totale du marteau: ${total_hammer:.2f} CAD
- Paiement net: ${net_payout:.2f} CAD

📢 POLITIQUE DE COMMISSION ZÉRO:
Aucune commission n'est facturée pour cette enchère. Vous recevrez 100% de la valeur du marteau.

Vos documents d'enchère sont joints, comprenant:
- Relevé du vendeur
- Reçu du vendeur
- Facture de commission (montrant 0% de commission)

Votre paiement sera transféré dans les 5 à 7 jours ouvrables.

Si vous avez des questions, n'hésitez pas à nous contacter.

Cordialement,
L'équipe BidVex
support@bidvex.com
"""
        
        return f"""
Dear {name.split()[0]},

Your auction "{auction_title}" has now concluded.

AUCTION RESULTS:
- Lots Sold: {lots_sold}
- Total Hammer Value: ${total_hammer:.2f} CAD
- Net Payout: ${net_payout:.2f} CAD

📢 ZERO COMMISSION POLICY:
No commission is charged for this auction. You will receive 100% of the hammer value.

Your auction documents are attached, including:
- Seller Statement
- Seller Receipt
- Commission Invoice (showing 0% commission)

Your payout will be transferred within 5-7 business days.

If you have any questions, please don't hesitate to contact us.

Sincerely,
The BidVex Team
support@bidvex.com
"""
    
    async def get_sent_emails(self) -> List[Dict[str, Any]]:
        """Get list of all logged emails"""
        if self.db is not None:
            emails = await self.db.email_logs.find({}, {"_id": 0}).to_list(100)
            return emails
        return self.sent_emails
