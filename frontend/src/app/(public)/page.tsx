import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Inexxio AG – Präzisionsfertigung Swiss Made',
  description:
    'Inexxio AG entwickelt und fertigt hochpräzise Maschinenkomponenten und Baugruppen. Toleranzen bis 0,001 mm. ISO 9001. Made in Switzerland.',
};

const features = [
  {
    idx: '01',
    title: 'Präzisionsfertigung',
    description:
      'CNC-Bearbeitung mit Toleranzen bis 0,001 mm. Modernste Mehrachsbearbeitungszentren für höchste Anforderungen in der Luft- und Raumfahrt, Medizintechnik und im Maschinenbau.',
    highlights: ['5-Achs CNC-Fräsen', 'Toleranzen bis 0,001 mm', 'Qualitätsprüfung CMM'],
  },
  {
    idx: '02',
    title: 'Entwicklung & Konstruktion',
    description:
      'Von der Idee bis zum Serienteil begleiten wir Sie durch den gesamten Entwicklungsprozess. Konstruktion, Prototypenbau und Serienproduktion aus einer Hand.',
    highlights: ['CAD/CAM Konstruktion', 'Rapid Prototyping', 'Serienreife Optimierung'],
  },
  {
    idx: '03',
    title: 'Komplettlösungen',
    description:
      'Ob Einzelteile, Baugruppen oder komplette Systemlösungen – wir decken die gesamte Wertschöpfungskette ab und koordinieren alle Lieferanten für Sie.',
    highlights: ['Einzelteile & Serien', 'Baugruppen-Montage', 'Just-in-Time Lieferung'],
  },
];

const stats = [
  { n: '1\'000+', l: 'Aktive Artikel im ERP' },
  { n: '0,001', l: 'mm Toleranz' },
  { n: '24h', l: 'Angebotszeit' },
];

export default function HomePage() {
  return (
    <>
      {/* ── Hero ─────────────────────────────────────────── */}
      <section
        style={{
          background: 'var(--bg-dark)',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          overflow: 'hidden',
        }}
      >
        <div className="ix-wrap">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              minHeight: '80vh',
              gap: 0,
            }}
            className="hero-grid"
          >
            {/* Left copy */}
            <div
              style={{
                padding: '80px 56px 80px 0',
                display: 'flex',
                flexDirection: 'column',
                borderRight: '1px solid rgba(255,255,255,0.08)',
              }}
              className="hero-copy"
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 14,
                  paddingBottom: 22,
                  marginBottom: 38,
                  borderBottom: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                <span
                  style={{
                    font: '600 11px var(--font-body)',
                    letterSpacing: '0.18em',
                    textTransform: 'uppercase',
                    color: 'var(--ix-red-bright)',
                  }}
                >
                  Swiss Made
                </span>
                <span style={{ color: 'rgba(255,255,255,0.2)', fontSize: 12 }}>·</span>
                <span
                  style={{
                    font: '600 11px var(--font-body)',
                    letterSpacing: '0.18em',
                    textTransform: 'uppercase',
                    color: 'rgba(255,255,255,0.45)',
                  }}
                >
                  ISO 9001
                </span>
                <span style={{ color: 'rgba(255,255,255,0.2)', fontSize: 12 }}>·</span>
                <span
                  style={{
                    font: '600 11px var(--font-body)',
                    letterSpacing: '0.18em',
                    textTransform: 'uppercase',
                    color: 'rgba(255,255,255,0.45)',
                  }}
                >
                  Maschinenbau
                </span>
              </div>

              <h1
                style={{
                  font: '800 clamp(40px,5.4vw,76px)/0.98 var(--font-display)',
                  letterSpacing: '-0.04em',
                  color: '#fff',
                  margin: 0,
                }}
              >
                Präzision für
                <br />
                <span style={{ color: 'var(--ix-red)' }}>anspruchsvolle</span>
                <br />
                Industrie
              </h1>

              <p
                style={{
                  font: 'var(--body-lg)',
                  color: 'rgba(255,255,255,0.65)',
                  margin: '30px 0 0',
                  maxWidth: 480,
                }}
              >
                Inexxio AG entwickelt und fertigt hochpräzise Maschinenkomponenten und
                Baugruppen für die Industrie. Von der Konstruktion bis zur Auslieferung –
                alles aus einer Hand.
              </p>

              <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 38 }}>
                <Link href="/kontakt" className="ix-btn ix-btn-primary ix-btn-lg">
                  Kontakt aufnehmen
                  <ArrowRight style={{ width: 18, height: 18 }} />
                </Link>
                <Link href="/ueber-uns" className="ix-btn ix-btn-ghost-light">
                  Über uns
                </Link>
              </div>

              {/* Stats */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3,1fr)',
                  marginTop: 'auto',
                  paddingTop: 46,
                  borderTop: '1px solid rgba(255,255,255,0.08)',
                  gap: 0,
                }}
                className="hero-stats"
              >
                {stats.map((s) => (
                  <div key={s.l} style={{ paddingRight: 18 }}>
                    <div
                      style={{
                        font: '800 32px/1 var(--font-display)',
                        letterSpacing: '-0.03em',
                        color: 'var(--ix-red)',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {s.n}
                    </div>
                    <div
                      style={{
                        font: 'var(--caption)',
                        color: 'rgba(255,255,255,0.45)',
                        marginTop: 7,
                      }}
                    >
                      {s.l}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: visual panel */}
            <div
              style={{
                position: 'relative',
                overflow: 'hidden',
                background: 'linear-gradient(135deg, rgba(229,26,20,0.06) 0%, rgba(0,0,0,0) 60%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '60px 0 60px 56px',
              }}
              className="hero-visual"
            >
              {/* Swiss-grid decorative */}
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  opacity: 0.04,
                  backgroundImage:
                    'linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)',
                  backgroundSize: '48px 48px',
                }}
              />
              <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
                {[
                  { label: 'Artikel', value: '1\'000+', sub: 'Aktive Teile im ERP' },
                  { label: 'Toleranz', value: '0,001 mm', sub: 'Höchste Präzision' },
                  { label: 'Zertifizierung', value: 'ISO 9001', sub: 'Qualitätsmanagement' },
                ].map((card) => (
                  <div
                    key={card.label}
                    style={{
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 'var(--r-lg)',
                      padding: '20px 24px',
                    }}
                  >
                    <div style={{ font: 'var(--caption)', color: 'rgba(255,255,255,0.4)', marginBottom: 6 }}>
                      {card.label}
                    </div>
                    <div
                      style={{
                        font: '700 28px/1 var(--font-display)',
                        letterSpacing: '-0.025em',
                        color: '#fff',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {card.value}
                    </div>
                    <div style={{ font: 'var(--body-sm)', color: 'rgba(255,255,255,0.45)', marginTop: 4 }}>
                      {card.sub}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────── */}
      <section className="ix-section">
        <div className="ix-wrap">
          <div className="ix-section-head">
            <div className="ix-section-head-meta">
              <span className="ix-section-idx">01</span>
              <span className="ix-eyebrow">Kompetenzen</span>
            </div>
            <div>
              <h2 className="ix-section-title">Unsere Kernkompetenzen</h2>
              <p className="ix-section-lead">
                Drei Säulen, die unsere Leistungsfähigkeit definieren und Ihnen maximale
                Sicherheit in der Lieferkette geben.
              </p>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3,1fr)',
              gap: 1,
              background: 'var(--border-1)',
              border: '1px solid var(--border-1)',
            }}
            className="features-grid"
          >
            {features.map((feature) => (
              <div
                key={feature.title}
                className="ix-card"
                style={{
                  borderRadius: 0,
                  border: 'none',
                  padding: 0,
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <div style={{ padding: '28px 30px 32px', display: 'flex', flexDirection: 'column', flex: 1 }}>
                  <div
                    style={{
                      font: 'var(--mono-sm)',
                      letterSpacing: '0.08em',
                      color: 'var(--ix-red)',
                      marginBottom: 16,
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {feature.idx}
                  </div>
                  <h3
                    style={{
                      font: 'var(--h3)',
                      letterSpacing: '-0.02em',
                      color: 'var(--fg-1)',
                      margin: '0 0 12px',
                    }}
                  >
                    {feature.title}
                  </h3>
                  <p style={{ font: 'var(--body-sm)', color: 'var(--fg-2)', margin: '0 0 20px', lineHeight: 1.65 }}>
                    {feature.description}
                  </p>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 'auto 0 0', display: 'flex', flexDirection: 'column' }}>
                    {feature.highlights.map((item) => (
                      <li
                        key={item}
                        style={{
                          display: 'flex',
                          gap: 12,
                          alignItems: 'center',
                          font: 'var(--body-sm)',
                          color: 'var(--fg-2)',
                          padding: '9px 0',
                          borderTop: '1px solid var(--border-1)',
                        }}
                      >
                        <CheckCircle2
                          style={{ width: 16, height: 16, color: 'var(--ix-red)', flexShrink: 0 }}
                        />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Why Inexxio ──────────────────────────────────── */}
      <section className="ix-section ix-section-alt">
        <div className="ix-wrap">
          <div className="ix-section-head">
            <div className="ix-section-head-meta">
              <span className="ix-section-idx">02</span>
              <span className="ix-eyebrow">Warum Inexxio</span>
            </div>
            <div>
              <h2 className="ix-section-title">Was uns von anderen unterscheidet</h2>
              <p className="ix-section-lead">
                Schweizer Präzision, modernste Fertigungsmethoden und ein kompromissloser
                Qualitätsanspruch – aus einer Hand.
              </p>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3,1fr)',
              gap: 1,
              background: 'var(--border-1)',
              border: '1px solid var(--border-1)',
            }}
            className="why-grid"
          >
            {[
              {
                label: 'ISO 9001',
                title: 'Qualitätsgarantie',
                text: 'Unser gesamter Fertigungsprozess ist nach ISO 9001 zertifiziert. Lückenlose Qualitätsdokumentation und 100%-Endkontrolle.',
              },
              {
                label: 'Flexibel',
                title: 'Losgrösse 1 bis Grossserie',
                text: 'Kurze Rüstzeiten und flexible Kapazitäten ermöglichen schnelle Reaktion auf Ihren Bedarf – vom Einzelteil bis zur Serie.',
              },
              {
                label: 'Swiss Made',
                title: 'Schweizer Qualitätsversprechen',
                text: 'Präzise, zuverlässig, termingerecht. Jahrzehntelange Erfahrung macht uns zum verlässlichen Partner für anspruchsvolle Projekte.',
              },
            ].map((card) => (
              <div
                key={card.title}
                style={{
                  background: '#fff',
                  padding: '36px 32px',
                  display: 'flex',
                  flexDirection: 'column',
                  minHeight: 240,
                  transition: 'all 0.3s',
                }}
                className="why-card"
              >
                <div
                  style={{
                    font: '800 28px/1 var(--font-display)',
                    letterSpacing: '-0.025em',
                    color: 'var(--ix-red)',
                    marginBottom: 12,
                  }}
                >
                  {card.label}
                </div>
                <h3
                  style={{
                    font: 'var(--h3)',
                    letterSpacing: '-0.02em',
                    color: 'var(--fg-1)',
                    margin: '0 0 12px',
                  }}
                >
                  {card.title}
                </h3>
                <p style={{ font: 'var(--body-sm)', color: 'var(--fg-2)', margin: 'auto 0 0', lineHeight: 1.65 }}>
                  {card.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Band ─────────────────────────────────────── */}
      <section style={{ padding: '0 0 104px' }}>
        <div className="ix-wrap">
          <div className="ix-cta-band">
            <div style={{ position: 'relative' }}>
              <h2
                style={{
                  font: 'var(--h2)',
                  letterSpacing: '-0.035em',
                  color: '#fff',
                  margin: 0,
                }}
              >
                Bereit für ein{' '}
                <span style={{ color: 'var(--ix-red)' }}>unverbindliches</span>{' '}
                Gespräch?
              </h2>
              <p
                style={{
                  font: 'var(--body-lg)',
                  color: 'rgba(255,255,255,0.65)',
                  margin: '14px 0 0',
                  maxWidth: 440,
                }}
              >
                Kontaktieren Sie uns für ein kostenloses Beratungsgespräch.
                Wir melden uns innert 24 Stunden bei Ihnen.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', position: 'relative' }}>
              <Link href="/kontakt" className="ix-btn ix-btn-primary ix-btn-lg">
                Jetzt anfragen
                <ArrowRight style={{ width: 18, height: 18 }} />
              </Link>
              <a
                href="mailto:info.inexxio@gmail.com"
                className="ix-btn ix-btn-ghost-light"
              >
                info.inexxio@gmail.com
              </a>
            </div>
          </div>
        </div>
      </section>

      <style>{`
        @media (max-width: 1000px) {
          .hero-grid { grid-template-columns: 1fr !important; }
          .hero-copy { padding: 60px 0 48px !important; border-right: none !important; }
          .hero-visual { display: none !important; }
          .hero-stats { padding-top: 32px !important; }
        }
        @media (max-width: 760px) {
          .features-grid { grid-template-columns: 1fr !important; }
          .why-grid { grid-template-columns: 1fr !important; }
        }
        .why-card:hover {
          transform: translateY(-4px);
          box-shadow: var(--glow-sm);
        }
      `}</style>
    </>
  );
}
