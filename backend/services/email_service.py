"""
BidVex Email Service - SendGrid Integration

Provides a scalable, production-ready email system with:
- SendGrid Dynamic Templates
- Bilingual support (EN/FR)
- Retry logic with exponential backoff
- Event tracking via webhooks
- Comprehensive error logging

Usage:
    from services.email_service import EmailService
    
    email_service = EmailService()
    await email_service.send_email(
        to='user@example.com',
        template_id='d-xxxxx',
        dynamic_data={'name': 'John', 'amount': 100},
        language='en'
    )
"""

import os
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from python_http_client.exceptions import HTTPError

# Configure logging
logger = logging.getLogger(__name__)


class EmailService:
    """
    Production-grade email service using SendGrid.
    Supports dynamic templates, bilingual content, and event tracking.
    """
    
    def __init__(self):
        self.api_key = os.environ.get('SENDGRID_API_KEY')
        self.from_email = os.environ.get('SENDGRID_FROM_EMAIL', 'support@bidvex.com')
        self.from_name = os.environ.get('SENDGRID_FROM_NAME', 'BidVex Auctions')
        
        if not self.api_key:
            logger.warning(
                "SENDGRID_API_KEY not configured. Email service will be disabled. "
                "Set SENDGRID_API_KEY in environment variables to enable emails."
            )
            self.client = None
        else:
            self.client = SendGridAPIClient(self.api_key)
            logger.info("SendGrid email service initialized successfully")
    
    def is_configured(self) -> bool:
        """Check if SendGrid is properly configured."""
        return self.client is not None
    
    async def send_email(
        self,
        to: str,
        template_id: str,
        dynamic_data: Dict[str, Any],
        language: str = 'en',
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Send email using SendGrid Dynamic Template.
        
        Args:
            to: Recipient email address
            template_id: SendGrid dynamic template ID
            dynamic_data: Variables for template substitution
            language: Language code ('en' or 'fr')
            cc: Optional CC recipients
            bcc: Optional BCC recipients
            reply_to: Optional reply-to address
            max_retries: Maximum retry attempts (default: 3)
            
        Returns:
            Dict with status and message_id
            
        Raises:
            Exception: If email fails after all retries
        """
        if not self.is_configured():
            logger.error(f"Email send failed: SendGrid not configured. Recipient: {to}")
            return {
                "success": False,
                "error": "Email service not configured",
                "message_id": None
            }
        
        # Add language to dynamic data for template selection
        dynamic_data['language'] = language
        dynamic_data['current_year'] = datetime.now().year
        
        # Build message
        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to)
        )
        
        # Set template ID
        message.template_id = template_id
        
        # Add dynamic template data
        message.dynamic_template_data = dynamic_data
        
        # Add CC/BCC if provided
        if cc:
            for cc_email in cc:
                message.add_cc(cc_email)
        if bcc:
            for bcc_email in bcc:
                message.add_bcc(bcc_email)
        
        # Set reply-to
        if reply_to:
            message.reply_to = Email(reply_to)
        
        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                response = self.client.send(message)
                
                logger.info(
                    f"Email sent successfully: to={to}, template={template_id}, "
                    f"status={response.status_code}, message_id={response.headers.get('X-Message-Id')}"
                )
                
                return {
                    "success": True,
                    "message_id": response.headers.get('X-Message-Id'),
                    "status_code": response.status_code
                }
                
            except HTTPError as e:
                error_body = e.body if hasattr(e, 'body') else str(e)
                logger.error(
                    f"SendGrid HTTP error (attempt {attempt + 1}/{max_retries}): "
                    f"to={to}, error={error_body}"
                )
                
                # If final attempt, raise exception
                if attempt == max_retries - 1:
                    # Notify admin of failed email
                    await self._notify_admin_of_failure(to, template_id, error_body)
                    return {
                        "success": False,
                        "error": str(error_body),
                        "message_id": None
                    }
                
                # Exponential backoff: 1s, 2s, 4s
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                logger.exception(f"Unexpected email error: to={to}, error={str(e)}")
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": str(e),
                        "message_id": None
                    }
                await asyncio.sleep(2 ** attempt)
    
    async def send_bulk_email(
        self,
        recipients: List[Dict[str, Any]],
        template_id: str,
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Send bulk emails with personalized data for each recipient.
        
        Args:
            recipients: List of dicts with 'email' and 'data' keys
            template_id: SendGrid template ID
            language: Default language
            
        Returns:
            Dict with success/failure counts
        """
        results = {
            "total": len(recipients),
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        for recipient in recipients:
            email = recipient.get('email')
            data = recipient.get('data', {})
            
            result = await self.send_email(
                to=email,
                template_id=template_id,
                dynamic_data=data,
                language=language
            )
            
            if result['success']:
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'email': email,
                    'error': result.get('error')
                })
        
        logger.info(
            f"Bulk email completed: total={results['total']}, "
            f"success={results['success']}, failed={results['failed']}"
        )
        
        return results
    
    async def _notify_admin_of_failure(
        self,
        recipient: str,
        template_id: str,
        error: str
    ) -> None:
        """
        Send notification to admin about email delivery failure.
        """
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@bidvex.com')
        
        try:
            # Simple text email to admin (not using template)
            message = Mail(
                from_email=Email(self.from_email, 'BidVex System'),
                to_emails=To(admin_email),
                subject=f'[BidVex] Email Delivery Failure',
                plain_text_content=Content(
                    'text/plain',
                    "Failed to send email after multiple retries.\n\n"
                    f"Recipient: {recipient}\n"
                    f"Template ID: {template_id}\n"
                    f"Error: {error}\n"
                    f"Time: {datetime.now().isoformat()}"
                )
            )
            
            self.client.send(message)
            logger.info(f"Admin notified of email failure for {recipient}")
        except Exception as e:
            logger.error(f"Failed to notify admin: {str(e)}")


# Singleton instance
_email_service = None

def get_email_service() -> EmailService:
    """
    Get or create the singleton email service instance.
    """
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
