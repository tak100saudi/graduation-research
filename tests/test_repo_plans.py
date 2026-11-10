"""Checks against the real repository plans."""
import json
import subprocess
import sys

from conftest import REPO
from studio.model import Project, validate_project
from studio.providers import SUPPORTED, get_provider


def test_exactly_22_video_slots_with_all_concept_families():
    p = Project.load(REPO)
    ids = p.campaign["video_ids"]
    assert len(ids) == 22 == p.campaign["expected_video_count"]
    assert ids[:2] == ["HERO42", "HERO15"]
    for fam in "TSXY":
        assert [f"{fam}{i}" for i in range(1, 6)] == [i for i in ids if i[0] == fam and len(i) == 2]
    assert set(ids) == set(p.videos)


def test_repo_plans_have_no_structural_errors_but_block_production():
    rep = validate_project(Project.load(REPO))
    assert rep.errors == []
    assert rep.ok(production=False) and not rep.ok(production=True)


def test_no_placeholder_creative_content_is_presented_as_final():
    for v in Project.load(REPO).videos.values():
        if v["source_status"] in ("pending_source", "unidentified", "pending_script"):  # none left once all are scripted
            assert v["shots"] == [] and v["concept"] == ""


def test_cli_validate_exit_codes():
    run = lambda *a: subprocess.run([sys.executable, str(REPO / "scripts" / "studio.py"), *a], capture_output=True)
    assert run("validate").returncode == 0
    assert run("validate", "--production").returncode == 1
    out = json.loads(run("validate", "--json").stdout)
    assert set(out) == {"errors", "blockers", "warnings"}


def test_shipped_provider_specs_are_unverified_and_contain_no_guessed_endpoints():
    specs = json.loads((REPO / "config" / "providers.json").read_text())["providers"]
    for name in SUPPORTED:
        s = specs[name]
        assert s["verified"] is False and s["submit"]["url"] == "" and s["model"] == ""
        assert not get_provider(name, root=REPO, env={}).readiness()["ready"]


def test_shipped_prices_are_null():
    rates = json.loads((REPO / "config" / "pricing.json").read_text())["rates"]
    assert all(r["usd_per_second"] is None for r in rates.values())


def test_no_secrets_committed():
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.split()
    assert ".env" not in tracked
    env_example = (REPO / ".env.example").read_text()
    for line in env_example.splitlines():
        if line.startswith("SV_") and "KEY" in line:
            assert line.split("=", 1)[1].strip() == ""
