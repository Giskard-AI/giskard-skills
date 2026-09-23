#!/usr/bin/env python3
"""Check packaging, Grok discovery, or skills CLI installation without model calls."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml


ROOT = Path(__file__).resolve().parent.parent
SKILLS_VERSION = "1.7.0"
MANIFESTS = (".claude-plugin/plugin.json", ".grok-plugin/plugin.json")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def tracked_files():
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return [Path(p) for p in result.stdout.decode().split("\0") if p]


def packaging(files):
    manifests = [json.loads((ROOT / path).read_text()) for path in MANIFESTS]
    require(manifests[0] == manifests[1], "Claude and Grok manifests differ")
    manifest = manifests[0]
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", manifest["name"]),
            "Invalid plugin name")
    require(isinstance(manifest.get("description"), str) and manifest["description"].strip(),
            "Missing plugin description")
    require(re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]), "Invalid plugin version")
    paths = manifest.get("skills")
    require(isinstance(paths, list) and paths, "No skill paths declared")
    require(all(isinstance(p, str) and p.startswith("./") for p in paths),
            "Skill paths must be relative and start with ./")
    declared = {Path(p) / "SKILL.md" for p in paths}
    require(len(declared) == len(paths), "Duplicate skill paths")
    discovered = {p for p in files if p.name == "SKILL.md"}
    require(declared == discovered,
            f"Manifest coverage mismatch: missing={discovered - declared}, extra={declared - discovered}")
    skills = {}
    for path in sorted(declared):
        require((ROOT / path).resolve().is_relative_to(ROOT), f"Path escapes repo: {path}")
        text = (ROOT / path).read_text()
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        require(match is not None, f"Missing frontmatter: {path}")
        metadata = yaml.safe_load(match.group(1))
        require(isinstance(metadata, dict), f"Invalid frontmatter: {path}")
        name = metadata.get("name")
        require(isinstance(name, str) and name == path.parent.name,
                f"Skill name must match its directory: {path}")
        require(name not in skills, f"Duplicate skill name: {name}")
        require(isinstance(metadata.get("description"), str) and metadata["description"].strip(),
                f"Missing description: {path}")
        skills[name] = path.parent
    print(f"Packaging OK: {len(skills)} skills; manifests match", flush=True)
    return manifest, skills


def snapshot(files, destination):
    for path in files:
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)


def grok(module_path, files, manifest, skills):
    spec = importlib.util.spec_from_file_location("plugin_catalog", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="giskard-grok-smoke-") as temp:
        root = Path(temp)
        snapshot(files, root)
        # Exercise each manifest independently, including Claude fallback support.
        for hidden in (".claude-plugin", ".grok-plugin"):
            original = root / hidden / "plugin.json"
            backup = original.with_suffix(".disabled")
            original.rename(backup)
            try:
                result = module.extract_plugin(root)
                found = [item["name"] for item in result["components"].get("skills", [])]
                require(set(found) == set(skills) and len(found) == len(skills),
                        f"Grok discovery mismatch with {hidden} hidden: {found}")
                require(result.get("version") == manifest["version"], "Grok version mismatch")
            finally:
                backup.rename(original)
    print("Grok discovery OK for both manifests independently", flush=True)


def install_skills(files, skills):
    with tempfile.TemporaryDirectory(prefix="giskard-skills-smoke-") as temp:
        root = Path(temp)
        source, project = root / "source", root / "project"
        snapshot(files, source)
        project.mkdir()
        env = {**os.environ, "DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
               "CI": "1", "npm_config_cache": str(root / "npm-cache")}
        command = ["npx", "--yes", f"skills@{SKILLS_VERSION}", "add", str(source)]
        listing = subprocess.run(command + ["--list"], cwd=project, env=env,
                                 capture_output=True, text=True, timeout=180)
        require(listing.returncode == 0,
                f"skills CLI discovery failed:\n{listing.stdout}\n{listing.stderr}")
        for name in skills:
            require(name in listing.stdout, f"skills CLI did not list {name}: {listing.stdout}")
        subprocess.run(command + ["--skill", "*", "--agent", "claude-code", "cursor", "grok",
                                  "--copy", "--yes"],
                       cwd=project, env=env, check=True, timeout=180)
        # skills 1.7.0 installs Cursor skills to the shared .agents directory.
        for agent_dir in (".claude", ".agents", ".grok"):
            installed = project / agent_dir / "skills"
            found = {p.parent.name for p in installed.glob("*/SKILL.md")}
            require(found == set(skills), f"Installed skill mismatch in {agent_dir}: {found}")
            for name, source_dir in skills.items():
                for path in files:
                    if path.is_relative_to(source_dir):
                        copied = installed / name / path.relative_to(source_dir)
                        require(copied.is_file() and copied.read_bytes() == (source / path).read_bytes(),
                                f"Missing or changed installed file: {copied}")
    print("skills CLI discovery and copied resources OK for Claude Code, Cursor, and Grok", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("packaging", "grok", "skills"))
    parser.add_argument("--grok-catalog", type=Path, help="Path to xAI scripts/plugin_catalog.py")
    args = parser.parse_args()
    files = tracked_files()
    manifest, skills = packaging(files)
    if args.target == "grok":
        if args.grok_catalog is None:
            parser.error("--grok-catalog is required")
        grok(args.grok_catalog, files, manifest, skills)
    elif args.target == "skills":
        install_skills(files, skills)


if __name__ == "__main__":
    main()
