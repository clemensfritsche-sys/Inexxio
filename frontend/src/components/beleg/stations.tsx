import { Check, CreditCard, FileText, Flag, Truck, type LucideIcon } from 'lucide-react';
import type { components } from '@/types/api';
import css from './beleg.module.css';

type Station = components['schemas']['StationOut'];

/** Das Symbol je Station – Offerte · Auftragsbestätigung · Rechnung · Bezahlt (`voucher_docs.WAY`). */
const ICONS: LucideIcon[] = [FileText, Truck, CreditCard, Flag];

/**
 * **Der Weg** wie «Ablauf» auf der Website: die Linie steht nur zwischen den Stationen,
 * ausgezogen bis zur aktuellen; die aktuelle Karte ist weiss und trägt ihre Nummer dunkel,
 * erledigte tragen einen Haken. Wer was tut, sagt der Server (`stations`).
 */
export function Stations({ stations }: { stations: Station[] }) {
  return (
    <ol className={css.way}>
      {stations.map((s, i) => {
        const Icon = s.state === 'done' ? Check : (ICONS[i] ?? FileText);
        const next = stations[i + 1];
        const cls = [css.st, s.state === 'active' ? css.cur : '', s.state === 'done' ? css.done : '']
          .filter(Boolean).join(' ');
        return (
          <li key={`${i}-${s.title}`} className={cls} aria-current={s.state === 'active' ? 'step' : undefined}>
            <div className={css.top}>
              {next && (
                <span aria-hidden="true"
                  className={next.state === 'ahead' ? css.line : `${css.line} ${css.lineDone}`} />
              )}
              <span className={css.node} aria-hidden="true">
                <Icon size={24} strokeWidth={1.75} />
              </span>
            </div>
            <div className={css.card}>
              <span className={css.no} aria-hidden="true">{i + 1}</span>
              <span className={css.who}>{s.who}</span>
              <h2 className={css.title}>{s.title}</h2>
              <p className={css.text}>{s.text}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
