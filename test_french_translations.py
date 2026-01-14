#!/usr/bin/env python3
"""
French Translation Testing for CreateMultiItemListing and AffiliateDashboard
Tests that I18nextProvider wrapper and forced language reload are working correctly.
"""

import asyncio
import re
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from datetime import datetime
from typing import Dict, List, Tuple

# Configuration
BASE_URL = "https://launchapp-4.preview.emergentagent.com"
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

class FrenchTranslationTester:
    def __init__(self):
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.console_logs: List[str] = []
        self.test_results = {}
        
    async def setup_browser(self):
        """Initialize Playwright browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='fr-FR'
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(60000)  # 60 second timeout
        
        # Capture console logs
        def handle_console(msg):
            try:
                self.console_logs.append(f"[{msg.type}] {msg.text}")
            except:
                pass
        self.page.on('console', handle_console)
        
    async def cleanup_browser(self):
        """Cleanup browser resources"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
            
    async def set_french_language(self):
        """Set localStorage to French language"""
        await self.page.evaluate("""
            () => {
                localStorage.setItem('bidvex_language', 'fr');
                localStorage.setItem('i18nextLng', 'fr');
            }
        """)
        print("✅ Set localStorage: bidvex_language='fr', i18nextLng='fr'")
        
    async def login_as_admin(self):
        """Login as admin user"""
        try:
            print(f"\n🔐 Logging in as admin: {ADMIN_EMAIL}")
            
            # Navigate to login page
            await self.page.goto(f"{BASE_URL}/auth", wait_until='load', timeout=60000)
            await self.page.wait_for_timeout(3000)
            
            # Fill login form
            await self.page.fill('input[type="email"]', ADMIN_EMAIL)
            await self.page.fill('input[type="password"]', ADMIN_PASSWORD)
            
            # Click login button
            await self.page.click('button[type="submit"]')
            await self.page.wait_for_timeout(3000)
            
            # Verify login success by checking URL or presence of user menu
            current_url = self.page.url
            if '/auth' not in current_url:
                print(f"✅ Admin login successful")
                return True
            else:
                print(f"❌ Admin login failed - still on auth page")
                return False
                
        except Exception as e:
            print(f"❌ Error during admin login: {str(e)}")
            return False
            
    async def count_french_text_percentage(self, page_html: str, expected_french_phrases: List[str]) -> Tuple[float, List[str], List[str]]:
        """
        Count percentage of French text on page.
        Returns: (percentage, found_phrases, missing_phrases)
        """
        found_phrases = []
        missing_phrases = []
        
        for phrase in expected_french_phrases:
            if phrase.lower() in page_html.lower():
                found_phrases.append(phrase)
            else:
                missing_phrases.append(phrase)
        
        if len(expected_french_phrases) > 0:
            percentage = (len(found_phrases) / len(expected_french_phrases)) * 100
        else:
            percentage = 0.0
            
        return percentage, found_phrases, missing_phrases
        
    async def test_create_multi_item_listing_french(self) -> Dict:
        """Test CreateMultiItemListing page French translation"""
        print("\n" + "="*70)
        print("🧪 Testing CreateMultiItemListing French Display")
        print("="*70)
        
        result = {
            "page": "CreateMultiItemListing",
            "success": False,
            "french_percentage": 0.0,
            "found_phrases": [],
            "missing_phrases": [],
            "console_logs": [],
            "screenshot": None
        }
        
        try:
            # Clear console logs
            self.console_logs = []
            
            # Navigate to create-multi-item-listing
            print(f"📍 Navigating to {BASE_URL}/create-multi-item-listing")
            await self.page.goto(f"{BASE_URL}/create-multi-item-listing", wait_until='networkidle')
            await self.page.wait_for_timeout(3000)
            
            # Get page HTML
            page_html = await self.page.content()
            
            # Expected French phrases
            expected_french_phrases = [
                "Créer une Enchère Multi-Lots",
                "Titre de l'Enchère",
                "Info de Base",
                "Suivant",
                "Description",
                "Catégorie",
                "Ville",
                "Province/État",
                "Emplacement",
                "Date de Fin d'Enchère",
                "Devise",
                "Retour"
            ]
            
            # Count French text percentage
            percentage, found, missing = await self.count_french_text_percentage(page_html, expected_french_phrases)
            
            result["french_percentage"] = percentage
            result["found_phrases"] = found
            result["missing_phrases"] = missing
            
            # Check for specific French text
            print(f"\n📊 French Translation Coverage: {percentage:.1f}%")
            print(f"✅ Found {len(found)} French phrases:")
            for phrase in found:
                print(f"   - {phrase}")
            
            if missing:
                print(f"\n❌ Missing {len(missing)} French phrases:")
                for phrase in missing:
                    print(f"   - {phrase}")
            
            # Check console logs for debug messages
            i18n_logs = [log for log in self.console_logs if 'CreateMultiItemListing' in log or 'i18n' in log.lower() or 'language' in log.lower()]
            result["console_logs"] = i18n_logs
            
            print(f"\n📝 Console Logs (i18n related):")
            if i18n_logs:
                for log in i18n_logs:
                    print(f"   {log}")
            else:
                print("   No i18n-related console logs found")
            
            # Check for specific debug logs
            force_reload_log = any("[CreateMultiItemListing] Forcing language reload" in log for log in self.console_logs)
            language_changed_log = any("[CreateMultiItemListing] Language changed successfully" in log for log in self.console_logs)
            
            if force_reload_log:
                print("✅ Found: [CreateMultiItemListing] Forcing language reload")
            else:
                print("❌ Missing: [CreateMultiItemListing] Forcing language reload")
                
            if language_changed_log:
                print("✅ Found: [CreateMultiItemListing] Language changed successfully")
            
            # Take screenshot
            screenshot_path = f"/app/screenshots/create_multi_item_listing_french_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=screenshot_path, full_page=True)
            result["screenshot"] = screenshot_path
            print(f"📸 Screenshot saved: {screenshot_path}")
            
            # Determine success (85%+ coverage required)
            result["success"] = percentage >= 85.0
            
            if result["success"]:
                print(f"\n✅ CreateMultiItemListing French translation: PASS ({percentage:.1f}% >= 85%)")
            else:
                print(f"\n❌ CreateMultiItemListing French translation: FAIL ({percentage:.1f}% < 85%)")
            
            return result
            
        except Exception as e:
            print(f"❌ Error testing CreateMultiItemListing: {str(e)}")
            result["error"] = str(e)
            return result
            
    async def test_affiliate_dashboard_french(self) -> Dict:
        """Test AffiliateDashboard page French translation"""
        print("\n" + "="*70)
        print("🧪 Testing AffiliateDashboard French Display")
        print("="*70)
        
        result = {
            "page": "AffiliateDashboard",
            "success": False,
            "french_percentage": 0.0,
            "found_phrases": [],
            "missing_phrases": [],
            "console_logs": [],
            "screenshot": None
        }
        
        try:
            # Clear console logs
            self.console_logs = []
            
            # Navigate to affiliate dashboard
            print(f"📍 Navigating to {BASE_URL}/affiliate")
            await self.page.goto(f"{BASE_URL}/affiliate", wait_until='networkidle')
            await self.page.wait_for_timeout(3000)
            
            # Get page HTML
            page_html = await self.page.content()
            
            # Expected French phrases
            expected_french_phrases = [
                "Tableau de Bord Affilié",
                "Total de Clics",
                "Commission en Attente",
                "Commission Payée",
                "Votre Lien de Parrainage",
                "Copier le Lien",
                "Partager sur",
                "Parrainages",
                "Demander Paiement",
                "Conversions"
            ]
            
            # Count French text percentage
            percentage, found, missing = await self.count_french_text_percentage(page_html, expected_french_phrases)
            
            result["french_percentage"] = percentage
            result["found_phrases"] = found
            result["missing_phrases"] = missing
            
            # Check for specific French text
            print(f"\n📊 French Translation Coverage: {percentage:.1f}%")
            print(f"✅ Found {len(found)} French phrases:")
            for phrase in found:
                print(f"   - {phrase}")
            
            if missing:
                print(f"\n❌ Missing {len(missing)} French phrases:")
                for phrase in missing:
                    print(f"   - {phrase}")
            
            # Check console logs for debug messages
            i18n_logs = [log for log in self.console_logs if 'AffiliateDashboard' in log or 'i18n' in log.lower() or 'language' in log.lower()]
            result["console_logs"] = i18n_logs
            
            print(f"\n📝 Console Logs (i18n related):")
            if i18n_logs:
                for log in i18n_logs:
                    print(f"   {log}")
            else:
                print("   No i18n-related console logs found")
            
            # Check for specific debug logs
            force_reload_log = any("[AffiliateDashboard] Forcing language reload" in log for log in self.console_logs)
            language_changed_log = any("[AffiliateDashboard] Language changed successfully" in log for log in self.console_logs)
            
            if force_reload_log:
                print("✅ Found: [AffiliateDashboard] Forcing language reload")
            else:
                print("❌ Missing: [AffiliateDashboard] Forcing language reload")
                
            if language_changed_log:
                print("✅ Found: [AffiliateDashboard] Language changed successfully")
            
            # Take screenshot
            screenshot_path = f"/app/screenshots/affiliate_dashboard_french_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.page.screenshot(path=screenshot_path, full_page=True)
            result["screenshot"] = screenshot_path
            print(f"📸 Screenshot saved: {screenshot_path}")
            
            # Determine success (100% coverage required)
            result["success"] = percentage >= 100.0
            
            if result["success"]:
                print(f"\n✅ AffiliateDashboard French translation: PASS ({percentage:.1f}% = 100%)")
            else:
                print(f"\n❌ AffiliateDashboard French translation: FAIL ({percentage:.1f}% < 100%)")
            
            return result
            
        except Exception as e:
            print(f"❌ Error testing AffiliateDashboard: {str(e)}")
            result["error"] = str(e)
            return result
            
    async def run_all_tests(self):
        """Run all French translation tests"""
        print("🚀 Starting French Translation Tests")
        print("=" * 70)
        print(f"Target URL: {BASE_URL}")
        print(f"Admin User: {ADMIN_EMAIL}")
        print("=" * 70)
        
        await self.setup_browser()
        
        try:
            # Navigate to homepage first
            await self.page.goto(BASE_URL, wait_until='load', timeout=60000)
            await self.page.wait_for_timeout(3000)
            
            # Set French language in localStorage
            await self.set_french_language()
            
            # Reload page to apply language
            await self.page.reload(wait_until='load', timeout=60000)
            await self.page.wait_for_timeout(3000)
            
            # Login as admin
            if not await self.login_as_admin():
                print("❌ Failed to login as admin - aborting tests")
                return False
            
            # Re-set French language after login (in case login cleared it)
            await self.set_french_language()
            await self.page.wait_for_timeout(1000)
            
            # Run tests
            create_listing_result = await self.test_create_multi_item_listing_french()
            affiliate_result = await self.test_affiliate_dashboard_french()
            
            # Store results
            self.test_results["CreateMultiItemListing"] = create_listing_result
            self.test_results["AffiliateDashboard"] = affiliate_result
            
            # Print summary
            print("\n" + "=" * 70)
            print("📊 FRENCH TRANSLATION TEST RESULTS SUMMARY")
            print("=" * 70)
            
            print(f"\n1. CreateMultiItemListing:")
            print(f"   - French Coverage: {create_listing_result['french_percentage']:.1f}%")
            print(f"   - Required: 85%+")
            print(f"   - Status: {'✅ PASS' if create_listing_result['success'] else '❌ FAIL'}")
            print(f"   - Found Phrases: {len(create_listing_result['found_phrases'])}/{len(create_listing_result['found_phrases']) + len(create_listing_result['missing_phrases'])}")
            
            print(f"\n2. AffiliateDashboard:")
            print(f"   - French Coverage: {affiliate_result['french_percentage']:.1f}%")
            print(f"   - Required: 100%")
            print(f"   - Status: {'✅ PASS' if affiliate_result['success'] else '❌ FAIL'}")
            print(f"   - Found Phrases: {len(affiliate_result['found_phrases'])}/{len(affiliate_result['found_phrases']) + len(affiliate_result['missing_phrases'])}")
            
            # Overall result
            all_passed = create_listing_result['success'] and affiliate_result['success']
            
            print("\n" + "=" * 70)
            if all_passed:
                print("🎉 All French translation tests PASSED!")
                print("=" * 70)
                return True
            else:
                print("⚠️  Some French translation tests FAILED")
                print("=" * 70)
                return False
                
        finally:
            await self.cleanup_browser()

async def main():
    """Main test runner"""
    tester = FrenchTranslationTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
