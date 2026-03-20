#!/usr/bin/env node

/**
 * BidVex i18n Audit Script
 * Scans the frontend codebase for translation issues:
 * 1. Hardcoded English strings in JSX
 * 2. Missing translation keys (used in code but absent from JSON)
 * 3. Unused translation keys (in JSON but never referenced)
 * 4. EN/FR sync check (keys present in one but not the other)
 */

const fs = require('fs');
const path = require('path');

const SRC_DIR = path.resolve(__dirname, '../src');
const EN_PATH = path.resolve(SRC_DIR, 'locales/en.json');
const FR_PATH = path.resolve(SRC_DIR, 'locales/fr.json');
const REPORT_PATH = path.resolve(__dirname, 'i18n-report.txt');

// Files/dirs to skip entirely
const SKIP_DIRS = ['node_modules', '.git', 'locales', '__tests__', 'test', 'components/ui'];
const SKIP_FILES = ['i18n.js', 'reportWebVitals.js', 'setupTests.js', 'serviceWorker.js', 'PrivacyEN.jsx', 'PrivacyFR.jsx', 'TermsEN.jsx', 'TermsFR.jsx'];

// ─── Utility: recursively collect .js/.jsx files ───
function collectFiles(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.some(s => full.includes(path.sep + s) || full.endsWith(path.sep + s))) {
        collectFiles(full, files);
      }
    } else if (/\.(js|jsx|ts|tsx)$/.test(entry.name) && !SKIP_FILES.includes(entry.name)) {
      files.push(full);
    }
  }
  return files;
}

// ─── Utility: flatten nested JSON to dot-notation keys ───
function flattenKeys(obj, prefix = '') {
  const keys = [];
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      keys.push(...flattenKeys(v, key));
    } else {
      keys.push(key);
    }
  }
  return keys;
}

// ─── 1. Extract all t() key usages from source files ───
function extractTKeys(files) {
  // Matches t('key'), t("key"), t('key', ...), t("key", ...)
  // Deliberately excludes template literals with ${} (dynamic keys)
  const tCallRegex = /\bt\(\s*['"]([^'"$\n]+?)['"]/g;
  const usages = new Map(); // key -> [{file, line}]

  for (const file of files) {
    const content = fs.readFileSync(file, 'utf8');
    const lines = content.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      let match;
      tCallRegex.lastIndex = 0;
      while ((match = tCallRegex.exec(line)) !== null) {
        const key = match[1];
        // Skip dynamic keys with interpolation markers
        if (key.includes('${') || key.includes('{') && key.includes('}')) continue;
        if (!usages.has(key)) usages.set(key, []);
        usages.get(key).push({
          file: path.relative(SRC_DIR, file),
          line: i + 1,
        });
      }
    }
  }
  return usages;
}

// ─── 2. Detect hardcoded strings in JSX ───
function detectHardcodedStrings(files) {
  const results = [];

  // Patterns to IGNORE (not hardcoded user-visible text)
  const ignorePatterns = [
    /^\s*\/\//, // comments
    /^\s*\*/, // multiline comment lines
    /console\.(log|error|warn|info|debug)/, // console calls
    /className/, // CSS classes
    /import\s/, // imports
    /export\s/, // exports
    /from\s+['"]/, // from 'module'
    /require\(/, // require()
    /^\s*const\s/, // const declarations
    /^\s*let\s/, // let declarations  
    /^\s*var\s/, // var declarations
    /^\s*return\s*$/, // bare return
    /^\s*\{?\s*\/\*/, // JSX comments
    /data-testid/, // test IDs
    /aria-label/, // accessibility (these should eventually be translated too)
    /placeholder=/, // handled separately
    /https?:\/\//, // URLs
    /localhost/, // localhost refs
    /^\s*case\s+'/, // switch cases
    /\.addEventListener/, // event listeners
    /process\.env/, // env vars
    /navigate\(/, // navigation calls
    /toast\.(error|success|info|warning)/, // toast calls that use t()
    /^\s*\w+:\s/, // object key: value
  ];

  // Patterns that indicate hardcoded JSX text content
  // Matches: >Some Text< or >Some Text</ (text between JSX tags)
  const jsxTextRegex = />\s*([A-Z][a-z]{2,}(?:\s+[A-Za-z]+)*)\s*</g;
  // Matches: {'Some Text'} or {"Some Text"} (string literals in JSX expressions)
  const jsxExprStringRegex = /\{['"]([A-Z][a-z]{2,}(?:\s+[A-Za-z]+)*)['"]}/g;

  for (const file of files) {
    const content = fs.readFileSync(file, 'utf8');
    const lines = content.split('\n');
    const relFile = path.relative(SRC_DIR, file);

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Skip lines matching ignore patterns
      if (ignorePatterns.some(p => p.test(line))) continue;
      // Skip lines that already contain t( calls (properly wrapped)
      if (/\bt\(/.test(line) && !/>([A-Z][a-z]{2,}(?:\s+[A-Za-z]+)*)</.test(line)) continue;

      // Check for JSX text content: >Text Here<
      let match;
      jsxTextRegex.lastIndex = 0;
      while ((match = jsxTextRegex.exec(line)) !== null) {
        const text = match[1].trim();
        // Skip short words, numbers, single words that are likely component names
        if (text.length < 3) continue;
        if (/^[A-Z][a-z]+$/.test(text) && text.length < 8) continue; // Component-like: "Card", "Badge"
        if (/^\d+/.test(text)) continue; // numbers
        if (/^(true|false|null|undefined|NaN)$/.test(text)) continue;
        // Skip if it's inside a t() call on the same line
        if (line.includes(`t('`) && line.includes(text)) continue;
        if (line.includes(`t("`)) continue;

        results.push({
          file: relFile,
          line: i + 1,
          text,
          context: line.trim().substring(0, 120),
        });
      }

      // Check for bare string expressions: {'Text Here'}
      jsxExprStringRegex.lastIndex = 0;
      while ((match = jsxExprStringRegex.exec(line)) !== null) {
        const text = match[1].trim();
        if (text.length < 3) continue;
        // Skip if it looks like a key or variable reference
        if (/^[a-z]/.test(text)) continue;

        results.push({
          file: relFile,
          line: i + 1,
          text,
          context: line.trim().substring(0, 120),
        });
      }
    }
  }

  return results;
}

// ─── Main Audit ───
function runAudit() {
  console.log('\n  BidVex i18n Audit\n');
  console.log('─'.repeat(60));

  // Load translation files
  const en = JSON.parse(fs.readFileSync(EN_PATH, 'utf8'));
  const fr = JSON.parse(fs.readFileSync(FR_PATH, 'utf8'));
  const enKeys = new Set(flattenKeys(en));
  const frKeys = new Set(flattenKeys(fr));

  // Collect source files
  const files = collectFiles(SRC_DIR);
  console.log(`  Scanned ${files.length} source files\n`);

  // 1. Extract t() key usages
  const tUsages = extractTKeys(files);
  const usedKeys = new Set(tUsages.keys());

  // 2. Detect hardcoded strings
  const hardcoded = detectHardcodedStrings(files);

  // 3. Missing keys: used in t() but not in EN or FR JSON
  const missingFromEn = [];
  const missingFromFr = [];
  for (const [key, locations] of tUsages) {
    if (!enKeys.has(key)) missingFromEn.push({ key, locations });
    if (!frKeys.has(key)) missingFromFr.push({ key, locations });
  }

  // 4. Unused keys: in JSON but never referenced via t()
  // Also check i18n.js resource builder references
  const i18nContent = fs.readFileSync(path.resolve(SRC_DIR, 'i18n.js'), 'utf8');
  const allSourceContent = files.map(f => fs.readFileSync(f, 'utf8')).join('\n') + '\n' + i18nContent;

  const unusedEnKeys = [];
  const unusedFrKeys = [];
  for (const key of enKeys) {
    // Check if key is used via t('key') or referenced as a string in source
    const lastSegment = key.split('.').pop();
    const keyUsedInT = usedKeys.has(key);
    // Also check if the key's last segment appears in i18n.js as a property reference
    const referencedInI18n = i18nContent.includes(`?.${lastSegment}`) || i18nContent.includes(`.${lastSegment}`);
    if (!keyUsedInT && !referencedInI18n) {
      unusedEnKeys.push(key);
    }
  }
  for (const key of frKeys) {
    const keyUsedInT = usedKeys.has(key);
    const lastSegment = key.split('.').pop();
    const referencedInI18n = i18nContent.includes(`?.${lastSegment}`) || i18nContent.includes(`.${lastSegment}`);
    if (!keyUsedInT && !referencedInI18n) {
      unusedFrKeys.push(key);
    }
  }

  // 5. Sync check
  const onlyInEn = [...enKeys].filter(k => !frKeys.has(k));
  const onlyInFr = [...frKeys].filter(k => !enKeys.has(k));

  // ─── Console Summary ───
  const totalInSync = [...enKeys].filter(k => frKeys.has(k)).length;
  console.log(`  ${totalInSync} keys in sync between EN and FR`);

  if (hardcoded.length > 0) {
    console.log(`  ${hardcoded.length} potential hardcoded strings detected`);
    hardcoded.slice(0, 15).forEach(h => {
      console.log(`    ${h.file}:${h.line} -> "${h.text}"`);
    });
    if (hardcoded.length > 15) console.log(`    ... and ${hardcoded.length - 15} more (see full report)`);
  } else {
    console.log(`  0 hardcoded strings detected`);
  }

  const totalMissing = missingFromEn.length + missingFromFr.length;
  if (totalMissing > 0) {
    console.log(`  ${totalMissing} missing keys`);
    if (missingFromEn.length > 0) {
      console.log(`    Missing from en.json (${missingFromEn.length}):`);
      missingFromEn.slice(0, 10).forEach(m => {
        console.log(`      ${m.key} (used in ${m.locations[0].file}:${m.locations[0].line})`);
      });
    }
    if (missingFromFr.length > 0) {
      console.log(`    Missing from fr.json (${missingFromFr.length}):`);
      missingFromFr.slice(0, 10).forEach(m => {
        console.log(`      ${m.key} (used in ${m.locations[0].file}:${m.locations[0].line})`);
      });
    }
  } else {
    console.log(`  0 missing keys`);
  }

  const totalUnused = new Set([...unusedEnKeys, ...unusedFrKeys]).size;
  if (totalUnused > 0) {
    console.log(`  ${totalUnused} potentially unused keys`);
    const allUnused = [...new Set([...unusedEnKeys, ...unusedFrKeys])];
    allUnused.slice(0, 10).forEach(k => console.log(`    ${k}`));
    if (allUnused.length > 10) console.log(`    ... and ${allUnused.length - 10} more (see full report)`);
  } else {
    console.log(`  0 unused keys`);
  }

  if (onlyInEn.length > 0 || onlyInFr.length > 0) {
    console.log(`  ${onlyInEn.length + onlyInFr.length} sync mismatches`);
    if (onlyInEn.length > 0) {
      console.log(`    In en.json but NOT fr.json (${onlyInEn.length}):`);
      onlyInEn.slice(0, 5).forEach(k => console.log(`      ${k}`));
    }
    if (onlyInFr.length > 0) {
      console.log(`    In fr.json but NOT en.json (${onlyInFr.length}):`);
      onlyInFr.slice(0, 5).forEach(k => console.log(`      ${k}`));
    }
  } else {
    console.log(`  EN/FR files perfectly in sync`);
  }

  console.log('\n' + '─'.repeat(60));

  // ─── Full Report File ───
  const reportLines = [];
  reportLines.push('='.repeat(70));
  reportLines.push('  BIDVEX i18n AUDIT REPORT');
  reportLines.push(`  Generated: ${new Date().toISOString()}`);
  reportLines.push(`  Files scanned: ${files.length}`);
  reportLines.push(`  EN keys: ${enKeys.size} | FR keys: ${frKeys.size}`);
  reportLines.push(`  t() calls found: ${usedKeys.size} unique keys`);
  reportLines.push('='.repeat(70));

  // Section 1: Sync
  reportLines.push('\n' + '─'.repeat(70));
  reportLines.push('  SECTION 1: EN/FR SYNC CHECK');
  reportLines.push('─'.repeat(70));
  reportLines.push(`Keys in sync: ${totalInSync}`);
  if (onlyInEn.length > 0) {
    reportLines.push(`\nKeys in en.json but MISSING from fr.json (${onlyInEn.length}):`);
    onlyInEn.forEach(k => reportLines.push(`  - ${k}`));
  }
  if (onlyInFr.length > 0) {
    reportLines.push(`\nKeys in fr.json but MISSING from en.json (${onlyInFr.length}):`);
    onlyInFr.forEach(k => reportLines.push(`  - ${k}`));
  }
  if (onlyInEn.length === 0 && onlyInFr.length === 0) {
    reportLines.push('EN and FR files are perfectly in sync.');
  }

  // Section 2: Missing keys
  reportLines.push('\n' + '─'.repeat(70));
  reportLines.push('  SECTION 2: MISSING TRANSLATION KEYS');
  reportLines.push('  (Keys used via t() but absent from JSON files)');
  reportLines.push('  NOTE: These may exist in i18n.js resource builder.');
  reportLines.push('  Migrating them to JSON is recommended for maintainability.');
  reportLines.push('─'.repeat(70));
  if (missingFromEn.length > 0) {
    reportLines.push(`\nKeys used in code but MISSING from en.json (${missingFromEn.length}):`);
    for (const m of missingFromEn) {
      reportLines.push(`  - ${m.key}`);
      m.locations.forEach(l => reportLines.push(`      used in ${l.file}:${l.line}`));
    }
  }
  if (missingFromFr.length > 0) {
    reportLines.push(`\nKeys used in code but MISSING from fr.json (${missingFromFr.length}):`);
    for (const m of missingFromFr) {
      reportLines.push(`  - ${m.key}`);
      m.locations.forEach(l => reportLines.push(`      used in ${l.file}:${l.line}`));
    }
  }
  if (missingFromEn.length === 0 && missingFromFr.length === 0) {
    reportLines.push('All t() keys have corresponding entries in both JSON files.');
  }

  // Section 3: Unused keys
  reportLines.push('\n' + '─'.repeat(70));
  reportLines.push('  SECTION 3: POTENTIALLY UNUSED KEYS');
  reportLines.push('─'.repeat(70));
  const allUnusedSet = new Set([...unusedEnKeys, ...unusedFrKeys]);
  if (allUnusedSet.size > 0) {
    reportLines.push(`Found ${allUnusedSet.size} keys not directly referenced via t() or i18n.js:\n`);
    for (const k of [...allUnusedSet].sort()) {
      const inEn = unusedEnKeys.includes(k) ? 'EN' : '';
      const inFr = unusedFrKeys.includes(k) ? 'FR' : '';
      reportLines.push(`  - ${k} [${[inEn, inFr].filter(Boolean).join(', ')}]`);
    }
    reportLines.push('\nNote: Some keys may be referenced dynamically (template literals, computed keys).');
    reportLines.push('Review before deleting.');
  } else {
    reportLines.push('No unused keys detected.');
  }

  // Section 4: Hardcoded strings
  reportLines.push('\n' + '─'.repeat(70));
  reportLines.push('  SECTION 4: POTENTIAL HARDCODED STRINGS');
  reportLines.push('─'.repeat(70));
  if (hardcoded.length > 0) {
    reportLines.push(`Found ${hardcoded.length} potential hardcoded strings:\n`);
    // Group by file
    const byFile = {};
    for (const h of hardcoded) {
      if (!byFile[h.file]) byFile[h.file] = [];
      byFile[h.file].push(h);
    }
    for (const [file, items] of Object.entries(byFile).sort()) {
      reportLines.push(`  ${file}:`);
      for (const h of items) {
        reportLines.push(`    Line ${h.line}: "${h.text}"`);
        reportLines.push(`      ${h.context}`);
      }
      reportLines.push('');
    }
    reportLines.push('Note: Some may be false positives (component names, enum values, user content).');
    reportLines.push('Review each one manually.');
  } else {
    reportLines.push('No hardcoded strings detected.');
  }

  reportLines.push('\n' + '='.repeat(70));
  reportLines.push('  END OF REPORT');
  reportLines.push('='.repeat(70));

  const report = reportLines.join('\n');
  fs.writeFileSync(REPORT_PATH, report, 'utf8');
  console.log(`\n  Full report written to: ${path.relative(process.cwd(), REPORT_PATH)}\n`);

  // Exit code: 1 if there are missing keys or sync issues (hard errors)
  const hasHardErrors = missingFromEn.length > 0 || missingFromFr.length > 0 || onlyInEn.length > 0 || onlyInFr.length > 0;
  process.exit(hasHardErrors ? 1 : 0);
}

runAudit();
