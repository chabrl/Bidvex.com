#!/usr/bin/env node
/**
 * P1 Migration: Extract all keys from i18n.js resource builders into JSON files
 * Then simplify i18n.js to only reference JSON.
 */
const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '../src');
const I18N_PATH = path.resolve(SRC, 'i18n.js');
const EN_PATH = path.resolve(SRC, 'locales/en.json');
const FR_PATH = path.resolve(SRC, 'locales/fr.json');

// Load existing JSON
const enJSON = require(EN_PATH);
const frJSON = require(FR_PATH);

// Read i18n.js source
const src = fs.readFileSync(I18N_PATH, 'utf8');

// Extract builder function body between arrow and closing
function extractBuilderBody(source, fnName) {
  const marker = `const ${fnName} = () => ({`;
  const startIdx = source.indexOf(marker);
  if (startIdx === -1) throw new Error(`Could not find ${fnName}`);
  
  const bodyStart = startIdx + marker.length;
  let depth = 1;
  let i = bodyStart;
  while (i < source.length && depth > 0) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}') depth--;
    i++;
  }
  // i is now after the closing }, go back 1 to exclude it
  return source.substring(bodyStart, i - 1);
}

// Evaluate builder with JSON translations in scope
function evaluateBuilder(body, translations, varName) {
  // The body uses `enTranslations` or `frTranslations` - we pass it as a parameter
  const fn = new Function(varName, `"use strict"; return ({${body}});`);
  return fn(translations);
}

// Deep merge: source into target (target wins for existing leaf values only if source is undefined)
function deepMerge(target, source) {
  for (const key of Object.keys(source)) {
    const sv = source[key];
    const tv = target[key];
    if (sv && typeof sv === 'object' && !Array.isArray(sv)) {
      if (!tv || typeof tv !== 'object') {
        target[key] = {};
      }
      deepMerge(target[key], sv);
    } else if (tv === undefined || tv === null) {
      // Only add if target doesn't already have the key
      target[key] = sv;
    } else {
      // Source has a value, keep it (it's the built value)
      target[key] = sv;
    }
  }
  return target;
}

try {
  console.log('Extracting English resources...');
  const enBody = extractBuilderBody(src, 'buildEnglishResources');
  const enResources = evaluateBuilder(enBody, enJSON, 'enTranslations');
  
  console.log('Extracting French resources...');
  const frBody = extractBuilderBody(src, 'buildFrenchResources');
  const frResources = evaluateBuilder(frBody, frJSON, 'frTranslations');

  // Count keys
  function countKeys(obj, prefix = '') {
    let count = 0;
    for (const [k, v] of Object.entries(obj)) {
      if (v && typeof v === 'object' && !Array.isArray(v)) {
        count += countKeys(v, prefix + k + '.');
      } else {
        count++;
      }
    }
    return count;
  }

  const enBefore = countKeys(enJSON);
  const frBefore = countKeys(frJSON);

  // Deep merge built resources into JSON (built resources take priority)
  const mergedEn = deepMerge({}, enResources);
  const mergedFr = deepMerge({}, frResources);

  const enAfter = countKeys(mergedEn);
  const frAfter = countKeys(mergedFr);

  console.log(`EN: ${enBefore} -> ${enAfter} keys (+${enAfter - enBefore})`);
  console.log(`FR: ${frBefore} -> ${frAfter} keys (+${frAfter - frBefore})`);

  // Write updated JSON
  fs.writeFileSync(EN_PATH, JSON.stringify(mergedEn, null, 2) + '\n', 'utf8');
  fs.writeFileSync(FR_PATH, JSON.stringify(mergedFr, null, 2) + '\n', 'utf8');

  console.log('\nJSON files updated successfully.');
  console.log('Now rewrite i18n.js to reference JSON only.');
} catch (err) {
  console.error('Migration failed:', err.message);
  console.error(err.stack);
  process.exit(1);
}
