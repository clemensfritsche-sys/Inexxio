# Frontend – Next.js 14 (TypeScript)

## Technologie
Next.js 14, TypeScript, Tailwind CSS, App Router, next-intl, React Query, Zustand

## Starten
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # Production Build
```

## Struktur
```
src/app/
├── (public)/       ← Öffentliche Website (kein Auth)
│   ├── layout.tsx  ← Navbar + Footer
│   ├── page.tsx    ← Homepage
│   ├── ueber-uns/  ← Über uns
│   ├── kontakt/    ← Kontaktformular
│   ├── impressum/  ← Impressum (dynamisch aus API)
│   ├── agb/        ← AGB (B2B + B2C Tabs)
│   └── datenschutz/← Datenschutzerklärung
├── (auth)/
│   └── login/      ← Magic Link + Google Sign-In
└── (erp)/          ← Auth-geschützte ERP-Seiten
    ├── erp/        ← Universal Feed (Master-Detail)
    └── admin/
        ├── einstellungen/  ← Firmeneinstellungen
        └── benutzer/       ← Benutzerverwaltung
```

## Design System
- Tailwind CSS, 8px Grid
- Colors: slate-* (neutral), blue-600 (primary), green-600 (success), red-600 (error)
- Font: Inter (Google Fonts)
- Cards: rounded-xl border border-slate-200 shadow-sm
- Buttons: btn-primary (blue), btn-secondary (white/border)
- Max-Width: max-w-7xl mx-auto

## i18n
next-intl, Locales: de (primary), en
Übersetzungen: /messages/de.json, /messages/en.json

## Auth Guard
ERP-Seiten prüfen Firebase Auth. Nicht eingeloggt → Redirect zu /login.

## API-Integration
- Client: src/lib/api.ts (fetch wrapper mit Bearer Token)
- Firebase: src/lib/firebase.ts (Magic Link, Google Sign-In)
- React Query für Serverdaten-Caching

## Typen (Single Source of Truth)
- `src/types/api.ts` wird aus dem Backend-OpenAPI-Schema generiert – NICHT editieren.
- `src/types/index.ts` leitet `UserProfile` daraus ab (nur `role` wird auf die Union verengt).
- Neu generieren nach Backend-Schema-Änderung:
  ```bash
  cd backend && python -m scripts.dump_openapi   # → backend/openapi.json
  cd frontend && npm run generate:types          # → src/types/api.ts
  ```

## Wichtige Konventionen
- 'use client' nur wenn nötig (Interaktivität, Hooks)
- Server Components für statische Seiten
- react-hook-form + zod für alle Formulare
- Lucide React für alle Icons
- TypeScript strict: kein 'any'

## Rechtliche Seiten
- Impressum: Daten dynamisch von /api/v1/admin/settings/public
- AGB: Vollständiger Schweizer Rechtstext (B2B + B2C)
- Datenschutz: Vollständig DSGVO + CH DSG konform
