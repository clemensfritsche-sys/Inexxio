"""Restore items/boms/work_plans/prozess_schritte/auftraege/objekte tables

Revision ID: 011
Revises: 010
"""
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    # Drop the unified objekte table created by the overhaul (wrong schema)
    op.execute("DROP TABLE IF EXISTS objekte CASCADE")
    op.execute("DROP TABLE IF EXISTS auftraege CASCADE")
    op.execute("DROP TABLE IF EXISTS prozess_schritte CASCADE")

    op.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id BIGINT PRIMARY KEY REFERENCES objects(id) ON DELETE RESTRICT,
            name_id INTEGER REFERENCES item_names(id) ON DELETE RESTRICT,
            name VARCHAR(255) NOT NULL,
            unit VARCHAR(10) NOT NULL DEFAULT 'Stk',
            status VARCHAR(20) NOT NULL DEFAULT 'ENTWURF',
            batch_allowed BOOLEAN NOT NULL DEFAULT false,
            order_number VARCHAR(100),
            order_link VARCHAR(500),
            onshape_link VARCHAR(500),
            weight_g NUMERIC(12,4),
            dim_1_mm NUMERIC(12,4),
            dim_2_mm NUMERIC(12,4),
            dim_3_mm NUMERIC(12,4),
            surface_id INTEGER REFERENCES item_surfaces(id) ON DELETE SET NULL,
            purchase_price NUMERIC(15,4),
            purchase_currency VARCHAR(3) NOT NULL DEFAULT 'CHF',
            lead_time_days INTEGER,
            stock_total NUMERIC(15,3) NOT NULL DEFAULT 0,
            stock_reserved NUMERIC(15,3) NOT NULL DEFAULT 0,
            replaced_by_id BIGINT REFERENCES items(id),
            replaces_id BIGINT REFERENCES items(id),
            is_sales_product BOOLEAN NOT NULL DEFAULT false,
            sales_price NUMERIC(15,4),
            sales_currency VARCHAR(3) NOT NULL DEFAULT 'CHF',
            category_id INTEGER REFERENCES item_categories(id) ON DELETE SET NULL,
            vat_rate VARCHAR(5),
            shop_description_long TEXT,
            seo_title VARCHAR(200),
            seo_description TEXT,
            hs_code VARCHAR(20),
            submitted_at TIMESTAMPTZ,
            submitted_by BIGINT,
            approved_at TIMESTAMPTZ,
            approved_by BIGINT,
            serialization_type VARCHAR(20) NOT NULL DEFAULT 'none',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT true
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_items_name ON items(name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_items_status ON items(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS item_signatures (
            id SERIAL PRIMARY KEY,
            item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            signed_by BIGINT NOT NULL REFERENCES user_profiles(id) ON DELETE RESTRICT,
            signed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_item_signatures_item_id ON item_signatures(item_id)")

    # Keep boms/work_plans tables for legacy compatibility (objects.py queries work_plans)
    op.execute("""
        CREATE TABLE IF NOT EXISTS boms (
            id BIGINT PRIMARY KEY REFERENCES objects(id),
            parent_item_id BIGINT NOT NULL REFERENCES items(id),
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT true
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_boms_parent_item_id ON boms(parent_item_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS bom_lines (
            id BIGSERIAL PRIMARY KEY,
            bom_id BIGINT NOT NULL REFERENCES boms(id),
            component_item_id BIGINT NOT NULL REFERENCES items(id),
            quantity NUMERIC(15,4) NOT NULL,
            unit VARCHAR(50) NOT NULL DEFAULT 'Stk',
            position INTEGER NOT NULL DEFAULT 1,
            note TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_bom_lines_bom_id ON bom_lines(bom_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS work_plans (
            id BIGINT PRIMARY KEY REFERENCES objects(id),
            item_id BIGINT REFERENCES items(id),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT true
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_work_plans_item_id ON work_plans(item_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS work_plan_steps (
            id BIGSERIAL PRIMARY KEY,
            work_plan_id BIGINT NOT NULL REFERENCES work_plans(id),
            step_nr INTEGER NOT NULL,
            step_type VARCHAR(20) NOT NULL DEFAULT 'operation',
            name VARCHAR(255) NOT NULL,
            resource VARCHAR(255),
            setup_min NUMERIC(8,2),
            exec_min_per_unit NUMERIC(8,2),
            nominal_value NUMERIC(15,4),
            tolerance NUMERIC(15,4),
            unit VARCHAR(50),
            is_mandatory BOOLEAN NOT NULL DEFAULT true
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_work_plan_steps_work_plan_id ON work_plan_steps(work_plan_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS prozess_schritte (
            id SERIAL PRIMARY KEY,
            item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            beschreibung TEXT NOT NULL,
            ressourcen JSONB,
            daten_felder JSONB,
            ergebnis_optionen JSONB,
            aktion JSONB,
            onshape_link VARCHAR(500),
            dokument_link VARCHAR(500),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_prozess_schritte_item_id ON prozess_schritte(item_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS auftraege (
            id BIGINT PRIMARY KEY REFERENCES objects(id) ON DELETE RESTRICT,
            item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
            menge NUMERIC(15,4) NOT NULL DEFAULT 1,
            datum_faellig DATE,
            status VARCHAR(20) NOT NULL DEFAULT 'OFFEN',
            notiz TEXT,
            wiederkehrend BOOLEAN NOT NULL DEFAULT false,
            intervall_typ VARCHAR(20),
            intervall_wert VARCHAR(100),
            naechste_faelligkeit DATE,
            created_by BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_auftraege_item_id ON auftraege(item_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_auftraege_status ON auftraege(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS objekte (
            id BIGINT PRIMARY KEY REFERENCES objects(id) ON DELETE RESTRICT,
            item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
            auftrag_id BIGINT REFERENCES auftraege(id) ON DELETE SET NULL,
            typ VARCHAR(10) NOT NULL,
            batch_menge NUMERIC(15,4),
            batch_verbleibend NUMERIC(15,4),
            status VARCHAR(20) NOT NULL DEFAULT 'VERFUEGBAR',
            lagerort VARCHAR(200),
            gueltig_bis DATE,
            schritt_protokoll JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_objekte_item_id ON objekte(item_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_objekte_status ON objekte(status)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS objekte CASCADE")
    op.execute("DROP TABLE IF EXISTS auftraege CASCADE")
    op.execute("DROP TABLE IF EXISTS prozess_schritte CASCADE")
    op.execute("DROP TABLE IF EXISTS work_plan_steps CASCADE")
    op.execute("DROP TABLE IF EXISTS work_plans CASCADE")
    op.execute("DROP TABLE IF EXISTS bom_lines CASCADE")
    op.execute("DROP TABLE IF EXISTS boms CASCADE")
    op.execute("DROP TABLE IF EXISTS item_signatures CASCADE")
    op.execute("DROP TABLE IF EXISTS items CASCADE")
