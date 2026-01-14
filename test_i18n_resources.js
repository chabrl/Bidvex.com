// Simple Node.js script to test if i18n resources are properly configured
const i18n = require('./frontend/src/i18n.js').default;

console.log('=== i18n Configuration Test ===\n');

// Check if i18n is initialized
console.log('1. i18n initialized:', !!i18n);
console.log('2. Current language:', i18n.language);
console.log('3. Supported languages:', i18n.languages);

// Check if French resources exist
console.log('\n4. Has French bundle:', i18n.hasResourceBundle('fr', 'translation'));
console.log('5. Has English bundle:', i18n.hasResourceBundle('en', 'translation'));

// Try to get specific French translations
console.log('\n6. Testing French translations:');
console.log('   - createListing.title (EN):', i18n.t('createListing.title', { lng: 'en' }));
console.log('   - createListing.title (FR):', i18n.t('createListing.title', { lng: 'fr' }));
console.log('   - affiliate.dashboard (EN):', i18n.t('affiliate.dashboard', { lng: 'en' }));
console.log('   - affiliate.dashboard (FR):', i18n.t('affiliate.dashboard', { lng: 'fr' }));

// Check if resources are in store
console.log('\n7. French resources in store:');
const frResources = i18n.getResourceBundle('fr', 'translation');
if (frResources) {
  console.log('   - Has createListing:', !!frResources.createListing);
  console.log('   - Has affiliate:', !!frResources.affiliate);
  if (frResources.createListing) {
    console.log('   - createListing.title:', frResources.createListing.title);
  }
  if (frResources.affiliate) {
    console.log('   - affiliate.dashboard:', frResources.affiliate.dashboard);
  }
} else {
  console.log('   ❌ No French resources found in bundle!');
}

console.log('\n=== Test Complete ===');
