"""ARCHITECTURE.md §1.1 import rules and DEC-004 safety (T-002)."""

from __future__ import annotations

import ast
import importlib
import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "netcore"

FORBIDDEN: dict[str, tuple[str, ...]] = {
    "domain": (
        "textual",
        "sqlite3",
        "netcore.application",
        "netcore.infrastructure",
        "netcore.tui",
        "netcore.bootstrap",
    ),
    "application": ("textual", "sqlite3", "netcore.infrastructure", "netcore.tui"),
    "tui": ("sqlite3", "netcore.infrastructure", "netcore.domain"),
}
GLOBAL_FORBIDDEN = ("socket", "subprocess", "ctypes", "scapy")
FORBIDDEN_CALLS = {("os", "system"), (None, "eval"), (None, "exec")}


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = _module_name(path)
    if path.name != "__init__.py":
        package = package.rsplit(".", 1)[0]
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - node.level + 1]
                names.append(".".join([*base, node.module or ""]).rstrip("."))
            elif node.module:
                names.append(node.module)
    return names


def _files(pkg: str) -> list[Path]:
    return sorted((SRC / pkg).rglob("*.py"))


def _violations(pkg: str, forbidden: tuple[str, ...]) -> list[str]:
    bad = []
    for path in _files(pkg):
        for name in _imports(path):
            if any(name == f or name.startswith(f + ".") for f in forbidden):
                bad.append(f"{path.relative_to(SRC)} imports {name}")
    return bad


@pytest.mark.parametrize("pkg", sorted(FORBIDDEN))
def test_layer_rules(pkg):
    assert _violations(pkg, FORBIDDEN[pkg]) == []


def test_tui_only_uses_application_enums_via_dto():
    """TUI must not import domain entities (enums come via application.dto)."""
    assert _violations("tui", ("netcore.domain",)) == []


def test_no_network_or_shell_in_src():
    bad = []
    for path in sorted(SRC.rglob("*.py")):
        for name in _imports(path):
            if name.split(".")[0] in GLOBAL_FORBIDDEN:
                bad.append(f"{path.relative_to(SRC)} imports {name}")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    key = (func.value.id, func.attr)
                elif isinstance(func, ast.Name):
                    key = (None, func.id)
                else:
                    continue
                if key in FORBIDDEN_CALLS:
                    bad.append(f"{path.relative_to(SRC)} calls {key}")
    assert bad == []


def test_guard_detects_bad_import(tmp_path, monkeypatch):
    """The guard itself works: a deliberate bad import is caught."""
    fake = tmp_path / "netcore" / "domain"
    fake.mkdir(parents=True)
    (fake / "bad.py").write_text("import sqlite3\nfrom netcore.tui import app\n")
    monkeypatch.setattr(sys.modules[__name__], "SRC", tmp_path / "netcore")
    found = _violations("domain", FORBIDDEN["domain"])
    assert len(found) == 2


def test_no_circular_imports():
    """Import every module in a fresh interpreter."""
    import netcore

    names = [
        m.name
        for m in pkgutil.walk_packages(netcore.__path__, "netcore.")
        if ".migrations" not in m.name
    ]
    code = "import importlib\n" + "".join(
        f"importlib.import_module({n!r})\n" for n in names
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
    for name in names[:3]:
        importlib.import_module(name)
