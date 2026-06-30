# Backend – FastAPI (Python 3.12)

## Technologie
Python 3.12, FastAPI 0.109, SQLAlchemy 2.0, Pydantic v2, Alembic, PostgreSQL 15

## Pflichtregeln – vor jeder Änderung

Vor der ersten Änderung in einer Sitzung:
```bash
git fetch origin develop && git pull origin develop
git log --oneline -5 && git status
```
Dann: Betroffene Datei mit Read-Tool frisch laden – niemals Kontext-Zusammenfassungen als Dateiinhalt behandeln.

## Starten
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Alembic
```bash
alembic upgrade head          # Migrationen anwenden
alembic revision --autogenerate -m "description"  # Neue Migration erstellen
```

## Struktur
```
app/
├── main.py           ← FastAPI App, Router-Registrierung, CORS
├── core/
│   ├── config.py     ← Pydantic Settings (env vars)
│   ├── database.py   ← SQLAlchemy Engine + Session
│   └── auth.py       ← Firebase JWT-Verifikation, require_admin/require_staff
├── models/           ← SQLAlchemy 2.0 Modelle (je ein File pro Entität)
│   ├── user.py       ← UserProfile
│   ├── audit.py      ← AuditLog
│   ├── notification.py ← Notification
│   ├── admin.py      ← CompanySettings
│   └── __init__.py   ← Re-Export aller Modelle (immer von hier importieren)
├── schemas/          ← Pydantic v2 Request/Response Schemas
├── routers/          ← FastAPI Router (je ein File pro Ressource)
├── services/         ← Business Logic (DB-unabhängig testbar)
└── scripts/
    └── dump_openapi.py ← OpenAPI-Schema → backend/openapi.json (SSOT für FE-Typen)
```

## OpenAPI → Frontend-Typen (Single Source of Truth)
Die TypeScript-Typen des Frontends werden aus den Pydantic-Schemas generiert.
Nach jeder Änderung an einem Request/Response-Schema:
```bash
cd backend && python -m scripts.dump_openapi     # → backend/openapi.json
cd ../frontend && npm run generate:types          # → src/types/api.ts
```

## API-Endpunkte (tatsächlich vorhanden, Phase 1)
| Method | Path | Auth | Beschreibung |
|--------|------|------|--------------|
| GET | /health | – | Health Check |
| GET | /api/v1/auth/me | user | Eigenes Profil |
| PATCH | /api/v1/auth/me | user | Eigenes Profil bearbeiten (Self-Service) |
| POST | /api/v1/auth/terms-accept | user | AGB akzeptieren |
| GET | /api/v1/erp/records | staff | Benutzer-Feed (Master-Detail) |
| GET/PATCH | /api/v1/erp/records/{object_id} | staff/admin | Datensatz lesen/ändern |
| GET/POST | /api/v1/erp/articles | staff | Artikel-Feed / Artikel anlegen (Status 'draft') |
| GET/PATCH | /api/v1/erp/articles/{object_id} | staff | Artikel lesen/ändern |
| GET/POST | /api/v1/erp/articles/{object_id}/process-steps | staff | Prozessschritte (Purchase) lesen/anlegen |
| PATCH/DELETE | /api/v1/erp/articles/{object_id}/process-steps/{step_id} | staff | Prozessschritt ändern/entfernen |
| GET | /api/v1/erp/orders | user | Auftrag-Feed (Lieferant: nur eigene, mit eingebettetem Prozess) |
| POST | /api/v1/erp/orders | staff | Auftrag anlegen |
| GET | /api/v1/erp/orders/{object_id} | user | Auftrag lesen (inkl. Beschaffungs-Embed) |
| PATCH | /api/v1/erp/orders/{object_id} | staff | Auftrag ändern (Freigabe stösst Prozess an) |
| PATCH | /api/v1/erp/orders/{object_id}/purchase | user | Beschaffungsschritt (Offerte/Status, rollenabhängig) |
| GET/PATCH | /api/v1/erp/articles/{object_id}/sales | staff | Verkaufs-Profil (publiziert/Sichtbarkeit/Inhalt) – immer editierbar |
| GET/POST | /api/v1/erp/articles/{object_id}/sales/prices | staff | Verkaufspreise (1:n) lesen/anlegen |
| PATCH/DELETE | /api/v1/erp/articles/{object_id}/sales/prices/{price_id} | staff | Preis ändern/entfernen |
| GET/POST | /api/v1/erp/articles/{object_id}/sales/audience | staff | Zielgruppe (private/unlisted) lesen/zuweisen |
| DELETE | /api/v1/erp/articles/{object_id}/sales/audience/{row_id} | staff | Kunden-Zuweisung entfernen |
| GET | /api/v1/shop/config | – | Shop-Währungen + Default + Provider + **Publishable Key** (eingebettete Kasse) |
| GET | /api/v1/shop/products | optional | Publizierte Produkte (public + private des Kunden), inkl. Preis-Optionen |
| GET | /api/v1/shop/products/{object_id} | optional | Produktdetail (kanonisch über replaced_by_id) inkl. `prices[]` |
| POST | /api/v1/shop/checkout | user | **Warenkorb** (`items[]`) → CheckoutIntent → Stripe-Embedded (`client_secret`) / manual; Auftrag entsteht aufgeschoben bei Zahlung |
| GET | /api/v1/shop/session/{session_id} | user | Intent-/Zahlungsstatus (Erfolgsseite nach eingebetteter Kasse) |
| POST | /api/v1/shop/portal | user | Stripe Customer Portal (Abo/Zahlungsmittel verwalten) → URL |
| POST | /api/v1/shop/payments/webhook | – | Stripe-Webhook (signaturgeprüft): Zahlung/Abo spiegeln |
| GET | /api/v1/shop/payment/{token} | user | Zahlungsstatus (manueller Fallback-Provider) |
| POST | /api/v1/shop/payments/simulate | user | Manueller Provider: Zahlung simulieren (nur ohne Stripe) |
| GET/PATCH | /api/v1/admin/settings | admin | Firmeneinstellungen (inkl. Shop-Währungen/Provider) |
| GET | /api/v1/admin/settings/public | – | Öffentliche Firma-Infos |
| GET | /api/v1/admin/users | staff | Benutzerliste |
| PATCH | /api/v1/admin/users/{id}/role | admin | Rolle ändern |
| DELETE | /api/v1/admin/users/{id} | admin | Benutzer deaktivieren |
| GET | /api/v1/admin/audit-log | admin | Audit Log |
| GET | /api/v1/admin/notifications | user | Eigene Benachrichtigungen |
| POST | /api/v1/contact | – | Kontaktformular |

> Artikel: **Stammdaten** + **Prozess** (Purchase-Schritt) implementiert; Reiter **Bestand** ist
> noch Platzhalter. Prozessschritt-Modul «Purchase»: Auftrag (Artikel+Menge) → Freigabe instanziiert
> die Bestellung. Diese läuft **unter der Auftragsnummer** (Tabelle `purchase_orders` OHNE eigene
> Objektnummer, eingebettet als `purchase` in der OrderResponse). Status requested→quoted→
> approved/rejected→confirmed→received; Einstandspreis netto/Stück wird auf den Artikel zurück-
> geschrieben; der Auftrag wird automatisch `completed`, wenn alle Schritte erledigt sind
> (`services/purchase.py`, `services/orders.py`). E-Mail-Versand ist nur als TODO vermerkt.
> Seriennummern/Eingangskontrolle, BOM/Arbeitspläne, Stripe sind Phase 2+ und **noch nicht** implementiert.
>
> Objektnummern (9-stellig) werden objekttyp-übergreifend in `app/services/objects.py`
> vergeben (Maximum über alle Objekttabellen + 1).

## Konventionen
- Soft-Delete überall: is_active=false, KEIN hard delete
- UTC Timestamps überall
- Pydantic v2: `model_validate()`, `model_dump()`, `ConfigDict(from_attributes=True)`
- SQLAlchemy 2.0: `Mapped[T]`, `mapped_column()`
- Fehler: `raise HTTPException(status_code=..., detail="...")`
- Audit-Log bei jedem Update schreiben

## Env-Variablen
Siehe /.env.example für vollständige Liste.
Pflicht lokal: DATABASE_URL, FIREBASE_PROJECT_ID
