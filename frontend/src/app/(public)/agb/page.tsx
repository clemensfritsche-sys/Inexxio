'use client';

import { useState } from 'react';
import { Printer } from 'lucide-react';

const VERSION = '1.0';
const VALID_FROM = '01.01.2026';

export default function AGBPage() {
  const [activeTab, setActiveTab] = useState<'b2b' | 'b2c'>('b2b');

  return (
    <div className="min-h-screen bg-white">
      {/* Hero */}
      <section className="bg-slate-900 py-16">
        <div className="container">
          <h1 className="text-4xl font-bold text-white">Allgemeine Geschäftsbedingungen</h1>
          <p className="mt-2 text-slate-400">
            Version {VERSION} | Gültig ab {VALID_FROM}
          </p>
        </div>
      </section>

      <section className="section">
        <div className="container max-w-4xl">
          {/* Tab Navigation */}
          <div className="mb-8 flex items-center justify-between gap-4 flex-wrap">
            <div className="flex rounded-xl border border-slate-200 bg-slate-50 p-1">
              <button
                onClick={() => setActiveTab('b2b')}
                className={`rounded-lg px-5 py-2 text-sm font-medium transition-all ${
                  activeTab === 'b2b'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Für Geschäftskunden (B2B)
              </button>
              <button
                onClick={() => setActiveTab('b2c')}
                className={`rounded-lg px-5 py-2 text-sm font-medium transition-all ${
                  activeTab === 'b2c'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Für Endkunden (B2C)
              </button>
            </div>
            <button
              onClick={() => window.print()}
              className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 print:hidden"
            >
              <Printer className="h-4 w-4" />
              Drucken
            </button>
          </div>

          {/* B2B Terms */}
          {activeTab === 'b2b' && (
            <div className="prose prose-slate max-w-none">
              <div className="mb-6 rounded-lg bg-blue-50 border border-blue-200 px-4 py-3">
                <p className="text-sm text-blue-800 font-medium">
                  Diese Allgemeinen Verkaufsbedingungen gelten für alle Lieferungen und Leistungen
                  der Inexxio AG an Geschäftskunden.
                </p>
              </div>

              <Section title="§ 1 Geltungsbereich">
                <p>
                  Diese Allgemeinen Verkaufsbedingungen (nachfolgend «AVB») gelten für alle
                  Lieferungen, Leistungen und Angebote der Inexxio AG, Schweiz (nachfolgend
                  «Inexxio»), an Geschäftskunden (nachfolgend «Käufer»). Als Geschäftskunden gelten
                  natürliche oder juristische Personen, die das Rechtsgeschäft in Ausübung ihrer
                  gewerblichen oder beruflichen Tätigkeit abschliessen.
                </p>
                <p className="mt-3">
                  Abweichende Bedingungen des Käufers werden nur anerkannt, wenn Inexxio ihrer
                  Geltung ausdrücklich und schriftlich zugestimmt hat. Diese AVB gelten auch für
                  künftige Geschäfte, ohne dass es eines erneuten ausdrücklichen Hinweises bedarf.
                </p>
              </Section>

              <Section title="§ 2 Angebote und Auftragsbestätigung">
                <p>
                  Angebote von Inexxio sind freibleibend und unverbindlich, sofern sie nicht
                  ausdrücklich als verbindlich bezeichnet werden. Angebote sind 30 Tage ab
                  Ausstellungsdatum gültig, sofern keine andere Frist angegeben wird.
                </p>
                <p className="mt-3">
                  Ein Vertrag kommt erst durch die schriftliche Auftragsbestätigung von Inexxio
                  zustande oder durch den Beginn der Leistungserbringung. Mündliche
                  Nebenabreden, Zusagen und Zusicherungen bedürfen zu ihrer Wirksamkeit der
                  schriftlichen Bestätigung durch Inexxio.
                </p>
                <p className="mt-3">
                  Für kundenspezifische Konstruktions- und Entwicklungsleistungen gilt: Technische
                  Zeichnungen, Spezifikationen und sonstige Unterlagen bleiben Eigentum von Inexxio
                  und dürfen ohne ausdrückliche Zustimmung nicht vervielfältigt, an Dritte
                  weitergegeben oder anderweitig genutzt werden.
                </p>
              </Section>

              <Section title="§ 3 Preise und Zahlungsbedingungen">
                <p>
                  Alle Preise verstehen sich in Schweizer Franken (CHF), zuzüglich der gesetzlichen
                  Mehrwertsteuer zum jeweils gültigen Satz, sofern nicht ausdrücklich anders
                  vereinbart.
                </p>
                <p className="mt-3">
                  Rechnungen sind innert 30 Tagen netto fällig, sofern keine abweichende Vereinbarung
                  getroffen wurde. Bei Zahlung innert 10 Tagen wird ein Skonto von 2% gewährt.
                  Inexxio behält sich vor, für Erstkunden oder bei fehlender Bonität Vorauszahlung
                  zu verlangen.
                </p>
                <p className="mt-3">
                  Bei Zahlungsverzug werden Verzugszinsen in Höhe von 5% p.a. sowie eine
                  Mahngebühr von CHF 20.– pro Mahnung erhoben. Inexxio behält sich das Recht vor,
                  bei Zahlungsverzug die weitere Leistungserbringung einzustellen und fällige
                  Forderungen sofort einzuziehen.
                </p>
                <p className="mt-3">
                  Bei wesentlichen Veränderungen der Einstandspreise (insbesondere Rohmaterial,
                  Energie, Fremdleistungen) behält Inexxio sich das Recht vor, Preisanpassungen
                  vorzunehmen und den Käufer rechtzeitig zu informieren.
                </p>
              </Section>

              <Section title="§ 4 Lieferung und Gefahrenübergang">
                <p>
                  Liefertermine sind unverbindlich, sofern nicht ausdrücklich schriftlich als
                  verbindlich bestätigt. Teillieferungen sind zulässig und können separat
                  in Rechnung gestellt werden.
                </p>
                <p className="mt-3">
                  Sofern nichts anderes vereinbart wird, erfolgt die Lieferung ab Werk (EXW,
                  Incoterms 2020). Die Gefahr geht mit der Übergabe an den ersten Frachtführer auf
                  den Käufer über. Transportversicherungen werden nur auf ausdrückliche Anfrage und
                  auf Kosten des Käufers abgeschlossen.
                </p>
                <p className="mt-3">
                  Lieferverzögerungen infolge höherer Gewalt (u.a. Streik, Naturkatastrophen,
                  Pandemien, Rohstoffengpässe, behördliche Anordnungen) berechtigen den Käufer
                  nicht zum Rücktritt vom Vertrag oder zu Schadensersatzforderungen, sofern Inexxio
                  den Käufer unverzüglich informiert.
                </p>
              </Section>

              <Section title="§ 5 Eigentumsvorbehalt">
                <p>
                  Die gelieferte Ware bleibt bis zur vollständigen Bezahlung aller Forderungen aus
                  der Geschäftsbeziehung Eigentum von Inexxio (Eigentumsvorbehalt). Der Käufer ist
                  verpflichtet, die Vorbehaltsware pfleglich zu behandeln, ausreichend zu versichern
                  und bei drohenden Zugriffen Dritter Inexxio unverzüglich zu informieren.
                </p>
                <p className="mt-3">
                  Die Weiterveräusserung der Vorbehaltsware ist nur im ordentlichen Geschäftsgang
                  gestattet. Der Käufer tritt bereits jetzt alle Forderungen, die ihm aus der
                  Weiterveräusserung der Vorbehaltsware gegenüber seinen Abnehmern entstehen, zur
                  Sicherheit an Inexxio ab.
                </p>
              </Section>

              <Section title="§ 6 Gewährleistung und Mängelrüge">
                <p>
                  Offensichtliche Mängel sind unverzüglich, spätestens innert 10 Werktagen nach
                  Erhalt der Ware schriftlich zu rügen. Versteckte Mängel sind unverzüglich nach
                  Entdeckung schriftlich anzuzeigen (Rügepflicht gem. OR Art. 201). Unterlässt der
                  Käufer die rechtzeitige Rüge, gilt die Ware als genehmigt.
                </p>
                <p className="mt-3">
                  Die Gewährleistungspflicht beträgt 1 Jahr ab Lieferdatum. Bei berechtigter,
                  rechtzeitiger Mängelrüge hat Inexxio das Recht zur Nachbesserung (Reparatur) oder
                  Ersatzlieferung. Schlägt die Nacherfüllung zweimal fehl, kann der Käufer
                  Preisminderung verlangen oder – bei erheblichen Mängeln – vom Vertrag zurücktreten.
                </p>
                <p className="mt-3">
                  Die Gewährleistung entfällt bei unsachgemässer Handhabung, eigenmächtiger
                  Modifikation oder Reparatur durch den Käufer oder Dritte ohne schriftliche
                  Zustimmung von Inexxio.
                </p>
              </Section>

              <Section title="§ 7 Haftungsbeschränkung">
                <p>
                  Die Haftung von Inexxio für Schäden aus oder im Zusammenhang mit dem Vertrag ist
                  auf direkte Schäden begrenzt und auf den Betrag der betreffenden Rechnung
                  beschränkt. Eine Haftung für indirekte Schäden, entgangenen Gewinn,
                  Produktionsausfall oder Folgeschäden ist – soweit gesetzlich zulässig –
                  ausgeschlossen.
                </p>
                <p className="mt-3">
                  Diese Haftungsbeschränkung gilt nicht bei Vorsatz oder grober Fahrlässigkeit von
                  Inexxio, bei Verletzung von Leben, Körper oder Gesundheit sowie bei
                  Verletzung wesentlicher Vertragspflichten.
                </p>
              </Section>

              <Section title="§ 8 Geheimhaltung">
                <p>
                  Beide Parteien verpflichten sich, alle im Rahmen der Geschäftsbeziehung
                  erhaltenen vertraulichen Informationen (insbesondere technische Daten, Preise,
                  Geschäftsstrategien) geheim zu halten und ausschliesslich zur Erfüllung des
                  Vertrags zu verwenden.
                </p>
                <p className="mt-3">
                  Diese Geheimhaltungspflicht gilt noch 3 Jahre nach Beendigung der
                  Vertragsbeziehung. Ausgenommen sind Informationen, die allgemein bekannt sind
                  oder dem Empfänger bereits bekannt waren.
                </p>
              </Section>

              <Section title="§ 9 Datenschutz">
                <p>
                  Die Verarbeitung personenbezogener Daten von Kontaktpersonen des Käufers erfolgt
                  gemäss unserer Datenschutzerklärung unter{' '}
                  <a href="/datenschutz" className="text-blue-600 hover:underline">
                    inexxio.com/datenschutz
                  </a>
                  . Grundlage der Verarbeitung sind das Schweizer DSG (01.09.2023) und die DSGVO.
                </p>
              </Section>

              <Section title="§ 10 Anwendbares Recht und Gerichtsstand">
                <p>
                  Es gilt ausschliesslich Schweizer Recht, unter Ausschluss des
                  UN-Kaufrechts (CISG). Ausschliesslicher Gerichtsstand für alle Streitigkeiten
                  aus oder im Zusammenhang mit diesem Vertrag ist der Sitz von Inexxio in der
                  Schweiz. Inexxio behält sich vor, den Käufer an seinem allgemeinen Gerichtsstand
                  zu belangen.
                </p>
              </Section>

              <Section title="§ 11 Schlussbestimmungen" isLast>
                <p>
                  Sollten einzelne Bestimmungen dieser AVB ganz oder teilweise unwirksam sein oder
                  werden, berührt dies die Wirksamkeit der übrigen Bestimmungen nicht. Die
                  unwirksame Bestimmung wird durch eine wirksame ersetzt, die dem wirtschaftlichen
                  Zweck der unwirksamen Bestimmung am nächsten kommt.
                </p>
                <p className="mt-3">
                  Änderungen und Ergänzungen zu diesen AVB bedürfen zu ihrer Wirksamkeit der
                  Schriftform.
                </p>
                <p className="mt-4 text-sm text-slate-500">
                  Version {VERSION} | Gültig ab {VALID_FROM} | Inexxio AG
                </p>
              </Section>
            </div>
          )}

          {/* B2C Terms */}
          {activeTab === 'b2c' && (
            <div className="prose prose-slate max-w-none">
              <div className="mb-6 rounded-lg bg-blue-50 border border-blue-200 px-4 py-3">
                <p className="text-sm text-blue-800 font-medium">
                  Diese Allgemeinen Geschäftsbedingungen gelten für alle Käufe über den
                  Online-Shop von Inexxio AG durch Endverbraucher.
                </p>
              </div>

              <Section title="§ 1 Geltungsbereich">
                <p>
                  Diese Allgemeinen Geschäftsbedingungen (nachfolgend «AGB») gelten für alle über
                  den Online-Shop www.inexxio.com (nachfolgend «Shop») abgeschlossenen Kaufverträge
                  zwischen der Inexxio AG, Schweiz (nachfolgend «Inexxio» oder «wir»), und
                  Endverbrauchern (nachfolgend «Kunde»).
                </p>
                <p className="mt-3">
                  Verbraucher im Sinne dieser AGB ist jede natürliche Person, die ein Rechtsgeschäft
                  zu einem Zweck abschliesst, der überwiegend weder ihrer gewerblichen noch ihrer
                  selbständigen beruflichen Tätigkeit zugerechnet werden kann.
                </p>
              </Section>

              <Section title="§ 2 Vertragsschluss">
                <p>
                  Die Präsentation der Produkte im Online-Shop stellt kein verbindliches Angebot
                  dar, sondern eine unverbindliche Aufforderung zur Abgabe eines Angebots.
                </p>
                <p className="mt-3">
                  Durch Klicken auf den Button «Kostenpflichtig bestellen» geben Sie eine
                  verbindliche Bestellung der im Warenkorb befindlichen Produkte auf. Die
                  Auftragsbestätigung per E-Mail bestätigt den Eingang Ihrer Bestellung und
                  stellt die Annahme Ihres Angebots dar. Der Kaufvertrag kommt mit dem Versand
                  dieser Bestätigung zustande.
                </p>
                <p className="mt-3">
                  Sie erhalten die Vertragsunterlagen (Bestellbestätigung, AGB,
                  Datenschutzerklärung) per E-Mail sowie einen Rechnungslink in Ihrem Kundenkonto.
                </p>
              </Section>

              <Section title="§ 3 Preise und Zahlungsbedingungen">
                <p>
                  Alle Preise verstehen sich in Schweizer Franken (CHF) inklusive der gesetzlichen
                  Mehrwertsteuer zum jeweils gültigen Satz. Die Versandkosten werden im
                  Checkout-Prozess gesondert ausgewiesen.
                </p>
                <p className="mt-3">
                  Wir akzeptieren folgende Zahlungsmittel: Kreditkarte (Visa, Mastercard), TWINT
                  und Banküberweisung. Die Zahlung ist mit Bestellabschluss fällig.
                </p>
                <p className="mt-3">
                  Bei Zahlung per Banküberweisung erhalten Sie die Kontoverbindung in der
                  Bestellbestätigung. Die Ware wird erst nach vollständigem Zahlungseingang
                  versandt.
                </p>
              </Section>

              <Section title="§ 4 Lieferung und Versandkosten">
                <p>
                  Lieferungen erfolgen innerhalb der Schweiz sowie in ausgewählte EU-Länder. Die
                  Lieferzeiten betragen üblicherweise 5–10 Werktage für Lagerware. Für
                  kundenspezifisch angefertigte Produkte gelten die in der Auftragsbestätigung
                  angegebenen Lieferzeiten.
                </p>
                <p className="mt-3">
                  Die Versandkosten werden im Checkout-Prozess angezeigt. Alle Lieferungen
                  erfolgen per Post oder Kurierdienst. Nach Versand erhalten Sie eine
                  Versandbestätigung mit Tracking-Nummer.
                </p>
              </Section>

              <Section title="§ 5 Widerrufsrecht">
                <p>
                  Sie haben das Recht, diesen Vertrag binnen 14 Tagen ohne Angabe von Gründen zu
                  widerrufen.
                </p>
                <p className="mt-3">
                  Die Widerrufsfrist beträgt 14 Tage ab dem Tag, an dem Sie oder ein von Ihnen
                  benannter Dritter, der nicht der Beförderer ist, die letzte Ware in Besitz
                  genommen haben bzw. hat.
                </p>
                <p className="mt-3">
                  Um das Widerrufsrecht auszuüben, müssen Sie uns (Inexxio AG, E-Mail:
                  info@inexxio.com) mittels einer eindeutigen Erklärung (z.B. ein mit der Post
                  versandter Brief, Telefax oder E-Mail) über Ihren Entschluss, diesen Vertrag zu
                  widerrufen, informieren. Sie können dafür das beigefügte Muster-Widerrufsformular
                  verwenden, das jedoch nicht vorgeschrieben ist.
                </p>
                <p className="mt-3">
                  Das Widerrufsrecht gilt nicht für:
                </p>
                <ul className="mt-2 ml-4 list-disc space-y-1">
                  <li>Kundenspezifisch angefertigte oder personalisierte Produkte</li>
                  <li>Versiegelte Waren, die aus gesundheitlichen oder hygienischen Gründen
                    nicht zur Rückgabe geeignet sind, wenn die Versiegelung nach der Lieferung
                    entfernt wurde</li>
                </ul>
                <p className="mt-3 font-medium">Folgen des Widerrufs:</p>
                <p className="mt-2">
                  Wenn Sie diesen Vertrag widerrufen, erstatten wir Ihnen alle Zahlungen, die
                  wir von Ihnen erhalten haben, einschliesslich der Lieferkosten (mit Ausnahme
                  der zusätzlichen Kosten, die sich daraus ergeben, dass Sie eine andere Art der
                  Lieferung als die von uns angebotene, günstigste Standardlieferung gewählt
                  haben), unverzüglich und spätestens binnen 14 Tagen ab dem Tag zurückzuzahlen,
                  an dem die Mitteilung über Ihren Widerruf dieses Vertrags bei uns eingegangen
                  ist.
                </p>
                <p className="mt-3">
                  Sie tragen die unmittelbaren Kosten der Rücksendung der Waren. Sie müssen für
                  einen etwaigen Wertverlust der Waren nur aufkommen, wenn dieser Wertverlust auf
                  einen zur Prüfung der Beschaffenheit, Eigenschaften und Funktionsweise der
                  Waren nicht notwendigen Umgang mit Ihnen zurückzuführen ist.
                </p>
              </Section>

              <Section title="§ 6 Eigentumsvorbehalt">
                <p>
                  Die Ware bleibt bis zur vollständigen Bezahlung Eigentum von Inexxio.
                </p>
              </Section>

              <Section title="§ 7 Gewährleistung">
                <p>
                  Es gilt das Schweizer Gewährleistungsrecht gemäss OR Art. 197 ff. Sachmängel
                  sind unverzüglich nach Entdeckung zu melden. Die Gewährleistungsfrist beträgt
                  2 Jahre ab Lieferung.
                </p>
                <p className="mt-3">
                  Bei Mängeln haben Sie das Recht auf Nachbesserung oder Ersatzlieferung.
                  Schlägt die Nacherfüllung fehl, können Sie Preisminderung verlangen oder –
                  bei erheblichen Mängeln – vom Vertrag zurücktreten.
                </p>
              </Section>

              <Section title="§ 8 Datenschutz">
                <p>
                  Die Verarbeitung Ihrer personenbezogenen Daten erfolgt gemäss unserer{' '}
                  <a href="/datenschutz" className="text-blue-600 hover:underline">
                    Datenschutzerklärung
                  </a>
                  , die Sie unter www.inexxio.com/datenschutz einsehen können.
                </p>
              </Section>

              <Section title="§ 9 Anwendbares Recht und Streitigkeiten">
                <p>
                  Es gilt Schweizer Recht. Bei Streitigkeiten können Sie die Ombudsstelle für
                  Konsumentenrechte oder ein staatliches Schlichtungsverfahren in Anspruch nehmen.
                </p>
                <p className="mt-3">
                  Gerichtsstand ist, soweit gesetzlich zulässig, der Sitz von Inexxio.
                </p>
              </Section>

              <Section title="§ 10 Schlussbestimmungen" isLast>
                <p>
                  Sollten einzelne Bestimmungen dieser AGB unwirksam sein, berührt dies die
                  Wirksamkeit der übrigen Bestimmungen nicht. Es gilt Schweizer Recht.
                </p>
                <p className="mt-4 text-sm text-slate-500">
                  Version {VERSION} | Gültig ab {VALID_FROM} | Inexxio AG
                </p>
              </Section>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function Section({
  title,
  children,
  isLast = false,
}: {
  title: string;
  children: React.ReactNode;
  isLast?: boolean;
}) {
  return (
    <div className={`${isLast ? '' : 'mb-8 pb-8 border-b border-slate-100'}`}>
      <h2 className="mb-3 text-lg font-bold text-slate-900">{title}</h2>
      <div className="text-sm text-slate-700 leading-relaxed space-y-0">{children}</div>
    </div>
  );
}
