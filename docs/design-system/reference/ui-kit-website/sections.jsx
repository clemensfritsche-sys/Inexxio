// INEXXIO UI kit — Use-cases, Inspiration, Process (editorial)
const USE_CASES = [
  { no: '01', img: 'room5.png', t: 'Kleine Wohnungen maximieren', p: 'Jede kleine Wohnung wird zum vollwertigen Wohnraum ohne Kompromisse – jeder Quadratmillimeter intelligent genutzt.',
    c: ['Vollwertiger Wohnraum ohne Abstriche', 'Ausnutzung bis zum letzten Zentimeter', 'Maximaler Wohlfühlfaktor'] },
  { no: '02', img: 'room4.png', t: 'Multifunktionale Räume gestalten', p: 'Ein Raum, viele Möglichkeiten: Arbeiten, Leben, Schlafen – flexible Konzepte, die sich nahtlos anpassen.',
    c: ['Flexible Raumaufteilung', 'Kostensparend und effizient', 'Ideal für Familien & Homeoffice'] },
  { no: '03', img: 'room7.png', t: 'Ferienwohnungen aufwerten', p: 'Mehr Gäste, mehr Erlebnis: smarte Raumlösungen für maximalen Komfort in kompakten Ferienapartments.',
    c: ['Mehr Schlafplätze auf kleiner Fläche', 'Attraktivere Vermietung & Auslastung', 'Optimiert für Gruppen'] },
  { no: '04', img: 'room6.png', t: 'Loft-Wohnungen strukturieren', p: 'Struktur für schön, aber schwer möblierbare Loft-Räume – die Raumhöhe intelligent genutzt.',
    c: ['Struktur für offene, hohe Räume', 'Intelligente Höhennutzung', 'Mehr Wohnraum durch vertikale Lösungen'] },
];

function UseCases() {
  return (
    <section className="section" id="loesungen">
      <div className="wrap">
        <SectionHead index="02" eyebrow="Raumlösungen"
          title="Mehr als nur Möbel. Dein Raum, neu gedacht."
          sub="Smarte Konzepte, die Funktionalität und Design vereinen – für mehr Lebensqualität auf weniger Fläche." />
        <div className="uc-grid">
          {USE_CASES.map(u => (
            <article className="uc" key={u.t}>
              <div className="uc-fig">
                <img src={ASSET + u.img} alt={u.t} />
                <span className="uc-no">{u.no}</span>
              </div>
              <div className="uc-bd">
                <h3 className="h3">{u.t}</h3>
                <p>{u.p}</p>
                <ul className="checklist">{u.c.map(c => <Check key={c}>{c}</Check>)}</ul>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

const GALLERY = [
  ['room1.png', 'Studio · Hochbett'], ['room5.png', 'Kompaktküche'], ['room4.png', 'Wohnen + Arbeiten'],
  ['room7.png', 'Loft · vertikal'], ['room6.png', 'Multifunktion'], ['room3.png', 'Gästebereich'], ['room2.png', 'Stauraum'],
];

function Inspiration({ onOpen }) {
  return (
    <section className="section alt" id="inspiration">
      <div className="wrap">
        <SectionHead index="03" eyebrow="Inspiration"
          title="Aus Räumen werden Lösungen"
          sub="Entdecke die Möglichkeiten. Lass dich inspirieren. Verwandle deinen Raum." />
        <div className="masonry">
          {GALLERY.map(([g, cap], i) => (
            <figure key={i} onClick={() => onOpen(ASSET + g)}>
              <img src={ASSET + g} alt="Inexxio Raumkonzept" />
              <figcaption>{cap}</figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

const STEPS = [
  { n: '01', t: 'Raumdaten erfassen', p: 'Revolutionäre 3D-Scantechnologie verwandelt Ihren Raum in präzise digitale Daten. Mit LiDAR erfassen Sie jeden Winkel – selbst, wann es Ihnen passt.',
    m: [['zap', 'Komplett-Scan in 5–10 Minuten'], ['ruler', 'Präzision bis 2 mm'], ['smartphone', 'Einfach per Smartphone']] },
  { n: '02', t: 'Individuelles Designkonzept', p: 'Unser Designsystem erstellt in 48–72 Stunden ein massgeschneidertes 3D-Konzept. Sie sehen sofort, wie Ihr neuer Raum aussieht – fotorealistisch.',
    m: [['cpu', 'KI-gestützte Raumnutzung'], ['eye', 'Fotorealistische Visualisierung'], ['repeat', 'Anpassungen bis 100 % passt']] },
  { n: '03', t: 'Produktion & Lieferung', p: 'Lokale Partnerbetriebe fertigen jedes Element millimetergenau auf CNC-Maschinen. Vormontierte Systeme ermöglichen kinderleichten Aufbau – bis vor die Haustür.',
    m: [['factory', 'Präzisionsfertigung, lokal'], ['leaf', 'Umweltfreundliche Materialien'], ['truck', 'Lieferung & Montage']] },
];

function Process() {
  return (
    <section className="section" id="prozess">
      <div className="wrap">
        <SectionHead index="04" eyebrow="So funktioniert's"
          title="Dein Wohnraum, in drei Schritten"
          sub="Von der präzisen Erfassung bis zur perfekten Umsetzung – aus jedem Raum wird ein multifunktionales Meisterwerk." />
        <div className="steps">
          {STEPS.map(s => (
            <div className="step" key={s.n}>
              <div className="step-no">{s.n}</div>
              <div className="step-bd">
                <div><h3 className="h3">{s.t}</h3><p>{s.p}</p></div>
                <div className="step-meta">
                  {s.m.map(([ic, tx]) => <span key={tx}><Icon name={ic} size={17} />{tx}</span>)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

Object.assign(window, { UseCases, Inspiration, Process });
