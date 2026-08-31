#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

JSON_VERSION_FILES = [
    "package.json",
    "apps/web/package.json",
    "apps/admin/package.json",
    "apps/desktop/package.json",
    "apps/mobile/package.json",
    "apps/admin-desktop/package.json",
    "apps/admin-mobile/package.json",
    "packages/api-client/package.json",
    "packages/types/package.json",
]

TAURI_FILES = [
    "apps/desktop/src-tauri/tauri.conf.json",
    "apps/mobile/src-tauri/tauri.conf.json",
    "apps/admin-desktop/src-tauri/tauri.conf.json",
    "apps/admin-mobile/src-tauri/tauri.conf.json",
]

CARGO_FILES = [
    "apps/desktop/src-tauri/Cargo.toml",
    "apps/mobile/src-tauri/Cargo.toml",
    "apps/admin-desktop/src-tauri/Cargo.toml",
    "apps/admin-mobile/src-tauri/Cargo.toml",
]

DOCKERFILES = [
    "infrastructure/docker/api/Dockerfile",
    "infrastructure/docker/worker/Dockerfile",
]


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_json_version(relative: str, version: str) -> None:
    path = ROOT / relative
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = version
    write_json(path, payload)


def sync_package_lock(version: str) -> None:
    path = ROOT / "package-lock.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = version
    packages = payload.setdefault("packages", {})
    root_package = packages.setdefault("", {})
    root_package["version"] = version
    write_json(path, payload)


def sync_cargo(relative: str, version: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^version = "[^"]+"$',
        f'version = "{version}"',
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"Não foi possível atualizar version em {relative}")
    path.write_text(updated, encoding="utf-8")


def sync_dockerfile(relative: str, version: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(?m)^ARG APP_VERSION=.*$",
        f"ARG APP_VERSION={version}",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"Não foi possível atualizar APP_VERSION em {relative}")
    path.write_text(updated, encoding="utf-8")


def sync_health_default(version: str) -> None:
    path = ROOT / "apps/api/app/api/v1/routes/health.py"
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'APP_VERSION = os\.getenv\("APP_VERSION", "[^"]+"\)',
        f'APP_VERSION = os.getenv("APP_VERSION", "{version}")',
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Não foi possível atualizar APP_VERSION em health.py")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza a versão canônica do Scheduler Pro.")
    parser.add_argument("version")
    parser.add_argument("--source-merge-sha", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--bump", choices=["initial", "patch", "minor", "major", "retry"], required=True)
    args = parser.parse_args()

    version = args.version.strip()
    if not SEMVER_RE.fullmatch(version):
        raise SystemExit(f"Versão inválida: {version}")

    (ROOT / "VERSION").write_text(version + "\n", encoding="utf-8")

    for relative in JSON_VERSION_FILES:
        sync_json_version(relative, version)

    sync_package_lock(version)

    for relative in TAURI_FILES:
        sync_json_version(relative, version)

    for relative in CARGO_FILES:
        sync_cargo(relative, version)

    for relative in DOCKERFILES:
        sync_dockerfile(relative, version)

    sync_health_default(version)

    visual_builder = json.loads((ROOT / "packages/visual-builder/package.json").read_text(encoding="utf-8"))
    major, minor, _patch = version.split(".")
    release_manifest = {
        "schema": "scheduler-pro-release-manifest/v1",
        "product": "Scheduler Pro",
        "version": version,
        "source_merge_sha": args.source_merge_sha,
        "source_pr": args.pr_number,
        "bump": args.bump,
        "visual_builder": {
            "package": visual_builder.get("name"),
            "version": visual_builder.get("version"),
        },
        "ghcr": {
            "version": version,
            "minor": f"{major}.{minor}",
            "major": major,
            "latest": "latest",
            "sha_strategy": "release-metadata-commit-sha",
        },
    }
    write_json(ROOT / "RELEASE-MANIFEST.json", release_manifest)


if __name__ == "__main__":
    main()
