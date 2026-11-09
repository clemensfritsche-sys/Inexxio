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
  // Die Rolle fragt EINE Stelle: isStaff · isAdmin (lib/record-status) – Spiegel von
  // `domain/policy`. Ob man etwas darf, sagt der Server (`can`, `may_edit`).
  ...['left', 'right'].flatMap((side) => ['employee', 'admin'].map((role) => ({
    selector: `BinaryExpression[operator=/^[!=]==?$/][${side}.value='${role}']`,
    message: 'Die Rolle nur über isStaff() / isAdmin() (lib/record-status) vergleichen.',
  }))),
  // `busy` sperrt Handlungen, nie einen Wert: `disabled` nimmt dem Feld den Fokus, und ein
  // Auto-Save darf nichts verschieben.
  // Gilt auch für den Feld-Baustein (`Input` · `Select` · `TextArea` · `Field` · `SelectField`).
  {
    selector: "JSXOpeningElement[name.name=/^(input|select|textarea|Input|Select|TextArea|Field|SelectField)$/] > JSXAttribute[name.name='disabled'] > JSXExpressionContainer > Identifier[name='busy']",
    message: '`busy` sperrt Handlungen, nie ein Eingabefeld (disabled nimmt den Fokus).',
  },
];
const BUSY_INPUT = HOUSE_SYNTAX[HOUSE_SYNTAX.length - 1];
const STAFF_ROLE = HOUSE_SYNTAX.filter((r) => r.selector.startsWith('BinaryExpression'));
const without = (all, ...drop) => all.filter((r) => !drop.includes(r));
/**
 * ►►► **Ein Feld steht im Feld-Baustein** (`components/form/field.tsx`, Logik in
 * `use-field.ts`; Projektakte «Die lernende Firma» §4.3, Schritt 2.1). ◄◄◄ Ein loses
 * `<input>` / `<select>` / `<textarea>` hätte seine eigene Fassung von Enter, Pflicht, Format –
 * und später keinen Vorschlag. Wer anders aussehen muss (der Beleg), nimmt `Input` · `Select`
 * · `TextArea` mit eigener Klasse: Logik zentral, Aussehen frei. Kästchen und Dateiwahl
 * sind kein Wert zum Tippen und fallen nicht darunter.
 */
const RAW_FIELD = {
  selector: "JSXOpeningElement[name.name=/^(input|select|textarea)$/]:not(:has(JSXAttribute[name.name='type'][value.value=/^(checkbox|file)$/]))",
  message: 'Ein Feld über den Feld-Baustein (components/form/field: Field · SelectField · Input · Select · TextArea), nicht als loses Element.',
};
// Wo der Wächter gilt: die Oberflächen der Datensätze (ERP, Konto, Kundenseite).
const RECORD_UI = ['src/components/erp/**', 'src/components/account/**', 'src/components/beleg/**'];
/**
 * **Die Ausnahmen – je Datei mit Grund.** Hier ist jedes lose Feld KEIN Wert eines
 * Datensatzes. Steht eine Ausnahme mitten in einer Datei mit echten Feldern, trägt sie ein
 * `eslint-disable-next-line no-restricted-syntax -- <Grund>` am Element (Adresssuche,
 * Instanzsuche der Stückliste); ein überflüssiges meldet ESLint (`reportUnusedDisableDirectives`).
 */
const RAW_FIELD_ALLOWED = [
  'src/components/erp/feed-panel.tsx',              // Suchfeld des Feeds
  'src/components/erp/search-select.tsx',           // Suchtext des Auswahlfelds – der Wert ist die Wahl
  'src/components/erp/territory-map.tsx',           // Ländersuche der Gebietskarte
  'src/components/erp/communication/composer.tsx',  // Eingabe einer Nachricht (eigener Entwurf `Draft`)
  'src/components/erp/compose-chat.tsx',            // Eingabe im Chat «Verfassen» (KI)
];

// Gemeinsame Bausteine wohnen nicht unter «account»: nur das Konto importiert von dort.
const ACCOUNT_IMPORT = {
  regex: '^@/components/account/',
  message: 'Gemeinsame Bausteine liegen nicht unter components/account – nur das Konto importiert von dort.',
};

const config = [
  ...nextVitals,
  { rules: compilerRulesOff },
  {
    // Gebautes und Übernommenes, nicht Quelltext: OpenCV.js (`scripts/vendor-opencv.mjs`),
    // Kopf und Fuss der Website (`scripts/site-shell.mjs`).
    ignores: ['public/vendor/**', 'src/generated/**'],
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
  {
    files: ['src/components/account/**', 'src/app/(account)/**'],
    rules: { 'no-restricted-imports': 'off' },
  },
  {
    files: RECORD_UI,
    rules: { 'no-restricted-syntax': ['error', ...HOUSE_SYNTAX, RAW_FIELD] },
  },
  {
    files: RAW_FIELD_ALLOWED,
    rules: { 'no-restricted-syntax': ['error', ...HOUSE_SYNTAX] },
  },
  { linterOptions: { reportUnusedDisableDirectives: 'error' } },
];

export default config;
