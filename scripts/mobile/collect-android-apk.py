#!/usr/bin/env python3
"""Seleciona e valida o APK final gerado pelo Gradle/Tauri.

Evita publicar artefatos intermediários, APKs desalinhados/não assinados ou
arquivos inflados por ABIs/símbolos indevidos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def sdk_tool(name: str) -> Path | None:
    executable = f"{name}.bat" if os.name == "nt" else name
    direct = shutil.which(name)
    if direct:
        return Path(direct)
    roots = [os.getenv("ANDROID_SDK_ROOT"), os.getenv("ANDROID_HOME")]
    candidates: list[Path] = []
    for raw in roots:
        if raw:
            candidates.extend(Path(raw).glob(f"build-tools/*/{executable}"))
    return sorted(candidates)[-1] if candidates else None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_zip(path: Path, max_bytes: int) -> dict[str, object]:
    size = path.stat().st_size
    if size < 512 * 1024:
        fail(f"APK muito pequeno para ser instalável: {size} bytes ({path})")
    if size > max_bytes:
        fail(
            f"APK excede o limite de {max_bytes // (1024 * 1024)} MiB: "
            f"{size / (1024 * 1024):.1f} MiB ({path})"
        )
    with zipfile.ZipFile(path) as archive:
        broken = archive.testzip()
        if broken:
            fail(f"APK ZIP corrompido em {broken}: {path}")
        infos = archive.infolist()
        names = {entry.filename for entry in infos}
        if "AndroidManifest.xml" not in names:
            fail(f"AndroidManifest.xml ausente: {path}")
        if not any(name == "classes.dex" or name.startswith("classes") and name.endswith(".dex") for name in names):
            fail(f"classes.dex ausente: {path}")
        arm64 = [name for name in names if name.startswith("lib/arm64-v8a/") and name.endswith(".so")]
        if not arm64:
            fail(f"Biblioteca ARM64 ausente: {path}")
        other_abis = sorted(
            {
                name.split("/", 2)[1]
                for name in names
                if name.startswith("lib/") and name.count("/") >= 2
                and not name.startswith("lib/arm64-v8a/")
            }
        )
        if other_abis:
            fail(f"APK ARM64 contém ABIs adicionais que inflam o arquivo: {other_abis}")
        largest = max(infos, key=lambda item: item.file_size)
        if largest.file_size > 160 * 1024 * 1024:
            fail(f"Entrada individual excessiva no APK: {largest.filename} ({largest.file_size} bytes)")
        return {
            "entries": len(infos),
            "arm64_libraries": len(arm64),
            "largest_entry": largest.filename,
            "largest_entry_bytes": largest.file_size,
        }


def verify_signature(path: Path, required: bool) -> str:
    tool = sdk_tool("apksigner")
    if tool is None:
        if required:
            fail("apksigner não encontrado no Android SDK; assinatura não pôde ser validada.")
        return "apksigner-unavailable"
    process = subprocess.run(
        [str(tool), "verify", "--verbose", "--print-certs", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if process.returncode != 0:
        fail(f"Assinatura APK inválida ({path}):\n{process.stdout[-4000:]}")
    return process.stdout[-4000:]


def package_metadata(path: Path) -> str | None:
    tool = sdk_tool("aapt2")
    if tool is None:
        return None
    process = subprocess.run(
        [str(tool), "dump", "badging", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if process.returncode != 0:
        fail(f"aapt2 não reconheceu o APK ({path}):\n{process.stdout[-3000:]}")
    return process.stdout[:8000]


def candidates(app: Path) -> list[Path]:
    roots = [
        app / "src-tauri" / "gen" / "android" / "app" / "build" / "outputs" / "apk",
        app / "src-tauri" / "gen" / "android" / "build" / "outputs" / "apk",
    ]
    result: list[Path] = []
    for root in roots:
        if root.is_dir():
            for item in root.rglob("*.apk"):
                lower = item.name.lower()
                if "unsigned" in lower or "unaligned" in lower or "androidtest" in lower:
                    continue
                result.append(item)
    return sorted(set(result), key=lambda item: (item.stat().st_mtime_ns, item.stat().st_size), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("app_path", type=Path)
    parser.add_argument("output_apk", type=Path)
    parser.add_argument("--max-mib", type=int, default=int(os.getenv("APK_MAX_MIB", "200")))
    parser.add_argument("--require-signature", action="store_true")
    args = parser.parse_args()

    app = args.app_path.resolve()
    found = candidates(app)
    if not found:
        fail(
            "Nenhum APK final encontrado em app/build/outputs/apk. "
            "Artefatos de target/intermediates não são aceitos."
        )

    failures: list[str] = []
    selected: Path | None = None
    zip_report: dict[str, object] | None = None
    signature = ""
    metadata: str | None = None
    for item in found:
        try:
            zip_report = validate_zip(item, args.max_mib * 1024 * 1024)
            signature = verify_signature(item, args.require_signature)
            metadata = package_metadata(item)
            selected = item
            break
        except Exception as exc:
            failures.append(f"{item}: {exc}")

    if selected is None or zip_report is None:
        fail("Nenhum APK final passou na validação:\n" + "\n".join(failures))

    output = args.output_apk.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(selected, output)
    report = {
        "source": str(selected),
        "output": str(output),
        "bytes": output.stat().st_size,
        "mib": round(output.stat().st_size / (1024 * 1024), 2),
        "sha256": sha256(output),
        "zip": zip_report,
        "signature": signature,
        "package_metadata": metadata,
        "rejected_candidates": failures,
    }
    report_path = output.with_suffix(output.suffix + ".validation.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    output.with_suffix(output.suffix + ".sha256").write_text(f"{report['sha256']}  {output.name}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"APK validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
