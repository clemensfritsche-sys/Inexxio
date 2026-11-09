/**
 * ►►► **Gemeinsame Hilfen der Quelltext-Wächter** – gelesen wird der Syntaxbaum, nicht der Text. ◄◄◄
 *
 * Ein Wächter, der mit regulären Ausdrücken sucht, sieht Kommentare, Zeichenketten und
 * Umbrüche falsch. Hier wird jede Datei mit dem TypeScript-Parser gelesen (`typescript`, kein
 * Typprüfer – schnell); die Funktionen liefern Knoten oder einfache Werte. Jeder Wächter prüft
 * zusätzlich seine Bug-Form an einem Beispieltext (`parse(text)` statt einer Datei).
 *
 *     import { files, parse, calls, strings } from './lib/source.mjs';
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

export { ts };

/** `frontend/src` – Wurzel aller Pfade, die die Wächter nennen. */
export const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '../../src');

/** Generiert, nicht von Hand geschrieben – kein Wächter liest sie. */
const GENERATED = new Set(['types/api.ts', 'lib/status-catalog.ts', 'lib/vocab.ts']);

/** Alle `.ts`/`.tsx` unter `dir` (relativ zu `src`), ohne generierte Dateien – als Pfade relativ zu `src`. */
export function files(dir = '.') {
  const walk = (abs) => readdirSync(abs).flatMap((name) => {
    const p = join(abs, name);
    if (statSync(p).isDirectory()) return walk(p);
    return /\.tsx?$/.test(name) ? [relative(SRC, p)] : [];
  });
  return walk(resolve(SRC, dir)).filter((rel) => !GENERATED.has(rel)).sort();
}

/** Der Text einer Datei (Pfad relativ zu `src`). */
export function read(rel) {
  return readFileSync(resolve(SRC, rel), 'utf8');
}

/**
 * Der Syntaxbaum – einer Datei (`parse('lib/x.ts')`) oder eines Beispieltexts
 * (`parse('const a = 1;', { text: true })`, für die Gegenprobe der Bug-Form).
 */
export function parse(relOrText, { text = false } = {}) {
  const name = text ? 'sample.tsx' : relOrText;
  const body = text ? relOrText : read(relOrText);
  return ts.createSourceFile(name, body, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
}

/** Jeden Knoten unter `node` besuchen (Tiefe zuerst); `visit(n)` gibt `false` zurück, um nicht abzusteigen. */
export function walk(node, visit) {
  const go = (n) => {
    if (visit(n) === false) return;
    ts.forEachChild(n, go);
  };
  ts.forEachChild(node, go);
}

/** Alle Knoten, für die `test(n)` wahr ist. */
export function find(node, test) {
  const out = [];
  walk(node, (n) => { if (test(n)) out.push(n); });
  return out;
}

/** Der Name eines Aufrufs: `foo(…)` → `foo`, `api.bar(…)` → `api.bar`, sonst `''`. */
export function calleeName(call) {
  const e = call.expression;
  if (ts.isIdentifier(e)) return e.text;
  if (ts.isPropertyAccessExpression(e)) {
    const head = ts.isIdentifier(e.expression) || e.expression.kind === ts.SyntaxKind.ThisKeyword
      ? e.expression.getText() : '…';
    return `${head}.${e.name.text}`;
  }
  return '';
}

/** Alle Aufrufe – mit `name` nur die, deren Name passt (Text oder Ausdruck). */
export function calls(node, name) {
  const match = typeof name === 'string' ? (s) => s === name : name ?? (() => true);
  return find(node, (n) => ts.isCallExpression(n) && match(calleeName(n)));
}

/** Alle JSX-Elemente (öffnend und selbstschliessend) – mit `tag` nur diese. */
export function jsx(node, tag) {
  return find(node, (n) => (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n))
    && (tag === undefined || n.tagName.getText() === tag));
}

/** Die Importe einer Datei: `[{ from, names }]` (Standard-Import als `default`, `* as x` als `*`). */
export function imports(sf) {
  return sf.statements.filter(ts.isImportDeclaration).map((d) => {
    const names = [];
    const clause = d.importClause;
    if (clause?.name) names.push('default');
    const bindings = clause?.namedBindings;
    if (bindings && ts.isNamespaceImport(bindings)) names.push('*');
    if (bindings && ts.isNamedImports(bindings)) {
      for (const el of bindings.elements) names.push((el.propertyName ?? el.name).text);
    }
    return { from: d.moduleSpecifier.text, names };
  });
}

/** Die Namen, die eine Datei exportiert (Deklarationen und `export { … }`). */
export function exports(sf) {
  const out = [];
  for (const st of sf.statements) {
    const exported = ts.canHaveModifiers(st)
      && ts.getModifiers(st)?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword);
    if (exported && ts.isVariableStatement(st)) {
      for (const d of st.declarationList.declarations) out.push(d.name.getText());
    } else if (exported && st.name) {
      out.push(st.name.text);
    } else if (ts.isExportDeclaration(st) && st.exportClause && ts.isNamedExports(st.exportClause)) {
      for (const el of st.exportClause.elements) out.push(el.name.text);
    }
  }
  return out;
}

/** Alle festen Zeichenketten im Code (`'…'`, `"…"`, `` `…` `` ohne Platzhalter) – Kommentare nie. */
export function strings(node) {
  return find(node, (n) => ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n));
}

/** Zeile (ab 1) eines Knotens – für eine Meldung, die die Stelle nennt. */
export function line(node) {
  return node.getSourceFile().getLineAndCharacterOfPosition(node.getStart()).line + 1;
}

/** Der Text ohne Kommentare (aus dem Scanner, nicht per Ausdruck – `'//'` in einer Zeichenkette bleibt). */
export function stripComments(text) {
  const scanner = ts.createScanner(ts.ScriptTarget.Latest, false, ts.LanguageVariant.JSX, text);
  let out = '';
  for (let k = scanner.scan(); k !== ts.SyntaxKind.EndOfFileToken; k = scanner.scan()) {
    if (k !== ts.SyntaxKind.SingleLineCommentTrivia && k !== ts.SyntaxKind.MultiLineCommentTrivia) {
      out += scanner.getTokenText();
    }
  }
  return out;
}
