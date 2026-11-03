"""Static enforcement of the external consumer boundary.

This is an architecture check, not a security sandbox. Runtime owns execution
isolation and Authority. Consumer code must never import a private Runtime
implementation or modify Python's module search path.
"""

from __future__ import annotations

import ast
from pathlib import Path
import tomllib

PUBLIC_ROOTS = ("agent_meta_runtime.sdk", "agent_meta_runtime.protocols.public")


def check_source(source: str, filename: str = "<source>") -> list[str]:
    tree = ast.parse(source, filename)
    issues = []
    aliases = {}
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            for alias in node.names:
                name = f"{node.module}.{alias.name}"
                imports.append((node.lineno, name))
                aliases[alias.asname or alias.name] = name

    def qualified(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{qualified(node.value)}.{node.attr}"
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = qualified(node.func)
            if name in {"__import__", "importlib.import_module"}:
                # Dynamic module selection prevents a sound public-import audit.
                if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                    issues.append(f"{filename}:{node.lineno}: dynamic import target")
                else:
                    imports.append((node.lineno, node.args[0].value))
            if name.startswith("sys.path.") or name == "os.chdir":
                issues.append(f"{filename}:{node.lineno}: checkout-dependent {name}")
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if qualified(target).startswith("sys.path") or isinstance(target, ast.Subscript) and qualified(target.value) == "sys.path":
                    issues.append(f"{filename}:{node.lineno}: sys.path mutation")
    for line, name in imports:
        if name == "agent_meta_runtime" or name.startswith("agent_meta_runtime."):
            if not any(name == root or name.startswith(root + ".") for root in PUBLIC_ROOTS) or any(part.startswith("_") for part in name.split(".")):
                issues.append(f"{filename}:{line}: private Runtime import {name}")
    return sorted(set(issues))


def check_project(root: Path) -> list[str]:
    issues = []
    for directory in ("src", "tests", "scripts"):
        for path in sorted((root / directory).rglob("*.py")):
            issues.extend(check_source(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix()))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"].get("dependencies", [])
    runtime = [value for value in dependencies if value.startswith("agent-meta-runtime==")]
    if len(runtime) != 1:
        issues.append("pyproject.toml: exactly one pinned Runtime wheel version required")
    for dependency in dependencies:
        if any(token in dependency for token in ("file:", "../", "..\\", " @ ", "-e ")):
            issues.append("pyproject.toml: local/editable dependency forbidden")
    return sorted(issues)
