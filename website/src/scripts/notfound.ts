/**
 * Die eine 404-Seite in der Sprache der verlorenen Adresse (src/pages/404.astro): liegt sie unter
 * /<sprache>/, stehen Wörter, Links und `lang` dieser Sprache da. Ohne JavaScript bleibt Deutsch.
 */
interface Other {
  code: string;
  locale: string;
  words: Record<string, string>;
  links: { href: string; label: string; text: string }[];
  home?: string;
}

export function localize404(): void {
  const root = document.querySelector<HTMLElement>('[data-lang]');
  if (!root) return;
  const code = location.pathname.split('/')[1];
  const lang = (JSON.parse(root.dataset.lang ?? '[]') as Other[]).find((l) => l.code === code);
  if (!lang) return;
  document.documentElement.lang = lang.locale;
  document.title = `${lang.words.title} | ${document.title.split(' | ').pop() ?? ''}`;
  for (const el of root.querySelectorAll<HTMLElement>('[data-w]')) el.textContent = lang.words[el.dataset.w ?? ''] ?? el.textContent;
  root.querySelectorAll<HTMLAnchorElement>('[data-link]').forEach((a, i) => {
    const l = lang.links[i];
    if (!l) return;
    a.href = l.href;
    a.querySelector('.nf__label')!.textContent = l.label;
    a.querySelector('.nf__text')!.textContent = l.text;
  });
  const home = root.querySelector<HTMLAnchorElement>('[data-home]');
  if (home && lang.home) home.href = lang.home;
}
