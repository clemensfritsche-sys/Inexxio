# ADR 001: Technology Stack

**Status:** Accepted  
**Date:** 2026-06-03  
**Deciders:** Inexxio AG

## Context

We need a full-stack architecture for the Inexxio Enterprise Central System covering website, ERP, shop, and quality management.

## Decision

### Frontend: Next.js 14 (App Router)
- SSR + SPA capabilities for SEO and performance
- TypeScript for type safety
- Tailwind CSS for rapid, consistent UI
- PWA support via next-pwa

### Backend: FastAPI (Python 3.12)
- High performance, async-capable
- Automatic OpenAPI documentation
- Pydantic v2 for validation
- SQLAlchemy 2.0 for ORM

### Database: PostgreSQL 15
- ACID compliance for financial data
- pgvector extension for Phase 4 semantic search
- Alembic for schema migrations
- Single instance, universal 9-digit ID sequence

### Authentication: Firebase Authentication
- Magic Link (passwordless) as primary method
- Google SSO for convenience
- TOTP/MFA for admin accounts
- JWT tokens with 24h lifetime

### Infrastructure: Google Cloud
- Cloud Run for containerized backend (auto-scaling)
- Firebase Hosting for Next.js frontend
- Cloud SQL (managed PostgreSQL)
- Cloud Storage for files/signatures
- Secret Manager for credentials

## Consequences

**Positive:**
- Zero cold-start issues (Cloud Run min-instances)
- GDPR-compliant infrastructure (EU region)
- Serverless scaling reduces operational overhead
- Firebase Auth is battle-tested

**Negative:**
- Google Cloud vendor lock-in
- Python backend slower than Go/Rust (acceptable for this scale)
- next-intl adds complexity for i18n

## Alternatives Considered

- **Supabase:** Considered but Firebase chosen for its mature MFA/Magic Link support
- **Django REST Framework:** FastAPI chosen for performance and async support
- **MySQL:** PostgreSQL chosen for pgvector and JSONB support
