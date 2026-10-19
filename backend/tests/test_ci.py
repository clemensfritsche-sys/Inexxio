"""**Die CI prüft, was sie verspricht** – ein Wächter, der nur lokal läuft, ist keiner.

Die Prüfungen stehen EINMAL in ``.github/workflows/quality.yml``; Dev- und Prod-Deploy
rufen sie auf, bevor etwas ausgerollt wird. Hier steht, dass das so bleibt.
"""

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _steps(job: dict) -> list[dict]:
    return job.get("steps", [])


def _runs(job: dict) -> str:
    return "\n".join(s.get("run", "") for s in _steps(job))


def _step(job: dict, needle: str) -> tuple[int, dict]:
    hits = [(i, s) for i, s in enumerate(_steps(job)) if needle in s.get("run", "")]
    assert hits, f"Kein Schritt führt «{needle}» aus."
    return hits[0]


def test_both_deploys_run_the_one_quality_gate_first():
    """Bug-Formen: ein Deploy ohne Gate (Prod hatte keines); ein Deploy-Job, der nicht
    auf das Gate wartet; eine zweite, abweichende Kopie der Prüfungen."""
    for name, first in (("deploy-dev.yml", "deploy-backend"), ("deploy-prod.yml", "approve")):
        jobs = _load(name)["jobs"]
        assert jobs["quality"].get("uses") == "./.github/workflows/quality.yml", name
        needs = jobs[first].get("needs")
        assert "quality" in ([needs] if isinstance(needs, str) else needs or []), (
            f"{name}: «{first}» wartet nicht auf das Quality-Gate.")
        own = [j for j, d in jobs.items() if "pytest" in _runs(d)]
        assert not own, f"{name} trägt eigene Prüfungen neben dem Gate: {own}"


def test_the_backend_tests_run_against_a_required_database():
    """Schema aus den Migrationen, DANN pytest – mit Pflicht-Datenbank und sichtbaren Skips.

    Ohne Datenbank übersprangen sich ~300 Prüfungen lautlos, und der Job blieb grün.
    Bug-Formen: Schema nach den Tests; keine DATABASE_URL; kein ``INEXXIO_REQUIRE_DB``;
    kein ``-rs``; die Matrix-Dateien sind still verschwunden."""
    job = _load("quality.yml")["jobs"]["quality"]
    schema, _ = _step(job, "alembic upgrade head")
    tests, step = _step(job, "pytest")
    assert schema < tests, "Das Schema wird erst nach den Tests gebaut."
    env = step.get("env", {})
    assert "DATABASE_URL" in env, "Der Test-Schritt bekommt keine DATABASE_URL."
    assert str(env.get("INEXXIO_REQUIRE_DB")) == "1", "Die Datenbank ist nicht Pflicht."
    assert "-rs" in step["run"], "Skips laufen ohne Grund durch (-rs fehlt)."
    for name in ("matrix.py", "scenarios.py", "runner.py", "conftest.py",
                 "test_scenarios.py", "test_invariants.py", "test_flow_graph.py"):
        assert (ROOT / "backend" / "tests" / name).exists(), f"tests/{name} fehlt."


def test_the_gate_checks_frontend_lint_build_and_python():
    """Bug-Formen: Lint/Build/ruff fehlen im Gate; ``npm install`` statt ``npm ci``
    (nicht reproduzierbar); ruff mit mehr als den F-Regeln (Stil statt Fehler)."""
    runs = _runs(_load("quality.yml")["jobs"]["quality"])
    for cmd in ("npm ci", "npm run type-check", "npm run lint", "npm test",
                "npm run build", "ruff check"):
        assert cmd in runs, f"Das Gate führt «{cmd}» nicht aus."
    for name in ("quality.yml", "deploy-dev.yml", "deploy-prod.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if "npm install" in ln and " -g " not in ln]
        assert not lines, f"{name}: «npm install» statt «npm ci»: {lines}"
    ruff = (ROOT / "backend" / "ruff.toml").read_text(encoding="utf-8")
    assert 'select = ["F"]' in ruff, "ruff prüft nicht (nur) die F-Regeln."
