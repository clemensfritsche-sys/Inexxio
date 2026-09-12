// INEXXIO UI kit — Header + Hero (editorial)
function Header({ onScan }) {
  const [open, setOpen] = useState(false);
  const links = ['Raumlösungen', 'Inspiration', 'Services', 'Story', 'FAQ'];
  return (
    <header className="hdr">
      <div className="wrap hdr-in">
        <div className="hdr-left">
          <img className="hdr-logo" src={ASSET + 'logo.png'} alt="INEXXIO" />
          <nav className="nav">{links.map(l => <a key={l} href="#">{l}</a>)}</nav>
        </div>
        <div className="hdr-cta">
          <a href="#">Meine Projekte</a>
          <Button onClick={onScan} icon="scan-line">3D-Scan starten</Button>
          <button className="burger" onClick={() => setOpen(o => !o)} aria-label="Menu">
            <Icon name={open ? 'x' : 'menu'} size={26} />
          </button>
        </div>
      </div>
      <div className={`mobile-menu${open ? ' open' : ''}`}>
        {links.map(l => <a key={l} href="#" onClick={() => setOpen(false)}>{l}</a>)}
        <div style={{ marginTop: 18 }}><Button onClick={onScan} icon="scan-line">3D-Scan starten</Button></div>
      </div>
    </header>
  );
}

function Hero({ onScan }) {
  return (
    <section className="hero">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <div className="hero-kicker">
            <span className="idx">01 / Raumlösungen</span>
            <Eyebrow>Maximale Wohnqualität auf kleinem Raum</Eyebrow>
          </div>
          <h1 className="h-display">Klein wohnen.<br /><span className="mark">Gross</span> leben.</h1>
          <p className="sub">Ich will schöner wohnen – nicht grösser. Starte deinen 3D-Scan und entdecke ungeahntes Raumpotenzial in deinen eigenen vier Wänden.</p>
          <div className="hero-actions">
            <Button size="lg" onClick={onScan} icon="scan-line">Jetzt 3D-Scan starten</Button>
            <Button size="lg" variant="ghost" iconRight="arrow-right">Inspirieren lassen</Button>
          </div>
          <div className="hero-stats">
            <div><div className="n">48–72h</div><div className="l">bis zum 3D-Konzept</div></div>
            <div><div className="n">2 mm</div><div className="l">Scan-Präzision</div></div>
            <div><div className="n">+70 %</div><div className="l">mehr Stauraum</div></div>
          </div>
        </div>
        <div className="hero-visual">
          <img className="room" src={ASSET + 'room1.png'} alt="Inexxio Raumkonzept" />
          <div className="scan-pill"><span className="scan-dot"></span>LiDAR-Scan aktiv</div>
          <img className="phone-badge" src={ASSET + 'hero_scan.png'} alt="3D-Scan per Smartphone" />
          <div className="hero-cap">Studio · 24 m² · Zürich</div>
        </div>
      </div>
    </section>
  );
}

Object.assign(window, { Header, Hero });
