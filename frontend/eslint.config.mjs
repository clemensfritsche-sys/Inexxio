// ESLint 9 – Flat Config (ersetzt `.eslintrc.json`). Grundlage ist dieselbe wie vorher,
// `next/core-web-vitals`; es lädt das Plugin `@typescript-eslint` für .ts/.tsx selbst mit.
import nextVitals from 'eslint-config-next/core-web-vitals';

/**
 * **Die Hook-Regeln bleiben die beiden von vorher** (`rules-of-hooks` als Fehler,
 * `exhaustive-deps` als Warnung). `eslint-plugin-react-hooks` 7 bringt in seiner
 * Empfehlung die Regeln des React Compilers mit (`set-state-in-effect`, `refs`,
 * `static-components` …) – sie gelten Code, den der Compiler optimieren soll, und den
 * setzt dieses Projekt nicht ein. Ausgeschaltet wird, was NICHT zu den beiden gehört; so
 * schaltet eine künftige Fassung keine neue Regel still ein.
 */
const KEPT_HOOK_RULES = new Set(['react-hooks/rules-of-hooks', 'react-hooks/exhaustive-deps']);
const compilerRulesOff = Object.fromEntries(
  nextVitals
    .flatMap((c) => Object.keys(c.rules ?? {}))
    .filter((r) => r.startsWith('react-hooks/') && !KEPT_HOOK_RULES.has(r))
    .map((r) => [r, 'off']),
);

/**
 * **Regeln des Hauses am Syntaxbaum** – «eine Sache, eine Stelle» (CLAUDE.md, Leitbild).
 * Ausnahmen stehen unten je Datei: die eine Stelle, die die Regel umsetzt.
 */
// Eine Zahl wird über `formatAmount` (lib/utils) geschrieben – das ICU der Laufzeit
// schreibt den Tausender-Trenner je nach Fassung anders (Hydrations-Fehler).
const LOCALE_STRING = {
  selector: "CallExpression[callee.property.name='toLocaleString']",
  message: 'Zahlen über formatAmount (lib/utils), Datum über lib/when – nicht über das ICU der Laufzeit.',
};
const HOUSE_SYNTAX = [
  LOCALE_STRING,
  // Ein Datum hat EINE Ausgabe: lib/when.ts (`when` = Auskunft, `day` = Tag auf dem Papier).
  {
    selector: "CallExpression[callee.property.name=/^toLocale(Date|Time)String$/]",
    message: 'Ein Datum nur über lib/when.ts (when · day · formatWhen).',
  },
  {
    selector: "MemberExpression[object.name='Intl'][property.name='DateTimeFormat']",
    message: 'Ein Datum nur über lib/when.ts – die Wörter stehen dort, nicht im ICU.',
  },
  // «Ist das Personal?» fragt EINE Funktion: isStaff (lib/record-status).
  ...['left', 'right'].map((side) => ({
    selector: `BinaryExpression[operator=/^[!=]==?$/][${side}.value='employee']`,
    message: 'Die Rolle nur über isStaff() (lib/record-status) vergleichen.',
  })),
  // `busy` sperrt Handlungen, nie einen Wert: `disabled` nimmt dem Feld den Fokus, und ein
  // Auto-Save darf nichts verschieben.
  {
    selector: "JSXOpeningElement[name.name=/^(input|select|textarea)$/] > JSXAttribute[name.name='disabled'] > JSXExpressionContainer > Identifier[name='busy']",
    message: '`busy` sperrt Handlungen, nie ein Eingabefeld (disabled nimmt den Fokus).',
  },
];
const BUSY_INPUT = HOUSE_SYNTAX[HOUSE_SYNTAX.length - 1];
const STAFF_ROLE = HOUSE_SYNTAX.filter((r) => r.selector.startsWith('BinaryExpression'));
const without = (all, ...drop) => all.filter((r) => !drop.includes(r));
// Gemeinsame Bausteine wohnen nicht unter «account»: nur das Konto importiert von dort.
const ACCOUNT_IMPORT = {
  regex: '^@/components/account/',
  message: 'Gemeinsame Bausteine liegen nicht unter components/account – nur das Konto importiert von dort.',
};

const config = [
  ...nextVitals,
  { rules: compilerRulesOff },
  {
    // Gebautes und Übernommenes, nicht Quelltext: die Testnotiz-Insel und OpenCV.js
    // (`scripts/build-islands.mjs`, `scripts/vendor-opencv.mjs`), Kopf und Fuss der
    // Website (`scripts/site-shell.mjs`).
    ignores: ['public/islands/**', 'public/vendor/**', 'src/generated/**'],
  },
  {
    files: ['**/*.ts', '**/*.tsx'],
    rules: {
      // **Ein Knopf ohne Wirkung fällt auf** – die TypeScript-Fassung kennt auch Typen;
      // die Basisregel ist dafür aus. Ein Wächter liest diese Zeilen
      // (`backend/tests/test_source_ui.py`).
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['error', {
        args: 'none',
        varsIgnorePattern: '^_',
        destructuredArrayIgnorePattern: '^_',
        ignoreRestSiblings: true,
      }],
      'no-restricted-syntax': ['error', ...HOUSE_SYNTAX],
      'no-restricted-imports': ['error', { patterns: [ACCOUNT_IMPORT] }],
    },
  },
  // Die eine Stelle je Regel darf, was sie allen anderen abnimmt.
  {
    files: ['src/lib/utils.ts'],
    rules: { 'no-restricted-syntax': ['error', ...without(HOUSE_SYNTAX, LOCALE_STRING)] },
  },
  {
    files: ['src/lib/record-status.ts'],
    rules: { 'no-restricted-syntax': ['error', ...without(HOUSE_SYNTAX, ...STAFF_ROLE)] },
  },
  // Offener Befund: der Kanton-Wähler sperrt sich, solange die Regeln gespeichert werden
  // (zwei schnelle Wechsel liefen sonst ungeordnet) – zu lösen am Speicherweg, nicht hier.
  {
    files: ['src/components/erp/time/company-time.tsx'],
    rules: { 'no-restricted-syntax': ['error', ...without(HOUSE_SYNTAX, BUSY_INPUT)] },
  },
  {
    files: ['src/components/account/**', 'src/app/(account)/**'],
    rules: { 'no-restricted-imports': 'off' },
  },
];

export default config;
