"""**Eine fehlgeschlagene Migration bleibt nie unbemerkt** (``/health`` → ``schema``).

Scheitert ``alembic upgrade head`` beim Start, läuft der Dienst trotzdem weiter – so blieb auf
dev die Kette wochenlang bei ``156`` stehen. ``/health`` sagt darum, ob die Datenbank auf dem
Stand des Codes steht; der Deploy liest es und wird rot.
"""

from sqlalchemy import text

from app.routers import health


def test_head_is_the_highest_migration():
    from pathlib import Path
    names = [p.name.split("_")[0] for p in (Path(health.__file__).resolve().parents[2]
                                            / "alembic" / "versions").glob("[0-9]*.py")]
    assert health.migration_head() == max(names, key=int)


def test_the_schema_says_current_or_behind(db):
    real = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert health.schema_state(db) == {"schema": "current", "revision": real, "head": real}
    db.execute(text("UPDATE alembic_version SET version_num = '156'"))
    state = health.schema_state(db)
    assert state["schema"] == "behind" and state["revision"] == "156"


def _run_check(tmp_path, body: str):
    """``scripts/check-schema.sh`` mit nachgebildetem ``gcloud`` und ``curl``."""
    import os
    import subprocess
    from pathlib import Path
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    (bin_ / "gcloud").write_text('#!/bin/bash\n[ "$2" = "services" ] && echo https://svc.example\n'
                                 '[ "$1" = "logging" ] && echo "!!! Alembic migration failed"\nexit 0\n')
    (bin_ / "curl").write_text(f"#!/bin/bash\ncat <<'X'\n{body}\nX\n")
    (bin_ / "sleep").write_text("#!/bin/bash\nexit 0\n")
    for f in bin_.iterdir():
        f.chmod(0o755)
    script = Path(health.__file__).resolve().parents[3] / "scripts" / "check-schema.sh"
    return subprocess.run(["bash", str(script), "p", "s", "r"], capture_output=True, text=True,
                          env={**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}"})


def test_the_deploy_turns_red_when_the_schema_is_behind(tmp_path):
    ok = _run_check(tmp_path, '{"schema": "current", "revision": "160", "head": "160"}')
    assert ok.returncode == 0, ok.stdout + ok.stderr
    behind = _run_check(tmp_path, '{"schema": "behind", "revision": "156", "head": "160"}')
    assert behind.returncode == 1 and "156 statt 160" in behind.stdout
    assert "Alembic migration failed" in behind.stdout, "die Zeilen des Starts stehen im Log"
    unread = _run_check(tmp_path, "Forbidden")
    assert unread.returncode == 0 and "::warning::" in unread.stdout
