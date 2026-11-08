/**
 * ►►► **Das «+» auf der Website – nur für Personal.** ◄◄◄
 *
 * Wer als Mitarbeiter oder Admin angemeldet ist (`html[data-account="staff"]`, der
 * Anzeige-Cache aus scripts/early.js), sieht unten rechts dasselbe «+» wie im ERP. Es ist kein
 * Nachbau: ein Tipp öffnet die ERP-Seite `/erp/erfassen` in einem Rahmen über der Seite – mit
 * ihrer eigenen Anmeldung und Prüfung (wer kein Personal ist, kommt dort nicht hinein). Die
 * Stecknadel zeigt von dort aus auf diese Seite (gleicher Ursprung); das Gespräch mit dem
 * Assistenten (auch Foto und Datei) läuft im Rahmen, «Neu anlegen» und «Entwurf öffnen» springen
 * ins ERP.
 *
 * Alle anderen sehen nichts, und die Seite lädt dafür nichts. Nur auf der Website
 * (`html[data-site]`): Konto und ERP tragen dasselbe Skript als Teil des gemeinsamen Kopfs mit –
 * dort tut es nichts (das ERP hat sein «+»).
 *
 * Gesprochen wird über `postMessage` vom selben Ursprung: `ready` (erst dann wird der Rahmen
 * sichtbar – vorher sähe man die Seite laden) und `close`.
 */
const FRAME_ID = 'ix-capture-frame';
const FAB_ID = 'ix-capture-fab';
const SOURCE = 'inexxio-capture';
/** So lange darf die eingebettete Seite brauchen, bis sie bereit ist – auch nach einem
 *  Kaltstart des Dienstes (der beim Start erst die Datenbank prüft). */
const READY_MS = 45_000;

function staff(): boolean {
  return document.documentElement.dataset.account === 'staff';
}

function close(): void {
  document.getElementById(FRAME_ID)?.remove();
  document.documentElement.classList.remove('ix-capture-open', 'ix-capture-ready');
  document.getElementById(FAB_ID)?.removeAttribute('aria-busy');
  document.getElementById(FAB_ID)?.focus();
}

function open(): void {
  if (document.getElementById(FRAME_ID)) return;
  const frame = document.createElement('iframe');
  frame.id = FRAME_ID;
  frame.className = 'ix-capture-frame';
  frame.title = 'Assistent';
  frame.src = '/erp/erfassen';
  // Aufnehmen (Mikrofon) und Fotografieren gehen im Rahmen nur mit ausdrücklicher Erlaubnis.
  frame.allow = 'microphone; camera; screen-wake-lock';
  document.body.appendChild(frame);
  document.documentElement.classList.add('ix-capture-open');
  // Bis die Seite bereit ist, sagt der Knopf, dass er lädt – ein Tipp ist nie still.
  document.getElementById(FAB_ID)?.setAttribute('aria-busy', 'true');
  // Meldet sich die Seite nicht (abgemeldet, kein Netz), nicht unsichtbar hängen bleiben: ins
  // ERP – dort geht es zur Anmeldung oder es sagt, was fehlt.
  window.setTimeout(() => {
    if (document.getElementById(FRAME_ID) === frame && !frame.classList.contains('is-ready')) {
      close();
      location.href = '/erp';
    }
  }, READY_MS);
}

function onMessage(e: MessageEvent): void {
  if (e.origin !== location.origin) return;
  const data = e.data as { source?: string; what?: string } | null;
  if (!data || data.source !== SOURCE) return;
  const frame = document.getElementById(FRAME_ID) as HTMLIFrameElement | null;
  // Nur unser Rahmen spricht hier – kein anderes Fenster desselben Ursprungs.
  if (!frame || e.source !== frame.contentWindow) return;
  if (data.what === 'ready') {
    frame.classList.add('is-ready');
    document.documentElement.classList.add('ix-capture-ready');
    document.getElementById(FAB_ID)?.removeAttribute('aria-busy');
  }
  if (data.what === 'close') close();
}

function fab(): HTMLButtonElement {
  const b = document.createElement('button');
  b.id = FAB_ID;
  b.type = 'button';
  b.className = 'ix-capture-fab';
  b.setAttribute('aria-label', 'Assistent');
  b.title = 'Assistent – sagen, was ist, aufnehmen, auf eine Stelle zeigen';
  b.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    + 'stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>';
  b.addEventListener('click', open);
  return b;
}

/** Zeigt oder entfernt das «+» je nach Anmeldezustand – auch wenn er sich später ändert. */
function sync(): void {
  const there = document.getElementById(FAB_ID);
  if (staff()) {
    if (!there) document.body.appendChild(fab());
  } else {
    there?.remove();
    close();
  }
}

export function initCapture(): void {
  if (!document.documentElement.hasAttribute('data-site')) return;
  window.addEventListener('message', onMessage);
  sync();
  // Der Anmeldezustand kommt aus dem Anzeige-Cache und kann sich ändern (Anmelden, Abmelden).
  new MutationObserver(sync).observe(document.documentElement, { attributes: true, attributeFilter: ['data-account'] });
}
