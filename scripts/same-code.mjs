#!/usr/bin/env node
// ►►► Hat sich nur Text geändert, nie Code? ◄◄◄ Vergleicht jede geänderte Datei mit dem Stand
// `git <rev>` (Vorgabe HEAD): TypeScript/TSX übersetzt ohne Kommentare, Python als Syntaxbaum ohne
// Docstrings. Jede Abweichung wird genannt; Ausgang 1, wenn eine Datei mehr als Text änderte.
//   node scripts/same-code.mjs [rev]
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const ts = require('typescript');
const rev = process.argv[2] ?? 'HEAD';
const git = (...a) => execFileSync('git', a, { encoding: 'utf8', maxBuffer: 1 << 28 });
const changed = git('diff', '--name-only', rev, '--', '*.ts', '*.tsx', '*.py', '*.mjs')
  .split('\n').filter(Boolean);

const tsOut = (src, file) => ts.transpileModule(src, {
  fileName: file, reportDiagnostics: false,
  compilerOptions: { removeComments: true, jsx: ts.JsxEmit.Preserve, target: ts.ScriptTarget.ESNext,
                     module: ts.ModuleKind.ESNext },
}).outputText.replace(/^\s*$/gm, '').replace(/\n+/g, '\n');

const PY = `
import ast, sys
def strip(t):
    for n in ast.walk(t):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = n.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], 'value', None), ast.Constant) and isinstance(b[0].value.value, str):
                n.body = b[1:] or [ast.Pass()]
    return ast.dump(t, include_attributes=False)
a, b = sys.stdin.read().split('\\x00')
print('same' if strip(ast.parse(a)) == strip(ast.parse(b)) else 'diff')
`;

let bad = 0;
for (const file of changed) {
  let before = '';
  try { before = git('show', `${rev}:${file}`); } catch { continue; }      // neu: nichts zu vergleichen
  let after = '';
  try { after = git('show', `:${file}`); } catch { continue; }
  after = require('node:fs').readFileSync(file, 'utf8');
  let same;
  if (file.endsWith('.py')) {
    same = execFileSync('python3', ['-c', PY], { input: `${before}\0${after}`, encoding: 'utf8' }).trim() === 'same';
  } else {
    same = tsOut(before, file) === tsOut(after, file);
  }
  if (!same) { bad += 1; console.log(`CODE GEÄNDERT: ${file}`); }
}
console.log(`${changed.length} Dateien geprüft, ${bad} mit Code-Änderung.`);
process.exit(bad ? 1 : 0);
