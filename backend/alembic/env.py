from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Load alembic config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Dieselbe Adresse wie die App – aus den Settings (``DATABASE_URL``, Treiber festgelegt).
# ``%`` verdoppelt: die ini-Datei liest es sonst als Platzhalter (etwa in einem Passwort).
from app.core.config import get_settings  # noqa: E402

config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

# Import all models so Alembic can detect them for autogenerate
from app.core.database import Base  # noqa: E402 — must come after path setup
from app.models import (  # noqa: F401
    Article,
    AuditLog,
    Capture,
    CompanySettings,
    Instance,
    InstanceUnit,
    TimestampMixin,
    UserProfile,
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though
    an Engine is acceptable here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # **Eine Instanz migriert, die anderen warten** – startet ein Rollout mehrere
        # Instanzen zugleich, liefe ``upgrade head`` sonst parallel. Der Lock hängt an der
        # Verbindung und fällt mit ihr; die Wartenden finden danach nichts mehr zu tun.
        if connection.dialect.name == "postgresql":
            connection.exec_driver_sql("SELECT pg_advisory_lock(778899002)")
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
