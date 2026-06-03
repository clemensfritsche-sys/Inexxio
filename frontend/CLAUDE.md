# Inexxio Frontend – Next.js 14

## Stack
- Next.js 14, TypeScript (strict), App Router, Tailwind CSS
- Firebase Auth (Magic Link + Google SSO)
- SWR für Data Fetching, React Hook Form + Zod für Formulare
- Lucide React für Icons

## Struktur
```
app/
├── (public)/    Öffentliche Website (Impressum, AGB, Datenschutz, Kontakt, Startseite)
├── (app)/       ERP - Auth-geschützt (Dashboard, Artikel, Admin, ...)
└── (shop)/      Online Shop (Phase 2)
components/
├── layout/      PublicHeader, PublicFooter, ERPSidebar, ERPTopbar
├── ui/          Wiederverwendbare UI-Komponenten (ContactForm, ...)
└── erp/         ERP-spezifische Komponenten (ItemsView, ItemDetail, ...)
lib/
├── firebase.ts  Firebase Auth Initialisierung
├── api.ts       API Client mit Auth-Token
├── format.ts    Date/Currency/Number Formatierung (immer Intl.*)
└── cn.ts        Tailwind Merge Utility
types/index.ts   Shared TypeScript Interfaces
```

## Wichtige Regeln
- Timestamps: IMMER `formatDate/formatDateTime` aus `lib/format.ts` – NIEMALS manuell
- API Calls: IMMER über `api.*` aus `lib/api.ts` – NIEMALS direkt `fetch` ohne Auth
- Styling: Tailwind Classes, globale Utilities in `globals.css` (`.btn-primary`, `.input`, `.card`, `.badge-*`)
- Autosave: Debounced 3s, grüner Border-Flash bei Erfolg (`border-green-400 + shadow`)
- Kein `any` – TypeScript strict

## Farbsystem
- `brand-*`: Primärfarbe (Blau, brand-600 = Hauptfarbe)
- `success` / `warning` / `error`: Status-Farben
- Badges: `.badge-green` / `.badge-yellow` / `.badge-red` / `.badge-gray` / `.badge-blue`

## Lokaler Start
```bash
npm install
npm run dev    # http://localhost:3000
npm run type-check
```

## Status Phase 1
- [x] Next.js 14 Setup (App Router, TypeScript, Tailwind)
- [x] Firebase Auth Konfiguration
- [x] API Client mit Auth-Token
- [x] Öffentliche Website: Startseite, Impressum, AGB, Datenschutz, Kontakt
- [x] ERP Layout: Sidebar + Topbar
- [x] ERP: Artikel-Liste + Detail-Panel mit Autosave
- [ ] Firebase Auth Flow (Login-Seite mit Magic Link + Google)
- [ ] Auth Guard (Redirect zu Login wenn nicht eingeloggt)
- [ ] Admin-Seite (Firmeneinstellungen)
- [ ] Shop Grundgerüst (Phase 2)
