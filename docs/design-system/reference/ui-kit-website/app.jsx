// INEXXIO UI kit — App shell, scan modal, lightbox, toast
function ScanModal({ onClose, onDone }) {
  const [step, setStep] = useState(0);
  const steps = ['Raum scannen', 'Daten verarbeiten', 'Konzept anfordern'];
  const next = () => { if (step < 2) setStep(step + 1); else { onDone(); onClose(); } };
  return (
    <div className="modal-ov" onClick={e => { if (e.target.className === 'modal-ov') onClose(); }}>
      <div className="modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <Eyebrow>Schritt {step + 1} / 3</Eyebrow>
        <h3 className="h3" style={{ marginTop: 6 }}>{steps[step]}</h3>
        <div className="modal-steps">
          {[0, 1, 2].map(i => <div key={i} className={`d${i <= step ? ' on' : ''}`}></div>)}
        </div>
        {step === 0 && (
          <>
            <div className="scanframe"><img src={ASSET + 'room5.png'} alt="" /><div className="scanline"></div></div>
            <p style={{ font: 'var(--body-sm)', color: 'var(--fg-2)', margin: '0 0 18px' }}>Richte dein Smartphone auf den Raum. LiDAR erfasst jede Ecke millimetergenau – in 5–10 Minuten.</p>
          </>
        )}
        {step === 1 && (
          <div style={{ padding: '28px 0', textAlign: 'center' }}>
            <div style={{ width: 64, height: 64, margin: '0 auto 16px', borderRadius: '50%', background: 'rgba(229,26,20,.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="cloud-upload" size={30} color="var(--inexxio-red)" />
            </div>
            <p style={{ font: 'var(--body)', color: 'var(--fg-2)', margin: 0 }}>Deine Raumdaten werden in die INEXXIO Cloud übertragen. Unser Designsystem analysiert jeden Quadratmillimeter.</p>
          </div>
        )}
        {step === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, margin: '6px 0 18px' }}>
            <input className="m-field" placeholder="Vorname" defaultValue="" />
            <input className="m-field" placeholder="E-Mail" defaultValue="" />
            <input className="m-field" placeholder="Wohnfläche, z. B. 38 m²" defaultValue="" />
          </div>
        )}
        <Button variant="primary" onClick={next} iconRight={step < 2 ? 'arrow-right' : 'check'}>
          {step === 0 ? 'Scan starten' : step === 1 ? 'Weiter' : 'Konzept anfordern'}
        </Button>
      </div>
    </div>
  );
}

function Lightbox({ src, onClose }) {
  return (
    <div className="modal-ov" onClick={onClose}>
      <img src={src} alt="" style={{ maxWidth: '88vw', maxHeight: '86vh', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-lg)' }} />
    </div>
  );
}

function App() {
  const [scan, setScan] = useState(false);
  const [light, setLight] = useState(null);
  const [toast, setToast] = useState(false);

  useEffect(() => {
    if (toast) { const t = setTimeout(() => setToast(false), 3800); return () => clearTimeout(t); }
  }, [toast]);

  return (
    <>
      <Header onScan={() => setScan(true)} />
      <Hero onScan={() => setScan(true)} />
      <UseCases />
      <Inspiration onOpen={setLight} />
      <Calculator />
      <Process />
      <Story />
      <Testimonial />
      <CTA onScan={() => setScan(true)} />
      <FAQ />
      <Footer />
      {scan && <ScanModal onClose={() => setScan(false)} onDone={() => setToast(true)} />}
      {light && <Lightbox src={light} onClose={() => setLight(null)} />}
      {toast && <div className="toast"><Icon name="check-circle" size={18} color="var(--inexxio-red-bright)" />Scan empfangen – dein Konzept ist in 48–72h bereit.</div>}
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
