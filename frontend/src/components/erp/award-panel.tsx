'use client';

import { useEffect, useState } from 'react';
import {
  Ban, Check, FileText, Handshake, MapPin, PackageCheck, Send, Tags, TriangleAlert,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { Award } from '@/types';
import { AWARD_CHANNELS, awardChannel } from '@/lib/vergabe-catalog';
import { TONE } from '@/lib/status-flow';
import { formatObjectId } from '@/lib/utils';
import { ObjId } from '@/components/erp/obj-id';
import { PaletteButton, Palette, numericInputProps, numericOnly } from '@/components/erp/fields';

/**
 * **Die Vergabe — EIN Bauteil für den ganzen Zyklus** (PROCESS_CORE §15.5).
 *
 * Eine Vergabe ist der Vorgang «ein Dritter erbringt eine Leistung für uns»: heute ein
 * Transport, morgen eine Beschaffung. Darum steht sie hier **einmal** und nicht je
 * Aufrufstelle neu – der Anlass wird als Objektnummer hereingereicht, mehr braucht sie
 * nicht zu wissen.
 *
 * ## Drei Regeln, und alle drei kommen aus den Daten
 *
 * 1. **Angeboten wird, was der Dienst annimmt.** Welche Handlungen von hier aus möglich
 *    sind, sagt `next_states` – die Oberfläche rechnet die Übergangsmatrix nicht nach.
 *    Ein Knopf, der scheitert, ist schlimmer als keiner; und eine zweite Matrix hier
 *    wäre die Stelle, die man beim nächsten Zustand vergisst.
 * 2. **Der Zustand ist eine Auskunft, kein Eingabefeld.** Es gibt kein Status-Dropdown:
 *    geschrieben wird eine **Handlung**, welcher Zustand daraus folgt, entscheidet die
 *    Registry.
 * 3. **Beschriftung und Ampelton reisen mit** (`state_label`, `state_tone`). Eine
 *    Tabelle hier wäre die zweite – und sie veraltet stillschweigend.
 *
 * **Das System vergibt nie selbst.** Es darf Angebote holen und das günstigste
 * vorwählen; die Wahl trifft ein Mensch. Darum ist der günstigste Vorschlag
 * hervorgehoben, aber jeder andere genauso anklickbar – sonst wäre es keine Wahl.
 */
export function AwardPanel({ award, subjectObjectId, targetObjectId, unitIds = [],
                             busy, onQuote, onChanged }: {
  /** Die **offene** Vergabe – `null`, solange niemand angefragt hat. */
  award: Award | null;
  /** Der Anlass. Bei einem Transport der Ausgangsort. */
  subjectObjectId: number;
  targetObjectId: number | null;
  /** Die Stücke, die bei einer Abnahme **angekommen** sind. */
  unitIds?: number[];
  busy?: boolean;
  /**
   * **Tarife holen** – der Aufruf steht am **Modul**, nicht an der Vergabe: dort wohnt
   * die Fuhre. Fehlt er, gibt es den Knopf nicht (statt eines, der nichts tut).
   */
  onQuote?: () => Promise<void>;
  onChanged: (next: Award) => void;
}) {
  const [pending, setPending] = useState(false);
  const working = busy || pending;

  async function act(run: () => Promise<Award>) {
    setPending(true);
    try {
      onChanged(await run());
    } finally {
      setPending(false);
    }
  }

  if (!award) {
    return (
      <RequestRow subjectObjectId={subjectObjectId} targetObjectId={targetObjectId}
        busy={working} onRequested={onChanged} />
    );
  }

  const tone = TONE[(award.state_tone as 'pending' | 'done' | 'danger') ?? 'pending'];
  const channel = awardChannel(award.channel);
  const can = (state: string) => (award.next_states ?? []).includes(state);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Handshake size={13} style={{ flex: 'none', color: 'var(--fg-4)' }} />
        <span className="text-[11px] px-1.5 py-0.5 rounded-full"
          style={{ color: tone.color, background: tone.bg, fontWeight: 600 }}>
          {award.state_label}
        </span>
        {channel && (
          <span className="text-[11.5px]" style={{ color: 'var(--fg-3)' }}
            data-tip={channel.hint}>
            {channel.label}
          </span>
        )}
        {(award.provider || award.provider_name) && (
          <span className="text-[11.5px] truncate" style={{ color: 'var(--fg-3)' }}>
            {award.provider?.name ?? award.provider_name
              ?? formatObjectId(award.provider!.object_id)}
            {award.amount != null && ` · ${award.amount} ${award.currency ?? ''}`}
          </span>
        )}
      </div>

      {/* Der Grund gehört zum Ende: ohne ihn stünde da, dass es nicht geklappt hat,
          aber nicht warum. */}
      {award.reason && (
        <p className="text-[11.5px]" style={{ color: 'var(--fg-3)' }}>{award.reason}</p>
      )}

      {(award.offers ?? []).length > 0 && (
        <OfferList award={award} busy={working}
          onGrant={(offerId) => act(() => api.grantAward(award.id, offerId))} />
      )}

      {/* Was der Kauf hervorgebracht hat – eine **Tatsache über die Sendung**. */}
      {(award.label_url || award.tracking_number) && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {award.label_url && (
            <a href={award.label_url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11.5px]"
              style={{ color: 'var(--accent)' }}>
              <FileText size={12} /> Etikett
            </a>
          )}
          {award.tracking_number && (
            <span className="inline-flex items-center gap-1 text-[11.5px]"
              style={{ color: 'var(--fg-3)' }}>
              <MapPin size={12} />
              {award.tracking_url
                ? <a href={award.tracking_url} target="_blank" rel="noopener noreferrer"
                    style={{ color: 'var(--accent)' }}>{award.tracking_number}</a>
                : award.tracking_number}
            </span>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-1.5">
        {/* **Tarife werden nie von selbst geholt** (§15.7): ein Abruf beim Öffnen wäre
            ein Vorgang bei einem Dritten, den niemand bestellt hat – und bei manchen
            Anbietern kostet er. */}
        {onQuote && award.channel === 'plattform' && award.open && (
          <Action icon={Tags} label="Tarife holen" busy={working}
            hint="Fragt alle eingerichteten Frachtführer – eine Ausschreibung, die 2 Sekunden dauert."
            onClick={() => { setPending(true); void onQuote().finally(() => setPending(false)); }} />
        )}
        {award.tracking_number && award.open && (
          <Action icon={MapPin} label="Sendung verfolgen" busy={working}
            hint="Zugestellt? Dann entsteht die Ablage – dieselbe eine Stelle wie ein Scan."
            onClick={() => act(() => api.trackAward(award.id).then((r) => r.award))} />
        )}
        {/* «Selbst bestellt» kennt keine Angebote – dort wird unmittelbar vergeben. */}
        {can('vergeben') && !channel?.offers && (
          <DirectGrant awardId={award.id} busy={working}
            onGranted={(a) => onChanged(a)} />
        )}
        {can('erbracht') && (
          <Action icon={PackageCheck} label="Erbracht" busy={working}
            hint={'Der Dritte hat geliefert. WO die Stücke liegen, sagt der Scan am Ziel – '
                  + 'nicht dieser Knopf: der Ort ist eine Beobachtung.'}
            onClick={() => act(() => api.deliverAward(award.id, unitIds))} />
        )}
        {can('abgelehnt') && (
          <WithReason icon={Ban} label="Ablehnen" placeholder="Warum nicht?"
            busy={working} required={false}
            onSubmit={(r) => act(() => api.rejectAward(award.id, r))} />
        )}
        {can('gescheitert') && (
          <WithReason icon={TriangleAlert} label="Gescheitert" required
            placeholder="Was ist passiert? (Pflicht)" busy={working}
            onSubmit={(r) => act(() => api.failAward(award.id, r))} />
        )}
      </div>
    </div>
  );
}

/**
 * **Anfragen — der Klick eines Menschen** (§15.7).
 *
 * Das System legt nie von sich aus eine Vergabe an. Genau daran sind die abgeleitete
 * Bereitstellung und die Begleit-Bewegungen des Vorgängers gescheitert: es entstanden
 * Vorgänge, die niemand bestellt hatte, und niemand traute sich, sie zu löschen.
 *
 * Die Kanäle kommen aus dem **generierten** Katalog – ein neuer Kanal ist eine Zeile im
 * Backend und hier ohne Zutun wählbar.
 */
function RequestRow({ subjectObjectId, targetObjectId, busy, onRequested }: {
  subjectObjectId: number;
  targetObjectId: number | null;
  busy?: boolean;
  onRequested: (a: Award) => void;
}) {
  const [pending, setPending] = useState(false);
  /**
   * **Welche Kanäle jetzt wählbar sind.** Der generierte Katalog sagt, welche es *gibt*;
   * ob einer *heute* benutzbar ist, ist eine Laufzeit-Tatsache – ohne eingerichteten
   * Frachtführer gibt es «Plattform» nicht, und er erscheint dann **gar nicht**, statt
   * dazustehen und zu scheitern.
   */
  const [usable, setUsable] = useState<Record<string, string | null> | null>(null);
  useEffect(() => {
    let alive = true;
    void api.awardChannels()
      .then((rows) => alive && setUsable(Object.fromEntries(
        rows.map((r) => [r.value, r.available ? null : (r.reason ?? 'nicht verfügbar')]))))
      .catch(() => alive && setUsable({}));
    return () => { alive = false; };
  }, []);

  // Solange die Antwort aussteht, wird nichts angeboten: ein Knopf, der gleich wieder
  // verschwindet, ist schlimmer als einer, der kurz später erscheint.
  const shown = AWARD_CHANNELS.filter((c) => usable && usable[c.value] === null);
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11.5px]" style={{ color: 'var(--fg-3)' }}>
        Versand – ein Dritter muss das erbringen. Über welchen Weg?
      </span>
      <Palette style={{ justifyContent: 'flex-start' }}>
        {shown.map((c) => (
          <PaletteButton key={c.value} icon={Send} label={c.label}
            tone="var(--fg-2)" bg="var(--bg-2)" border="var(--border-1)"
            disabled={busy || pending}
            onClick={() => {
              setPending(true);
              void api.requestAward(subjectObjectId, targetObjectId, c.value)
                .then(onRequested)
                .finally(() => setPending(false));
            }} />
        ))}
      </Palette>
    </div>
  );
}

/**
 * **Die Angebote — günstigstes zuerst, aber jedes wählbar.**
 *
 * Die Reihenfolge ist die **Vorwahl** des Systems; sie kommt aus dem Dienst, damit
 * «am besten» nicht in einem Adapter entschieden wird. Die **Wahl** ist ein Klick, und
 * sie darf auf das teurere fallen – wer das verbietet, hat aus der Vorwahl eine Wahl
 * gemacht und den Menschen aus dem Vorgang genommen.
 */
function OfferList({ award, busy, onGrant }: {
  award: Award;
  busy?: boolean;
  onGrant: (offerId: number) => void;
}) {
  const offers = award.offers ?? [];
  const canGrant = (award.next_states ?? []).includes('vergeben');
  return (
    <div className="flex flex-col">
      {offers.map((o, i) => (
        <div key={o.id}
          className="flex flex-wrap items-center gap-x-2 gap-y-0.5 py-1"
          style={{ borderTop: i ? '1px solid var(--border-1)' : undefined }}>
          <span className="text-xs" style={{
            color: 'var(--fg-2)', fontWeight: i === 0 ? 600 : 500,
            fontVariantNumeric: 'tabular-nums',
          }}>
            {o.amount} {o.currency}
          </span>
          {o.days != null && (
            <span className="text-[11.5px]" style={{ color: 'var(--fg-3)' }}>
              {o.days} Tage
            </span>
          )}
          {/* **Der Anbieter ist ein Datensatz ODER ein Name.** Ein Frachtführer ist
              keiner – einen anzulegen wäre erfundene Daten. */}
          {o.provider
            ? <span className="text-[11.5px] truncate" style={{ color: 'var(--fg-3)' }}>
                {o.provider.name ?? <ObjId value={o.provider.object_id} />}
              </span>
            : o.provider_name && (
              <span className="text-[11.5px] truncate" style={{ color: 'var(--fg-3)' }}>
                {o.provider_name}
              </span>
            )}
          {i === 0 && offers.length > 1 && (
            <span className="text-[10.5px]" style={{ color: 'var(--fg-4)' }}
              data-tip="Vorgewählt, nicht entschieden – die Wahl trifft ein Mensch.">
              günstigstes
            </span>
          )}
          {award.chosen_offer_id === o.id && (
            <Check size={13} className="ml-auto" style={{ color: 'var(--success)' }} />
          )}
          {canGrant && award.chosen_offer_id !== o.id && (
            <button type="button" disabled={busy} onClick={() => onGrant(o.id)}
              className="ml-auto text-[11.5px] px-2 py-0.5 rounded-md erp-actbtn">
              Vergeben
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * **Vergeben ohne Angebot** – nur beim Kanal «Selbst bestellt».
 *
 * Dort gibt es keinen Angebotsvergleich; Dritter und Preis stehen von Anfang an fest,
 * und der Vorgang wird dokumentiert. Der Betrag ist optional: manchmal weiss man ihn
 * erst mit der Rechnung, und eine erfundene Zahl wäre schlechter als keine.
 */
function DirectGrant({ awardId, busy, onGranted }: {
  awardId: number;
  busy?: boolean;
  onGranted: (a: Award) => void;
}) {
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState('');
  const [amount, setAmount] = useState('');

  if (!open) {
    return <Action icon={Handshake} label="Vergeben" busy={busy}
      hint="Selbst bestellt – wer erbringt die Leistung?"
      onClick={() => setOpen(true)} />;
  }
  const id = Number(provider);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <input value={provider} onChange={(e) => setProvider(numericOnly(e.target.value))}
        placeholder="Objektnummer des Dritten" {...numericInputProps}
        className="text-xs px-2 py-1 rounded-md border" style={{ width: 170 }} />
      <input value={amount} onChange={(e) => setAmount(numericOnly(e.target.value, { decimals: true }))}
        placeholder="Betrag (optional)" {...numericInputProps}
        className="text-xs px-2 py-1 rounded-md border" style={{ width: 130 }} />
      <button type="button" disabled={busy || !id}
        className="text-[11.5px] px-2 py-1 rounded-md erp-actbtn erp-actbtn-primary"
        onClick={() => {
          void api.grantAward(awardId, null, {
            providerObjectId: id,
            amount: amount ? Number(amount) : undefined,
          }).then((a) => { setOpen(false); onGranted(a); });
        }}>
        Vergeben
      </button>
    </div>
  );
}

/**
 * Eine Handlung, die einen **Grund** braucht (oder annimmt).
 *
 * Beim Scheitern ist er Pflicht – durchgesetzt serverseitig; hier bleibt der Knopf
 * gesperrt, damit man nicht in eine Fehlermeldung läuft.
 */
function WithReason({ icon, label, placeholder, required, busy, onSubmit }: {
  icon: React.ElementType;
  label: string;
  placeholder: string;
  required: boolean;
  busy?: boolean;
  onSubmit: (reason: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  if (!open) {
    return <Action icon={icon} label={label} busy={busy} onClick={() => setOpen(true)} />;
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder}
        autoFocus className="text-xs px-2 py-1 rounded-md border" style={{ width: 240 }} />
      <button type="button" disabled={busy || (required && !text.trim())}
        className="text-[11.5px] px-2 py-1 rounded-md erp-actbtn"
        onClick={() => { setOpen(false); onSubmit(text); }}>
        {label}
      </button>
    </div>
  );
}

function Action({ icon: Icon, label, hint, busy, onClick }: {
  icon: React.ElementType;
  label: string;
  hint?: string;
  busy?: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" disabled={busy} onClick={onClick} data-tip={hint}
      className="flex items-center gap-1 text-[11.5px] px-2 py-1 rounded-md erp-actbtn">
      <Icon size={13} />
      {label}
    </button>
  );
}
