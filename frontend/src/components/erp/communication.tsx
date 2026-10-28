'use client';

/**
 * ►►► **Kommunikation – der Verlauf und die eine Eingabe** (CRM Schritt 2). ◄◄◄
 *
 * Alles ist eine Nachricht, und die Oberfläche kennt keine Art: wie eine Nachricht
 * aussieht, folgt aus ihren Angaben – **rechts**, was von uns kommt (`ours`), **grau**,
 * was das Haus nie verlässt (`channel.outside`), das **Symbol** aus dem Kanal. Ob sie
 * offen oder überfällig ist, sagt der Server; gerechnet wird hier nichts.
 *
 * Die Eingabe hat für E-Mail, Anruf und Intern **dieselbe Form** (Von → An → Betreff → Text →
 * Zeitpunkt). Die drei Knöpfe wählen nur den Kanal und belegen vor. **Geschrieben wird nur
 * im eigenen Namen** – oder, bei einer E-Mail, in dem einer eigenen Gesellschaft: «Von»
 * ist ein Chip wie «An» und wählt unter den **verbundenen** Postfächern.
 *
 * ►►► **Ein Chat je Person – wie WhatsApp.** ◄◄◄ Die **Seite** sagt, wer schreibt (links
 * von aussen, rechts wir, grau intern); eine Kopfzeile gibt es nicht. Den Namen trägt eine
 * Blase nur, wo die Seite ihn nicht schon sagt (ein Kollege, eine zweite Person der Firma).
 * Wer an wen, mit Adressen, steht im Hover.
 *
 * **Das Anliegen ist der Betreff** – klein und farbig oben in der Blase, gleicher Betreff
 * gleiche Farbe (`topicColor`, fest aus dem Betreff abgeleitet). Ein «Antwort auf» gibt es
 * nicht: «Antworten» belegt den **festen** Betreff («Re: » davor, wie Gmail) und **alle**
 * Beteiligten vor (`reply_all`); nur der Absender lässt sich nicht entfernen. Die Antwort
 * erledigt alle offenen Nachrichten dieses Betreffs – das sagt der Server.
 *
 * **Ein Anruf ist eine Nachricht wie jede andere** – auf der Seite dessen, der angerufen
 * hat, mit dem Telefon-Zeichen und «Eingehender/Ausgehender Anruf» darüber.
 *
 * **Der Zustand steht an der Nachricht, nicht darunter**: die Zeit einer offenen wird zur
 * kleinen Marke – orange = wartet, rot = überfällig; eine beantwortete trägt die Zeit grau.
 *
 * **Jede Nachricht hat einen Betreff** – eine Regel für alles, der Dienst verlangt ihn.
 * Steht eine Nachricht offen, ist die Eingabe schon die Antwort darauf (✕ = neu).
 * **Intern heisst intern**: angeboten werden nur Mitarbeiter.
 *
 * **Jede Nachricht wartet drei Sekunden** – Mail, Anruf, Intern («Rückgängig», wie Gmail),
 * und zwar **dort, wo sie hingehört**: blass im Verlauf, mit Uhr und «Rückgängig»; die
 * Eingabe ist so lange gesperrt. Im Browser, nicht auf dem Server – wer die Ansicht
 * verlässt, schickt sie sofort.
 *
 * **Ein Anruf hat genau zwei**: mich und die Person dieses Datensatzes – wählbar ist nur
 * die Richtung. **Cc/Bcc wie in Gmail**: ein Klick klappt das Feld auf, leer verlassen klappt
 * es zu. **Intern stehen die Empfänger vorne im Text** («@Monika Fritsche …») – aus dem «An».
 *
 * **E-Mail geht über das Postfach einer eigenen Gesellschaft** (CRM Schritt 3), verbunden an
 * ihrem Datensatz. Persönliche Postfächer gibt es nicht: im Kommunikationstool ist jeder
 * Benutzer gleich. Gmail ist der Speicher, abgeglichen wird im Hintergrund (`erp/page`).
 *
 * An einer **Firma** ist der Verlauf ein Spiegel: dieselbe Liste, keine Eingabe und kein
 * offen/überfällig – geschrieben wird immer von Person zu Person.
 *
 * ►►► **Drei Versandarten einer E-Mail: Mail · Rundschreiben · Newsletter.** ◄◄◄ Bcc bleibt
 * Bcc. Alle fünf Arten stehen in EINER Leiste (`KindBar`): Mail · Rundschreiben · Newsletter |
 * Anruf · Intern. Ein **Rundschreiben** geht an jede Person einzeln, mit ihrer Anrede – Information,
 * keine Werbung. Ein **Newsletter** ebenso, aber nur an Angemeldete und mit Abmeldelink;
 * das Tor sitzt im Dienst. Die Anrede («Guten Tag Vorname Name») und der Fuss des Newsletters
 * stehen fest in der Eingabe – man sieht, wie es hinausgeht. Im Verlauf steht beides **einmal** («Rundschreiben · an 23»),
 * bei jeder Empfängerin ihre eigene Kopie. Gewählt wird ausdrücklich, Vorgabe ist Mail.
 */

import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { MESSAGES_CHANGED } from '@/lib/feed';
import { qk } from '@/lib/queries';
import type { Mailbox, Message, MessageChannel } from '@/types';
import { Person } from '@/components/erp/communication/shared';
import { Sending, Timeline } from '@/components/erp/communication/timeline';
import { Composer, Target } from '@/components/erp/communication/composer';
import { Mailboxes } from '@/components/erp/communication/mailboxes';

// ─── Die Ansicht ────────────────────────────────────────────────────────────

export function Communication({ person, company, ownCompany, me }: {
  /** Person: Verlauf mit Eingabe. */
  person?: Person;
  /** Firma: der Verlauf ihrer Personen, nur lesend. */
  company?: number;
  /** Eine eigene Gesellschaft – dann steht hier ihr Postfach (nur sie hat eines). */
  ownCompany?: boolean;
  me?: Person | null;
}) {
  // ►►► **Der Verlauf ist eine Query** – geschlüsselt nach der Nummer, nicht nach dem Objekt
  // `person` (ein neues Objekt je Render lud sonst bei jeder Taste neu). Neues aus dem
  // Abgleich und Gesendetes laden über `MESSAGES_CHANGED` nach (`lib/use-feed.ts`). ◄◄◄
  const personId = person?.object_id;
  const scope = personId ? { person: personId } : { company };
  const history = useQuery({
    queryKey: qk.messages(scope),
    queryFn: ({ signal }) => api.getMessages(scope, { signal }),
    meta: { what: 'Verlauf' },
  });
  const messages: Message[] | null = history.data ?? null;
  // Ein Postfach hat nur eine eigene Gesellschaft – es steht an ihrem Datensatz.
  // Persönliche gibt es nicht: im Kommunikationstool ist jeder Benutzer gleich.
  const channels: MessageChannel[] = useQuery({
    queryKey: qk.senders(), queryFn: ({ signal }) => api.messageChannels({ signal }),
    enabled: !!personId, meta: { what: 'Absender' },
  }).data ?? [];
  const mailboxes: Mailbox[] = useQuery({
    queryKey: qk.mailboxes(company ?? 0), queryFn: ({ signal }) => api.mailboxes(company!, { signal }),
    enabled: !!company && !!ownCompany, meta: { what: 'Postfach' },
  }).data ?? [];
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<Target | null>(null);
  const [sending, setSending] = useState<Sending | null>(null);
  const changed = () => window.dispatchEvent(new Event(MESSAGES_CHANGED));
  // «Erledigt ohne Antwort» – eine stille interne Nachricht mit demselben Betreff, die den
  // Absender betrifft: dieselbe Regel wie jede Antwort, kein Sonderfall.
  const done = (m: Message) => {
    if (!person) return;
    api.createMessage({ channel: 'intern', about: [m.sender.object_id], subject: m.reply_subject || null,
      body: '', incoming: false, delivery: 'mail' })
      .then(changed).catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht gespeichert werden.'));
  };
  const writable = !!person && !!me && channels.length > 0;
  // ►►► Steht etwas offen, ist die Eingabe schon die Antwort darauf – die jüngste offene,
  // einmal beim Öffnen und ohne Sprung (✕ macht daraus eine neue Nachricht). ◄◄◄
  const primed = useRef(false);
  useEffect(() => {
    if (primed.current || !writable || !messages) return;
    primed.current = true;
    const open = messages.filter((m) => m.open);
    if (open.length) setTarget({ m: open[open.length - 1], n: Date.now(), quiet: true });
  }, [messages, writable]);
  // Die Anliegen dieser Person – zur Auswahl im Betreff, das jüngste zuerst.
  const topics = [...new Set((messages ?? []).map((m) => m.topic).filter(Boolean).reverse())];

  if (!messages && history.error) {
    return <p style={{ color: 'var(--danger)', fontSize: 13 }}>{history.error.message || 'Konnte nicht geladen werden.'}</p>;
  }
  if (!messages) return <p style={{ color: 'var(--fg-3)', fontSize: 13 }}>Lädt …</p>;
  return (
    <div>
      {error && <p style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</p>}
      <Mailboxes boxes={mailboxes} />
      {/* ►►► Der Verlauf steht bei der JÜNGSTEN Nachricht. ◄◄◄ `column-reverse` verankert das
          Rollen am unteren Ende: ohne Skript beim Öffnen unten, eine neue Nachricht bleibt im
          Blick, und «ältere laden» schiebt nichts weg. Höhe begrenzt, damit die Stammdaten
          darunter erreichbar bleiben; oben läuft der Verlauf weich aus. */}
      <div style={{ maxHeight: 'min(60vh, 560px)', overflowY: 'auto', display: 'flex',
        flexDirection: 'column-reverse',
        maskImage: 'linear-gradient(to bottom, transparent 0, #000 32px)',
        WebkitMaskImage: 'linear-gradient(to bottom, transparent 0, #000 32px)' }}>
      <div>
      <Timeline key={person?.object_id ?? company} messages={messages} mirror={!person} personId={person?.object_id} meId={me?.object_id}
        onReply={writable ? (m) => setTarget({ m, n: Date.now() }) : undefined}
        onDone={writable ? done : undefined} sending={sending} />
      </div>
      </div>
      {writable && person && me && (
        <Composer key={person.object_id} person={person} me={me} channels={channels}
          target={target} topics={topics} onSent={changed} onSending={setSending} />
      )}
    </div>
  );
}
