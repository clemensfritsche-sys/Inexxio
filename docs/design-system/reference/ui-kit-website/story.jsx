// INEXXIO UI kit — Story, Testimonial, FAQ, CTA, Footer (editorial)
function Story() {
  const blocks = [
    { n: '01', t: 'Warum weniger oft mehr ist', p: 'Ein Wandel im Denken ist spürbar: weniger Besitz, mehr Freiheit. Microliving wird zum Lifestyle – nicht aus Not, sondern aus Überzeugung.' },
    { n: '02', t: 'Wohnraum wird knapp', p: 'In urbanen Zentren steigen die Mieten, die Wohnflächen schrumpfen. Entscheidend ist, wie wir Raum nutzen – flexibel, funktional und bewusst.' },
    { n: '03', t: 'Neue Lösungen braucht das Wohnen', p: 'Multifunktionale Einrichtung, modulare Systeme und smarte Planung sind der Schlüssel für urbane Wohnqualität von morgen.' },
  ];
  return (
    <section className="section alt" id="story">
      <div className="wrap">
        <SectionHead index="06" eyebrow="INEXXIO Story"
          title="Zukunft des Wohnens – weniger Raum, mehr Lebensqualität" />
        <div className="story-grid">
          <figure className="story-figure" style={{ margin: 0 }}>
            <img src={ASSET + 'city_bw.png'} alt="Urbane Verdichtung" />
            <figcaption>Urbane Verdichtung · der Druck auf den Quadratmeter</figcaption>
          </figure>
          <div className="story-blocks">
            {blocks.map(b => (
              <div className="b" key={b.t}>
                <h3 className="h3"><span className="idx">{b.n}</span>{b.t}</h3>
                <p>{b.p}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Testimonial() {
  const cards = [
    { tag: 'WE', cls: '', p: '„Werde einer unserer ersten Kunden und gestalte mit uns die Zukunft des Wohnens neu.”' },
    { tag: 'WANT', cls: 'red', p: '„Entdecke, was mit smartem Design alles möglich ist – und wie beeindruckend ‚KLEIN‘ sein kann.”' },
    { tag: 'YOU', cls: 'dark', p: '„Werde Teil des Pilotprojekts und zeig, dass urbane Lebensqualität nicht an Quadratmetern scheitert.”' },
  ];
  return (
    <section className="section" id="testimonial">
      <div className="wrap">
        <SectionHead index="07" eyebrow="Testimonial" title="We · Want · You"
          sub="Wir suchen Pionier:innen, die mit uns das Wohnen neu denken." />
        <div className="wwy">
          {cards.map(c => (
            <div className={`wwy-card ${c.cls}`} key={c.tag}>
              <div className="wwy-tag">{c.tag}</div>
              <p>{c.p}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

const FAQS = [
  { q: 'Was ist INEXXIO eigentlich genau?', a: 'INEXXIO ist ein Einrichtungskonzept für urbane Wohnungen. Wir entwickeln durchdachte, massgeschneiderte Wohnlösungen, die Design, Funktion und Stauraum optimal vereinen – für mehr Lebensqualität auf weniger Quadratmetern.' },
  { q: 'Für wen ist INEXXIO geeignet?', a: 'Für alle, die in kompakten Wohnungen leben – Singles, Paare oder Familien – und ihren Wohnraum optimieren möchten. Besonders geeignet für Menschen in Städten, wo Wohnfläche teuer und knapp ist.' },
  { q: 'Wie läuft der Prozess ab?', a: 'Du startest mit einem einfachen 3D-Scan deiner Wohnung per Smartphone. Darauf basierend erstellen wir ein durchdachtes Einrichtungskonzept mit passenden Produkten. Was du davon umsetzt, entscheidest du selbst.' },
  { q: 'Muss ich das komplette Konzept kaufen?', a: 'Nein. Du bekommst ein vollständiges Designkonzept und entscheidest flexibel, welche Möbel oder Elemente du umsetzen möchtest. Du kaufst nur das, was du wirklich brauchst.' },
  { q: 'Kann ich eigene Möbel behalten?', a: 'Ja, selbstverständlich. Wir berücksichtigen vorhandene Lieblingsstücke gerne in der Planung und integrieren sie ins Gesamtkonzept – sofern das räumlich und stilistisch sinnvoll ist.' },
  { q: 'Wie viel mehr Stauraum bekomme ich?', a: 'Je nach Wohnung schaffen wir mit multifunktionalen Möbeln und smarter Planung bis zu 70 % mehr Stauraum – ohne dass der Raum vollgestellt wirkt. Weniger Quadratmeter, mehr Lebensqualität.' },
];

function FAQ() {
  const [open, setOpen] = useState(0);
  return (
    <section className="section alt" id="faq">
      <div className="wrap">
        <SectionHead index="08" eyebrow="Häufige Fragen" title="Antworten auf die wichtigsten Fragen" />
        <div className="faq">
          {FAQS.map((f, i) => (
            <div className={`faq-item${open === i ? ' open' : ''}`} key={i}>
              <button className="faq-q" onClick={() => setOpen(open === i ? -1 : i)}>
                {f.q}<span className="faq-ico"><Icon name="plus" size={22} /></span>
              </button>
              <div className="faq-a" style={{ maxHeight: open === i ? 320 : 0 }}>
                <div className="faq-a-inner">{f.a}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CTA({ onScan }) {
  return (
    <section className="section">
      <div className="wrap">
        <div className="cta-band">
          <div>
            <h2 className="h-sec">Bereit für deine perfekte Raumlösung?</h2>
            <p>Weil urbane Lebensqualität nicht an Quadratmetern scheitern darf.</p>
          </div>
          <div className="cta-actions">
            <Button size="lg" onClick={onScan} icon="scan-line">Projekt starten</Button>
            <Button size="lg" variant="ghost-light" iconRight="arrow-right">Beratung vereinbaren</Button>
          </div>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  const cols = [
    { h: 'Lösungen', items: ['Meine Projekte', 'Inspiration', "Wie funktioniert's", 'Preise'] },
    { h: 'Services', items: ['Planungsservice', 'Lieferservice', 'Montageservice'] },
    { h: 'Unternehmen', items: ['INEXXIO Story', 'Das ist INEXXIO', 'Testimonial', 'Werde Teil von INEXXIO'] },
  ];
  return (
    <footer className="footer">
      <div className="wrap">
        <div className="footer-top">
          <div>
            <img className="footer-logo" src={ASSET + 'logo.png'} alt="INEXXIO" />
            <p className="footer-tag">Innovative Raumlösungen. Maximale Wohnqualität auf kleinem Raum.</p>
            <div className="footer-contact">
              <span><Icon name="phone" size={15} />+41 79 505 83 02</span>
              <span><Icon name="mail" size={15} />info.inexxio@gmail.com</span>
            </div>
          </div>
          {cols.map(c => (
            <div key={c.h}>
              <h5>{c.h}</h5>
              <ul>{c.items.map(it => <li key={it}><a href="#">{it}</a></li>)}</ul>
            </div>
          ))}
        </div>
        <div className="footer-bottom">
          <span>© 2024 INEXXIO AG · Maximale Wohnqualität auf kleinem Raum</span>
          <span style={{ display: 'flex', gap: 18 }}>
            <a href="#">Impressum</a><a href="#">Datenschutz</a><a href="#">AGB</a>
          </span>
        </div>
      </div>
    </footer>
  );
}

Object.assign(window, { Story, Testimonial, FAQ, CTA, Footer });
