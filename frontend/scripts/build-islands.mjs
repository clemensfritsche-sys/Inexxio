// Bündelt Inseln für die Website: Next-Komponenten, die auf den Astro-Seiten laufen.
// Heute genau eine – die Testnotizen (src/islands/feedback.tsx).
//
// ►►► Nur in der Testumgebung. ◄◄◄ Die Notizen gibt es ausserhalb nicht (der Endpunkt
// antwortet 404), also wird die Insel dort gar nicht erst gebaut – und eine alte Fassung
// in `public/islands/` wird entfernt, damit sie nicht in einen Produktions-Build rutscht.
//
// Aufruf: `node scripts/build-islands.mjs` (läuft in `npm run build` vor `next build`).
import { build } from 'esbuild';
import { mkdirSync, readFileSync, rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import postcss from 'postcss';
import tailwind from 'tailwindcss';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const OUT_DIR = resolve(ROOT, 'public/islands');
const SCOPE = '#ix-feedback';

rmSync(OUT_DIR, { recursive: true, force: true });
if (process.env.NEXT_PUBLIC_ENVIRONMENT !== 'development') {
  console.log('Inseln: übersprungen (nur in der Testumgebung).');
  process.exit(0);
}

/** Die Tokens des Design-Systems – nur ihr `:root`-Block, auf die Insel begrenzt. */
function tokens() {
  const src = readFileSync(resolve(ROOT, 'src/styles/design-system/colors_and_type.css'), 'utf8');
  const start = src.indexOf(':root {');
  const end = src.indexOf('\n}', start);
  if (start < 0 || end < 0) throw new Error('colors_and_type.css: kein :root-Block gefunden');
  return `${SCOPE} ${src.slice(start + ':root '.length, end + 2)}`;
}

/**
 * Ohne Preflight (sonst setzte Tailwind die ganze Website zurück) – dafür ein kleiner
 * Rückbau dessen, was die Website an Elementen vorgibt. Die Spezifität (1,0,1) liegt unter
 * der der Hilfsklassen (`#ix-feedback .px-3` = 1,1,0), also gewinnen diese.
 */
const RESET = `
${SCOPE} { font: 400 14px/1.45 var(--font-body); color: var(--fg-1); }
${SCOPE} *, ${SCOPE} *::before, ${SCOPE} *::after { box-sizing: border-box; border: 0 solid var(--border-1); }
${SCOPE} p, ${SCOPE} ul, ${SCOPE} li { margin: 0; padding: 0; max-width: none; hyphens: manual; }
${SCOPE} button, ${SCOPE} textarea { font: inherit; color: inherit; background: none; margin: 0; padding: 0; }
${SCOPE} button { cursor: pointer; }
${SCOPE} svg { display: block; flex: none; }
`;

async function css() {
  const config = {
    presets: [(await import('../tailwind.config.js')).default],
    content: [resolve(ROOT, 'src/components/feedback/feedback-pin.tsx')],
    important: SCOPE,
    corePlugins: { preflight: false },
  };
  const input = `${tokens()}\n${RESET}\n@tailwind utilities;`;
  const out = await postcss([tailwind(config)]).process(input, { from: undefined });
  return out.css;
}

const islandCss = await css();
mkdirSync(OUT_DIR, { recursive: true });
const env = Object.fromEntries(
  Object.entries(process.env)
    .filter(([k]) => k.startsWith('NEXT_PUBLIC_'))
    .map(([k, v]) => [`process.env.${k}`, JSON.stringify(v)]),
);
await build({
  entryPoints: [resolve(ROOT, 'src/islands/feedback.tsx')],
  outfile: resolve(OUT_DIR, 'feedback.js'),
  bundle: true,
  minify: true,
  format: 'iife',
  target: 'es2019',
  jsx: 'automatic',
  legalComments: 'none',
  tsconfig: resolve(ROOT, 'tsconfig.json'),
  alias: { 'next/navigation': resolve(ROOT, 'src/islands/next-navigation.ts') },
  // Was nicht gesetzt ist, bleibt `undefined` – wie in Next, statt «process is not defined».
  define: { 'process.env': '{}', ...env, 'process.env.NODE_ENV': '"production"' },
  plugins: [{
    name: 'island-css',
    setup(b) {
      b.onResolve({ filter: /^islands:/ }, (a) => ({ path: a.path, namespace: 'island-css' }));
      b.onLoad({ filter: /.*/, namespace: 'island-css' }, () => ({ contents: islandCss, loader: 'text' }));
    },
  }],
});
console.log('Inseln: public/islands/feedback.js gebaut.');
