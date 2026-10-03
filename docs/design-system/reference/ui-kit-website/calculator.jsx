// INEXXIO UI kit — "INEXXIO in Zahlen" savings calculator (dark, editorial)
function chf(n) { return n.toLocaleString('de-CH').replace(/[\u2019',.]/g, "\u2019"); }

function Calculator() {
  const [area, setArea] = useState(45);
  const lostM2 = Math.round(area * 0.14);
  const rentPerM2 = 34;
  const yearlyLoss = lostM2 * rentPerM2 * 12;
  const solution = Math.round((2500 + lostM2 * 620) / 100) * 100 - 1;
  const amort = Math.max(1, Math.round(solution / (yearlyLoss / 12)));

  return (
    <section className="dark-sec" id="zahlen">
      <div className="wrap">
        <SectionHead index="05" eyebrow="INEXXIO in Zahlen"
          title="Still und leise verlierst du Geld"
          sub="Der teuerste Quadratmeter der Welt? Nicht in New York, nicht in Paris – sondern in deiner eigenen Wohnung, dort wo du Fläche bezahlst, aber nie nutzt." />
        <div className="calc-grid">
          <div className="kpis">
            <div className="kpi hl"><div className="n">{lostM2} m²</div><div className="l">Verlorener Wohnraum, den du heute bezahlst</div></div>
            <div className="kpi"><div className="n">{chf(yearlyLoss)}</div><div className="l">Verlorener Wohnwert pro Jahr, in CHF</div></div>
            <div className="kpi"><div className="n">{chf(solution)}</div><div className="l">Einmalige INEXXIO Lösung, in CHF</div></div>
            <div className="kpi"><div className="n">{amort} Mt.</div><div className="l">bis zur vollen Amortisation</div></div>
          </div>
          <div className="calc-card">
            <h4>Wie gross ist deine Wohnung?</h4>
            <div className="calc-val">{area}<span> m²</span></div>
            <input type="range" min="15" max="90" value={area} onChange={e => setArea(+e.target.value)} />
            <div className="calc-row"><span>15 m²</span><span>90 m²</span></div>
            <div className="calc-result">
              <div>
                <div className="rl">Zurückgewonnener Wert / Jahr</div>
                <div className="save">{chf(yearlyLoss)} CHF</div>
              </div>
              <Button variant="primary" iconRight="arrow-right">Jetzt Geld sparen</Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

Object.assign(window, { Calculator });
