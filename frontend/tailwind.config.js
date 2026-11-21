/** @type {import('tailwindcss').Config} */

// ── Inexxio Design System → Tailwind ─────────────────────────────────────────
// Jeder Wert hier ist ein Verweis auf eine Variable der einen Quelle,
// src/styles/design-system/colors_and_type.css. Die Utilities (bg-bg-2, text-fg-3,
// text-accent, border-border-1, rounded-ds-lg, shadow-ds-md, font-display …) lösen damit
// immer auf das Token auf – ein Wert wird dort geändert, nicht hier. Was keine Klasse
// liest, steht nicht hier.
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      fontFamily: {
        // Body/UI = Inter · Display headlines = Inter Tight · index/kicker = mono
        sans: ['Inter', 'system-ui', 'sans-serif'],
        body: ['var(--font-body)'],
        display: ['var(--font-display)'],
        mono: ['var(--font-mono)'],
      },
      colors: {
        // Rot – der eine laute Akzent: Anfrage, aktiver Zustand, echte Fehler; nie in einer
        // Überschrift.
        inexxio: {
          DEFAULT: 'var(--inexxio-red)',
          red: 'var(--inexxio-red)',
          bright: 'var(--inexxio-red-bright)',
          deep: 'var(--inexxio-red-deep)',
          black: 'var(--inexxio-black)',
        },
        // Slate – die leise Stimme: Info, aktiver Zustand, Links im ERP, wo Rot zu laut wäre.
        accent: {
          DEFAULT: 'var(--accent)',
          soft: 'var(--accent-soft)',
          ink: 'var(--accent-ink)',
        },
        // Schrift (kühles Grau, v4)
        fg: {
          1: 'var(--fg-1)',
          2: 'var(--fg-2)',
          3: 'var(--fg-3)',
          4: 'var(--fg-4)',
          'on-red': 'var(--fg-on-red)',
          'on-dark': 'var(--fg-on-dark)',
        },
        // Flächen (kühles Grau, v4)
        bg: {
          1: 'var(--bg-1)',
          2: 'var(--bg-2)',
          3: 'var(--bg-3)',
          4: 'var(--bg-4)',
          dark: 'var(--bg-dark)',
          'dark-2': 'var(--bg-dark-2)',
        },
        // Bedeutung – je mit ihrer getönten Fläche `-bg`
        success: { DEFAULT: 'var(--success)', bg: 'var(--success-bg)' },
        warning: { DEFAULT: 'var(--warning)', bg: 'var(--warning-bg)' },
        danger: { DEFAULT: 'var(--danger)', bg: 'var(--danger-bg)' },
        // Haarlinien
        border: {
          1: 'var(--border-1)',
          2: 'var(--border-2)',
          strong: 'var(--border-strong)',
        },
      },
      // Die Rahmenfarbe eines blossen `border` (Preflight) ist die Haarlinie des Hauses –
      // ohne diese Zeile wäre es Tailwinds gray-200, also die Alt-Palette durch die Hintertür.
      borderColor: {
        DEFAULT: 'var(--border-1)',
      },
      borderRadius: {
        // Radien unter `ds-*`, damit Tailwinds eigene rounded-{sm,md,lg,…} ihre Bedeutung
        // behalten: Bedienelement 8 px (md), Karte 12 px (lg).
        'ds-xs': 'var(--r-xs)',
        'ds-sm': 'var(--r-sm)',
        'ds-md': 'var(--r-md)',
        'ds-lg': 'var(--r-lg)',
      },
      boxShadow: {
        // Schatten nur für schwebende Ebenen; `shadow-ds-red` nur als Hover-Akzent des roten
        // Knopfs, nie im Ruhezustand.
        'ds-xs': 'var(--shadow-xs)',
        'ds-sm': 'var(--shadow-sm)',
        'ds-md': 'var(--shadow-md)',
        'ds-lg': 'var(--shadow-lg)',
        'ds-red': 'var(--shadow-red)',
      },
      letterSpacing: {
        overline: 'var(--tracking-overline)',
      },
    },
  },
  plugins: [],
};
