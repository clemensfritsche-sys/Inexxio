import { Fragment, type ReactNode } from 'react';

/**
 * ►►► **Die Antwort der KI, lesbar** – Markdown, wie die KI es schreibt. ◄◄◄
 *
 * Kein Regelwerk: die KI formatiert, wie es ihr passt; hier wird nur gezeigt, was sie schrieb –
 * Absätze, Überschriften (#), Listen (- * 1.), Zitat (>), Code (``` und `…`), **fett**, *kursiv*,
 * Links ([Wort](https://…)). Alles als React-Elemente, nie als HTML: was in der Antwort steht,
 * kann nichts ausführen. Was hier keine Form hat, steht als Text da.
 */
export function Markdown({ text }: { text: string }) {
  return <div className="erp-md">{blocks(text)}</div>;
}

function blocks(text: string): ReactNode[] {
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  const out: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (line.trimStart().startsWith('```')) {
      const code: string[] = [];
      for (i++; i < lines.length && !lines[i].trimStart().startsWith('```'); i++) code.push(lines[i]);
      i++;
      out.push(<pre key={out.length}><code>{code.join('\n')}</code></pre>);
      continue;
    }
    const head = /^(#{1,6})\s+(.*)$/.exec(line);
    if (head) {
      out.push(<p key={out.length} className="erp-md-h">{inline(head[2])}</p>);
      i++;
      continue;
    }
    const list = listItem(line);
    if (list) {
      const ordered = list.ordered;
      const items: string[] = [];
      for (; i < lines.length; i++) {
        const it = listItem(lines[i]);
        if (it && it.ordered === ordered) items.push(it.text);
        else if (lines[i].trim() && /^\s{2,}/.test(lines[i]) && items.length) items[items.length - 1] += ` ${lines[i].trim()}`;
        else break;
      }
      const kids = items.map((t, k) => <li key={k}>{inline(t)}</li>);
      out.push(ordered ? <ol key={out.length}>{kids}</ol> : <ul key={out.length}>{kids}</ul>);
      continue;
    }
    if (line.startsWith('>')) {
      const quote: string[] = [];
      for (; i < lines.length && lines[i].startsWith('>'); i++) quote.push(lines[i].replace(/^>\s?/, ''));
      out.push(<blockquote key={out.length}>{inline(quote.join(' '))}</blockquote>);
      continue;
    }
    const para: string[] = [];
    for (; i < lines.length && lines[i].trim() && !startsBlock(lines[i]); i++) para.push(lines[i]);
    out.push(<p key={out.length}>{para.map((p, k) => <Fragment key={k}>{k > 0 && <br />}{inline(p)}</Fragment>)}</p>);
  }
  return out;
}

function listItem(line: string): { ordered: boolean; text: string } | null {
  const m = /^\s{0,3}([-*•–]|\d+[.)])\s+(.*)$/.exec(line);
  return m ? { ordered: /\d/.test(m[1]), text: m[2] } : null;
}

const startsBlock = (line: string) => /^(#{1,6}\s|>|```)/.test(line.trimStart()) || !!listItem(line);

/** **fett**, *kursiv*, `Code`, [Link](https://…) – der Rest ist Text. */
const INLINE = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\*[^*\s][^*]*\*|_[^_\s][^_]*_|\[[^\]]+\]\(https?:\/\/[^)\s]+\))/g;

function inline(text: string): ReactNode[] {
  return text.split(INLINE).filter(Boolean).map((part, k) => {
    if (/^(\*\*|__)/.test(part) && part.length > 4) return <strong key={k}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.length > 2) return <code key={k}>{part.slice(1, -1)}</code>;
    const link = /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/.exec(part);
    if (link) return <a key={k} href={link[2]} target="_blank" rel="noreferrer noopener">{link[1]}</a>;
    if (/^[*_].+[*_]$/.test(part) && part.length > 2) return <em key={k}>{part.slice(1, -1)}</em>;
    return <Fragment key={k}>{part}</Fragment>;
  });
}
