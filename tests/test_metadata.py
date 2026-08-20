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
        "tests-103%20passed-brightgreen.svg",
        "security-Local--First-green.svg",
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
    assert "**Last-checked**: 2026-08-20" in content or "Last-checked: 2026-08-20" in content


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
