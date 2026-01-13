#!/usr/bin/env python3
"""
Seed Bilingual Legal Pages (EN/FR) to MongoDB
Populates Privacy Policy and Terms & Conditions in both English and French
"""
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / 'backend' / '.env')

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'bazario_db')

# Shared CSS for all legal pages
LEGAL_PAGE_CSS = """
<style>
  .legal-page-content { font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; color: #0f172a; }
  .legal-section { margin-bottom: 2rem; }
  .section-header { font-size: 1.5rem; font-weight: bold; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
  .colored-box { padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem; border: 2px solid; }
  .blue-box { background-color: #eff6ff; border-color: #3b82f6; }
  .green-box { background-color: #f0fdf4; border-color: #22c55e; }
  .red-box { background-color: #fef2f2; border-color: #ef4444; }
  .purple-box { background-color: #faf5ff; border-color: #a855f7; }
  .amber-box { background-color: #fffbeb; border-color: #f59e0b; }
  .cyan-box { background-color: #ecfeff; border-color: #06b6d4; }
  .slate-box { background-color: #f8fafc; border-color: #64748b; }
  .indigo-box { background-color: #eef2ff; border-color: #6366f1; }
  .highlight-box { background-color: #dcfce7; border: 2px solid #22c55e; padding: 1rem; border-radius: 0.5rem; margin: 1rem 0; }
  .data-tier { margin-bottom: 1rem; }
  .data-tier h3 { font-weight: bold; margin-bottom: 0.5rem; }
  .data-tier ul { list-style-type: disc; margin-left: 2rem; }
  .rights-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin: 1rem 0; }
  .right-card { background: white; padding: 1rem; border-radius: 0.5rem; border: 1px solid #e2e8f0; }
  .cookie-table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
  .cookie-table th, .cookie-table td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
  .cookie-table th { background-color: #fef3c7; font-weight: bold; }
  .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; font-weight: 600; }
  .badge-green { background-color: #dcfce7; color: #166534; }
  .badge-blue { background-color: #dbeafe; color: #1e40af; }
  .deletion-button { display: inline-block; background-color: #dc2626; color: white; padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-weight: bold; text-decoration: none; margin-top: 1rem; }
  .contact-card { background: white; padding: 1.5rem; border-radius: 0.5rem; border: 2px solid #818cf8; }
  .fee-percentage { font-size: 1.5rem; font-weight: bold; color: #1d4ed8; }
  .fee-percentage-green { font-size: 1.5rem; font-weight: bold; color: #16a34a; }
  .fee-percentage-red { font-size: 1.5rem; font-weight: bold; color: #dc2626; }
  .binding-box { background-color: #ede9fe; border: 2px solid #a855f7; padding: 1rem; border-radius: 0.5rem; margin: 1rem 0; }
  @media (max-width: 768px) { .rights-grid { grid-template-columns: 1fr; } }
</style>
"""

async def seed_legal_pages():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("🔍 Checking existing legal pages configuration...")
    
    # Check if legal pages already exist
    existing = await db.site_config.find_one({"type": "legal_pages"})
    
    # Import content from separate modules
    from legal_content_en import PRIVACY_POLICY_EN, TERMS_CONDITIONS_EN
    from legal_content_fr import PRIVACY_POLICY_FR, TERMS_CONDITIONS_FR
    
    legal_pages_config = {
        "type": "legal_pages",
        "pages": {
            "privacy_policy": {
                "en": {
                    "title": "Privacy Policy",
                    "content": f"<div class='legal-page-content'>{LEGAL_PAGE_CSS}{PRIVACY_POLICY_EN}</div>",
                    "link_type": "page",
                    "link_value": "/privacy-policy"
                },
                "fr": {
                    "title": "Politique de confidentialité",
                    "content": f"<div class='legal-page-content'>{LEGAL_PAGE_CSS}{PRIVACY_POLICY_FR}</div>",
                    "link_type": "page",
                    "link_value": "/privacy-policy"
                }
            },
            "terms_of_service": {
                "en": {
                    "title": "Terms & Conditions",
                    "content": f"<div class='legal-page-content'>{LEGAL_PAGE_CSS}{TERMS_CONDITIONS_EN}</div>",
                    "link_type": "page",
                    "link_value": "/terms-of-service"
                },
                "fr": {
                    "title": "Conditions d'utilisation",
                    "content": f"<div class='legal-page-content'>{LEGAL_PAGE_CSS}{TERMS_CONDITIONS_FR}</div>",
                    "link_type": "page",
                    "link_value": "/terms-of-service"
                }
            }
        },
        "updated_at": datetime.utcnow(),
        "updated_by": "system",
        "updated_by_email": "system@bidvex.com",
        "seeded": True
    }
    
    if existing:
        print("⚠️  Legal pages already exist. Updating with bilingual content...")
        await db.site_config.update_one(
            {"type": "legal_pages"},
            {"$set": legal_pages_config}
        )
        print("✅ Legal pages updated with EN/FR versions!")
    else:
        print("📝 Creating new bilingual legal pages...")
        await db.site_config.insert_one(legal_pages_config)
        print("✅ Bilingual legal pages created!")
    
    print("\n📊 Summary:")
    print("   - Privacy Policy: ✅ English + Français")
    print("   - Terms & Conditions: ✅ English + Français")
    print("   - Admin Panel: ✅ Both languages editable")
    print("\n🎉 Bilingual legal pages ready!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_legal_pages())
