/** @type {import('tailwindcss').Config} */

// ── Inexxio Design System → Tailwind ─────────────────────────────────────────
// Every value below is a reference to a CSS custom property defined in the single
// source of truth: src/styles/design-system/colors_and_type.css (vendored from
// Claude Design). Tailwind utilities (bg-bg-2, text-fg-3, text-accent,
// border-border-1, rounded-ds-lg, shadow-ds-md, font-display …) therefore always
// resolve to the canonical token — change a value there, not here.
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
        // Brand — the single loud accent. Use sparingly (CTAs, one headline word,
        // active nav underline). `inexxio` and `red` map to the same brand red.
        inexxio: {
          DEFAULT: 'var(--inexxio-red)',
          red: 'var(--inexxio-red)',
          bright: 'var(--inexxio-red-bright)',
          deep: 'var(--inexxio-red-deep)',
          black: 'var(--inexxio-black)',
        },
        // Cool slate accent — the quiet third voice for ERP info / active states
        // / links, where brand red would be too loud or read as an alert.
        accent: {
          DEFAULT: 'var(--accent)',
          soft: 'var(--accent-soft)',
          ink: 'var(--accent-ink)',
        },
        // Ink / foreground (warm-neutral)
        fg: {
          1: 'var(--fg-1)',
          2: 'var(--fg-2)',
          3: 'var(--fg-3)',
          4: 'var(--fg-4)',
          'on-red': 'var(--fg-on-red)',
          'on-dark': 'var(--fg-on-dark)',
        },
        // Surfaces / backgrounds (warm Scandinavian neutrals)
        bg: {
          1: 'var(--bg-1)',
          2: 'var(--bg-2)',
          3: 'var(--bg-3)',
          4: 'var(--bg-4)',
          dark: 'var(--bg-dark)',
          'dark-2': 'var(--bg-dark-2)',
        },
        // Warm neutral scale (oak / stone / sand) pulled from the interior renders
        sand: {
          50: 'var(--sand-50)',
          100: 'var(--sand-100)',
          200: 'var(--sand-200)',
          300: 'var(--sand-300)',
          400: 'var(--sand-400)',
        },
        oak: 'var(--oak)',
        stone: 'var(--stone)',
        // Semantic — pair each with its soft `-bg` tint for chips/rows
        success: { DEFAULT: 'var(--success)', bg: 'var(--success-bg)' },
        warning: { DEFAULT: 'var(--warning)', bg: 'var(--warning-bg)' },
        info: { DEFAULT: 'var(--info)', bg: 'var(--info-bg)' },
        danger: { DEFAULT: 'var(--danger)', bg: 'var(--danger-bg)' },
        // Hairline borders
        border: {
          1: 'var(--border-1)',
          2: 'var(--border-2)',
          strong: 'var(--border-strong)',
        },
        // DEPRECATED — legacy blue brand. Do not use in new UI: brand = inexxio
        // (red), informational/active = accent (slate). Kept only so existing
        // `brand-*` usages keep compiling during the incremental migration.
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
      },
      borderRadius: {
        // DS radii — namespaced `ds-*` so Tailwind's own rounded-{sm,md,lg,…}
        // (used across the existing app) keep their meaning.
        'ds-xs': 'var(--r-xs)',
        'ds-sm': 'var(--r-sm)',
        'ds-md': 'var(--r-md)',
        'ds-lg': 'var(--r-lg)',
        'ds-xl': 'var(--r-xl)',
        'ds-pill': 'var(--r-pill)',
      },
      boxShadow: {
        // DS shadows — soft, warm, low-contrast. `shadow-ds-red` / `shadow-glow-*`
        // are hover/press accents only, never a resting glow.
        'ds-xs': 'var(--shadow-xs)',
        'ds-sm': 'var(--shadow-sm)',
        'ds-md': 'var(--shadow-md)',
        'ds-lg': 'var(--shadow-lg)',
        'ds-xl': 'var(--shadow-xl)',
        'ds-red': 'var(--shadow-red)',
        'glow-sm': 'var(--glow-sm)',
        'glow-md': 'var(--glow-md)',
        'glow-lg': 'var(--glow-lg)',
      },
      letterSpacing: {
        tightest: 'var(--tracking-tight)',
        snug: 'var(--tracking-snug)',
        overline: 'var(--tracking-overline)',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideInRight: {
          from: { transform: 'translateX(100%)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
