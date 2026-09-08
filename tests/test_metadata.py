"""Automated tests for repository metadata, badges, documentation, and manifest parity."""

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

from ellmos_scheduler import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_version_consistency_across_manifests_and_docs():
    """Verify package version is strictly aligned across pyproject.toml, manifest, code, and README badges."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "ellmos-module.v2.json").read_text(encoding="utf-8"))

    pkg_version = pyproject["project"]["version"]
    assert pkg_version == __version__, f"pyproject.toml version ({pkg_version}) != __version__ ({__version__})"
    assert manifest["version"] == __version__, f"ellmos-module.v2.json version ({manifest['version']}) != __version__ ({__version__})"

    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    expected_badge = f"version-{__version__}-blue.svg"
    assert expected_badge in readme_en, f"README.md missing expected version badge: {expected_badge}"
    assert expected_badge in readme_de, f"README_de.md missing expected version badge: {expected_badge}"


def test_readme_badges_and_language_parity():
    """Verify badges, banners, and language navigation links match in English and German docs."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    # Both must reference header banner
    assert 'src="assets/banner.png"' in readme_en
    assert 'src="assets/banner.png"' in readme_de

    # Both must provide language switch links
    assert "[English](README.md) | [Deutsch](README_de.md)" in readme_en
    assert "[English](README.md) | [Deutsch](README_de.md)" in readme_de

    # Required badge signatures
    required_badges = [
        "python-3.10%2B-blue.svg",
        "platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg",
        "License-MIT-yellow.svg",
        "tests-111%20passed-brightgreen.svg",
        "code%20style-ruff-000000.svg",
        "security-Local--First-green.svg",
        "privacy-Zero--Egress-success.svg",
        "ecosystem-ellmos--ai-purple.svg",
        "umbrella-open--bricks-blueviolet.svg",
        "LLM--Ready-llms.txt-orange.svg",
    ]

    for badge in required_badges:
        assert badge in readme_en, f"README.md missing badge: {badge}"
        assert badge in readme_de, f"README_de.md missing badge: {badge}"


def test_architecture_and_sequence_diagrams():
    """Verify both README documents contain architecture and execution sequence Mermaid diagrams."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "```mermaid\ngraph TD" in readme_en
    assert "```mermaid\ngraph TD" in readme_de

    assert "```mermaid\nsequenceDiagram" in readme_en
    assert "```mermaid\nsequenceDiagram" in readme_de


def test_sibling_ecosystem_matrix():
    """Verify comprehensive cross-linking to sibling ecosystem projects in both documentation files."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    key_siblings = [
        "ellmos-core",
        "clutch",
        "coma",
        "gardener",
        "prompt-evidence-collector",
        "lock-master",
        "ticket-master",
        "ellmos-controlcenter-mcp",
        "ellmos-filecommander-mcp",
        "ellmos-codecommander-mcp",
        "ellmos-clatcher-mcp",
        "n8n-manager-mcp",
        "skills",
        "safe-start-for-codex",
        "automizer-for-claude-desktop",
        "DevCenter",
        "CodeBox",
        "open-bricks",
    ]

    for sibling in key_siblings:
        assert sibling in readme_en, f"README.md missing sibling reference: {sibling}"
        assert sibling in readme_de, f"README_de.md missing sibling reference: {sibling}"


def test_llms_txt_structure_and_timestamp():
    """Verify llms.txt index existence, key sections, and recent timestamp."""
    llms_path = ROOT / "llms.txt"
    assert llms_path.is_file(), "llms.txt must exist"

    content = llms_path.read_text(encoding="utf-8")
    assert "## Core Capabilities" in content
    assert "## Directory Structure & Key Files" in content
    assert "## CLI Usage Quick Reference" in content
    assert "## Integration & Metadata" in content
    assert "SECURITY.md" in content
    assert "2026-09-08" in content
    assert "Governance & Runtime Invariants" in content


def test_security_policy_structure():
    """Verify SECURITY.md policy sections in English and German."""
    sec_path = ROOT / "SECURITY.md"
    assert sec_path.is_file(), "SECURITY.md must exist"

    content = sec_path.read_text(encoding="utf-8")
    assert '<a name="english"></a>' in content
    assert '<a name="deutsch"></a>' in content
    assert "Local-First & Zero-Egress Invariant" in content
    assert "Local-First & Zero-Egress-Invariante" in content
    assert "security@ellmos.ai" in content
    assert "support@lukasgeiger.com" in content
    assert "lukas@open-bricks.org" in content
    assert "48 hours" in content or "48 Stunden" in content
    assert "5 business days" in content or "5 Werktagen" in content
    assert "0.3.x" in content


def test_module_manifest_validity():
    """Verify ellmos-module.v2.json adheres to schema and provides declared capabilities."""
    manifest_path = ROOT / "ellmos-module.v2.json"
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest.get("schema") == "ellmos.module.v2"
    assert manifest.get("id") == "ellmos-scheduler"
    assert manifest.get("category") == "control"
    assert "automation.schedule" in manifest.get("provides", [])
    assert "automation.lease" in manifest.get("provides", [])
    assert "automation.authority-receipt" in manifest.get("provides", [])


def test_github_actions_workflow_concurrency_and_matrix():
    """Verify GitHub Actions CI workflow configures concurrency control and multi-OS matrix."""
    workflow_path = ROOT / ".github" / "workflows" / "test.yml"
    assert workflow_path.is_file(), "test.yml workflow must exist"

    content = workflow_path.read_text(encoding="utf-8")
    assert "concurrency:" in content
    assert "cancel-in-progress: true" in content
    assert "ubuntu-latest" in content
    assert "windows-latest" in content
    assert "macos-latest" in content
    assert "actions/checkout@v4" in content
    assert "actions/setup-python@v5" in content


def test_pep621_project_urls_and_metadata():
    """Verify PEP 621 pyproject.toml declares standard ecosystem URLs and metadata."""
    pyproject_path = ROOT / "pyproject.toml"
    assert pyproject_path.is_file(), "pyproject.toml must exist"

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    urls = pyproject.get("project", {}).get("urls", {})
    assert "Homepage" in urls
    assert "Repository" in urls
    assert "Issues" in urls
    assert "Changelog" in urls
    assert "Documentation" in urls
    assert "Security" in urls
    assert urls.get("Parent Organization") == "https://github.com/ellmos-ai"
    assert urls.get("Umbrella Ecosystem") == "https://github.com/open-bricks"


def test_gitignore_hygiene():
    """Verify .gitignore includes sync conflict, lock, and test cache patterns."""
    gitignore_path = ROOT / ".gitignore"
    assert gitignore_path.is_file(), ".gitignore must exist"

    content = gitignore_path.read_text(encoding="utf-8")
    assert "*.sync-conflict-*" in content
    assert "*.conflict" in content
    assert "*-CONFLIT-*" in content
    assert "LOCK*.txt" in content
    assert ".pytest_cache/" in content
    assert ".ruff_cache/" in content
    assert ".coverage" in content
    assert ".wheel-smoke/" in content


def test_readme_quick_navigation_anchors():
    """Verify both README files provide complete 14-point quick navigation blocks with matching anchors."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    en_anchors = [
        "(#ellmos-scheduler)",
        "(#architecture--system-overview)",
        "(#execution--authority-preflight-lifecycle)",
        "(#governance--runtime-invariants)",
        "(#responsibility-boundary)",
        "(#supported-schedules)",
        "(#quick-start)",
        "(#canonical-authorities-per-run)",
        "(#security-and-availability-model)",
        "(#migration-from-bach)",
        "(#bundles-and-partners)",
        "(#ecosystem--sibling-tools)",
        "(#changelog)",
        "(#license)",
    ]

    de_anchors = [
        "(#ellmos-scheduler)",
        "(#architektur--systemübersicht)",
        "(#ausführungs--authority-preflight-lebenszyklus)",
        "(#governance--laufzeit-invarianten)",
        "(#verantwortungsgrenze)",
        "(#unterstützte-zeitpläne)",
        "(#schnellstart)",
        "(#kanonische-autoritäten-pro-lauf)",
        "(#sicherheits--und-verfügbarkeitsmodell)",
        "(#migration-von-bach)",
        "(#bundles-und-partner)",
        "(#ökosystem--geschwister-werkzeuge)",
        "(#änderungsprotokoll)",
        "(#lizenz)",
    ]

    for anchor in en_anchors:
        assert anchor in readme_en, f"README.md missing navigation anchor: {anchor}"

    for anchor in de_anchors:
        assert anchor in readme_de, f"README_de.md missing navigation anchor: {anchor}"


def test_governance_and_runtime_invariants_table():
    """Verify that both README files provide the complete 10-point Governance & Runtime Invariants table."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    en_invariants = [
        "1. 100% Local-First & Zero-Egress",
        "2. Unprivileged Non-Elevation Execution",
        "3. Atomic SQLite Leases & Deduplication",
        "4. Double Read-Only Authority Preflight",
        "5. Strict UTF-8 & Fail-Closed Decoding",
        "6. Shell-Free Safe Process Invocation",
        "7. Fail-Closed Timeout & Abandoned Leases",
        "8. Declarative Modular Integration",
        "9. Multi-OS Cross-Platform Parity",
        "10. Cryptographic Receipt Persistence",
    ]

    de_invariants = [
        "1. 100% Local-First & Zero-Egress",
        "2. Unprivilegierter User-Mode Betrieb",
        "3. Atomare SQLite-Leases & Deduplizierung",
        "4. Zweifache Read-Only Authority-Prüfung",
        "5. Strikte UTF-8- & Fail-Closed Kodierung",
        "6. Shell-freie sichere Prozessausführung",
        "7. Fail-Closed Timeout & Lease-Wiederherstellung",
        "8. Deklarative modulare Entkopplung",
        "9. Plattformübergreifende Parität",
        "10. Kryptographische Receipt-Persistenz",
    ]

    for inv in en_invariants:
        assert inv in readme_en, f"README.md missing governance invariant: {inv}"

    for inv in de_invariants:
        assert inv in readme_de, f"README_de.md missing governance invariant: {inv}"


def test_ci_status_and_quality_badges():
    """Verify CI workflow link and quality badges exist in both documentation files."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    ci_badge = "actions/workflows/test.yml/badge.svg"
    ruff_badge = "code%20style-ruff-000000.svg"

    assert ci_badge in readme_en, "README.md missing CI workflow badge"
    assert ci_badge in readme_de, "README_de.md missing CI workflow badge"
    assert ruff_badge in readme_en, "README.md missing Ruff code style badge"
    assert ruff_badge in readme_de, "README_de.md missing Ruff code style badge"


def test_local_marketing_log_audit():
    """Verify local MARKETING-LOG.txt exists and documents Pfad B execution details."""
    log_path = ROOT / "MARKETING-LOG.txt"
    assert log_path.is_file(), "MARKETING-LOG.txt must exist in repo root"

    content = log_path.read_text(encoding="utf-8")
    assert "2026-09-08" in content
    assert "ellmos-scheduler" in content
    assert "Pfad B" in content
    assert "Governance & Runtime Invariants Matrix" in content


def test_changelog_recent_pfad_b_entry():
    """Verify CHANGELOG.md contains the 2026-09-08 Pfad B release entry."""
    changelog_path = ROOT / "CHANGELOG.md"
    assert changelog_path.is_file(), "CHANGELOG.md must exist"

    content = changelog_path.read_text(encoding="utf-8")
    assert "## [0.3.1] - 2026-09-08" in content
    assert "Discoverability, Visual Architecture, Governance Invariants & Metadata Parity (Pfad B)" in content
