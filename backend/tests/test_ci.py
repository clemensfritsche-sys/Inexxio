"""**Die CI prüft, was sie verspricht** – ein Wächter, der nur lokal läuft, ist keiner.

Die Prüfungen stehen EINMAL in ``quality.yml``; ausgerollt wird über ``deploy.yml``, und
jeder Job, der ausrollt, hängt am Gate.
"""

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _needs(job: dict) -> set[str]:
    needs = job.get("needs") or []
    return {needs} if isinstance(needs, str) else set(needs)


def _upstream(jobs: dict, name: str) -> set[str]:
    seen: set[str] = set()
    todo = [name]
    while todo:
        for dep in _needs(jobs[todo.pop()]):
            if dep not in seen:
                seen.add(dep)
                todo.append(dep)
    return seen


def _runs(job: dict) -> str:
    return "\n".join(s.get("run", "") for s in job.get("steps", []))


def test_every_deploy_waits_for_the_one_gate():
    """Bug-Formen: ein Deploy ohne Gate; ein ausrollender Job, der nicht (auch nicht über
    eine Freigabe) auf das Gate wartet; eigene Prüfungen neben dem Gate."""
    for name in ("deploy-dev.yml", "deploy-prod.yml"):
        jobs = _load(name)["jobs"]
        gates = {j for j, d in jobs.items() if d.get("uses") == "./.github/workflows/quality.yml"}
        assert gates, f"{name} ruft das Gate nicht auf."
        rollout = [j for j, d in jobs.items() if d.get("uses") == "./.github/workflows/deploy.yml"]
        assert rollout, f"{name} rollt nicht über deploy.yml aus."
        for job in rollout:
            assert gates & _upstream(jobs, job), f"{name}: «{job}» wartet nicht auf das Gate."
        assert not [j for j, d in jobs.items() if "pytest" in _runs(d)], name
    prod = _load("deploy-prod.yml")["jobs"]
    assert any(d.get("environment") == "production" for j, d in prod.items()
               if j in _upstream(prod, "deploy")), "Prod rollt ohne Freigabe aus."


def test_the_rollout_uses_a_build_made_before_anything_went_out():
    """Bug-Formen: das Backend rollt aus, bevor der Build steht (ein Build-Fehler wäre ein
    Teil-Deploy); das Hosting baut selbst noch einmal statt die geprüfte Ausgabe zu nehmen."""
    jobs = _load("deploy.yml")["jobs"]
    builds = {j for j, d in jobs.items() if "npm run build" in _runs(d)}
    assert len(builds) == 1, f"Gebaut wird in {sorted(builds)} – genau einmal."
    for job, d in jobs.items():
        if "gcloud run deploy" in _runs(d) or "firebase deploy" in _runs(d):
            assert builds & _upstream(jobs, job), f"«{job}» rollt aus, bevor gebaut ist."


def test_the_backend_tests_run_against_a_required_database():
    """Ohne Datenbank übersprangen sich Prüfungen lautlos, und der Job blieb grün.
    Bug-Formen: keine DATABASE_URL; kein ``INEXXIO_REQUIRE_DB``; kein ``-rs``."""
    steps = [s for job in _load("quality.yml")["jobs"].values()
             for s in job.get("steps", []) if "pytest" in s.get("run", "")]
    assert len(steps) == 1, "pytest läuft nicht genau einmal im Gate."
    env = steps[0].get("env", {})
    assert "DATABASE_URL" in env, "Der Test-Schritt bekommt keine DATABASE_URL."
    assert str(env.get("INEXXIO_REQUIRE_DB")) == "1", "Die Datenbank ist nicht Pflicht."
    assert "-rs" in steps[0]["run"], "Skips laufen ohne Grund durch (-rs fehlt)."


def test_the_gate_checks_frontend_lint_build_and_python():
    """Bug-Formen: Lint/Build/ruff fehlen im Gate; ``npm install`` statt ``npm ci``
    (nicht reproduzierbar); ruff mit mehr als den F-Regeln (Stil statt Fehler)."""
    runs = "\n".join(_runs(j) for j in _load("quality.yml")["jobs"].values())
    for cmd in ("npm ci", "npm run type-check", "npm run lint", "npm test",
                "npm run build", "ruff check", "export-erp.mjs --check"):
        assert cmd in runs, f"Das Gate führt «{cmd}» nicht aus."
    for path in sorted(WORKFLOWS.glob("*.yml")):
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                 if "npm install" in ln and " -g " not in ln]
        assert not lines, f"{path.name}: «npm install» statt «npm ci»: {lines}"
    ruff = (ROOT / "backend" / "ruff.toml").read_text(encoding="utf-8")
    assert 'select = ["F"]' in ruff, "ruff prüft nicht (nur) die F-Regeln."
