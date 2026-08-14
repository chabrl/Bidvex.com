"""Resend ONLY the invoice_templates.py PDF batch (Delivery #43 replacement)
   after commission_invoice_template fixture fix + weasyprint installation.
   Same safeguards apply — only charbel911@gmail.com is addressed."""
import asyncio, sys, os
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
from dotenv import load_dotenv
load_dotenv(os.path.join(_BACKEND, ".env"), override=False)

from tests.iter482 import billing_visual_qa_delivery as qa

async def main():
    qa.install_safety_wrapper()
    await qa.deliver_pdf_variants()
    print(f"Resent {len(qa._DELIVERY_LOG)} messages")
    for row in qa._DELIVERY_LOG:
        print(f"  {row['result']:<10} {row['subject'][:120]}  attachments={row['attachments']}")

asyncio.run(main())
