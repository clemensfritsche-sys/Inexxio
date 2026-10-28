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
    },
  },
];

export default config;
