/* Read public reference bundles as data only. Never execute downloaded JavaScript. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const ts = require('../snowland-frontend/node_modules/typescript');

function literal(node) {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isNumericLiteral(node)) return Number(node.text);
  if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (node.kind === ts.SyntaxKind.NullKeyword) return null;
  if (ts.isArrayLiteralExpression(node)) return node.elements.map(literal);
  if (ts.isObjectLiteralExpression(node)) {
    const result = Object.create(null);
    for (const property of node.properties) {
      if (!ts.isPropertyAssignment(property) || property.name && ts.isComputedPropertyName(property.name)) throw Error('Non-literal property');
      const key = property.name.text;
      if (key === undefined || Object.hasOwn(result, key) || ['__proto__', 'constructor', 'prototype'].includes(key)) throw Error('Unsafe or duplicate property');
      result[key] = literal(property.initializer);
    }
    return result;
  }
  throw Error('Non-literal expression');
}

function extract(source) {
  const tree = ts.createSourceFile('reference.js', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  if (tree.parseDiagnostics.length) throw Error('Reference bundle is not valid JavaScript');
  const cards = [], articles = [];
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.initializer) {
      try {
        const value = literal(node.initializer);
        if (Array.isArray(value) && value.length && value.every(row => row && typeof row.title === 'string' && typeof row.url === 'string' && typeof row.category === 'string' && typeof row.excerpt === 'string')) cards.push(value);
        if (value && !Array.isArray(value) && Object.keys(value).length && Object.values(value).every(row => row && typeof row.title === 'string' && typeof row.html === 'string' && typeof row.heroImage === 'string')) articles.push(value);
      } catch { /* Runtime expressions are intentionally unsupported. */ }
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  if (cards.length !== 1 || articles.length !== 1) throw Error(`Ambiguous source: ${cards.length} card arrays, ${articles.length} article maps`);
  const urls = new Set();
  for (const card of cards[0]) {
    if (urls.has(card.url)) throw Error('Duplicate card URL');
    urls.add(card.url);
  }
  const byTitle = new Map();
  for (const [slug, article] of Object.entries(articles[0])) {
    if (byTitle.has(article.title)) throw Error('Duplicate article title');
    byTitle.set(article.title, {slug, ...article});
  }
  const rows = cards[0].map(card => {
    const article = byTitle.get(card.title);
    if (!article || !article.html.trim()) throw Error(`Missing full article: ${card.title}`);
    return {card, article};
  });
  if ([...byTitle.keys()].some(title => !rows.some(row => row.card.title === title))) throw Error('Unmatched article bodies');
  return rows;
}

if (require.main === module) {
  const [input, output] = process.argv.slice(2);
  if (!input || !output) throw Error('Usage: node tools/extract-customer-guide-source.cjs <downloaded-public-bundle> <new-json-file>');
  const source = fs.readFileSync(input, 'utf8');
  const rows = extract(source);
  const snapshot = {source_url:'https://snowland.pages.dev/guides', bundle_sha256:crypto.createHash('sha256').update(source).digest('hex'), articles:rows};
  // Refuse to replace a previously reviewed snapshot.
  fs.writeFileSync(path.resolve(output), JSON.stringify(snapshot, null, 2) + '\n', {flag:'wx'});
  console.log(`Extracted ${rows.length} complete articles without executing source code.`);
}
module.exports = {literal, extract};
