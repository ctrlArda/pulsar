from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from . import jury_smoke_test


ROOT_DIR = Path(__file__).resolve().parents[2]
ENGINE_DIR = ROOT_DIR / "engine"
TESTS_DIR = ENGINE_DIR / "tests"


@dataclass(slots=True)
class BackendCheck:
    label: str
    ok: bool
    detail: str


def _status(ok: bool) -> str:
    return "[PASS]" if ok else "[FAIL]"


def _compile_backend() -> BackendCheck:
    import compileall

    ok = compileall.compile_dir(str(ENGINE_DIR / "helioguard"), quiet=1)
    return BackendCheck("Python compileall", ok, "helioguard package syntax taramasi")


def _load_test_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Modul yuklenemedi: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_local_tests() -> list[BackendCheck]:
    checks: list[BackendCheck] = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        try:
            module = _load_test_module(path)
            functions = [
                getattr(module, name)
                for name in dir(module)
                if name.startswith("test_") and callable(getattr(module, name))
            ]
            if not functions:
                checks.append(BackendCheck(f"Local tests {path.name}", True, "Test fonksiyonu bulunmadi"))
                continue
            executed = 0
            for func in functions:
                func()
                executed += 1
            checks.append(BackendCheck(f"Local tests {path.name}", True, f"{executed} test fonksiyonu calisti"))
        except Exception as exc:
            checks.append(BackendCheck(f"Local tests {path.name}", False, str(exc)))
    return checks


async def _run_smoke(mode: str) -> BackendCheck:
    try:
        exit_code = await jury_smoke_test.run(mode)
        return BackendCheck(f"Jury smoke ({mode})", exit_code == 0, f"mode={mode}")
    except Exception as exc:
        return BackendCheck(f"Jury smoke ({mode})", False, str(exc))


async def _run_smoke_strict_live() -> BackendCheck:
    try:
        exit_code = await jury_smoke_test.run("live", strict_live=True)
        return BackendCheck("Jury smoke (live strict)", exit_code == 0, "mode=live strict")
    except Exception as exc:
        return BackendCheck("Jury smoke (live strict)", False, str(exc))


async def run_backend_suite(include_live: bool, live_only: bool, strict_live: bool) -> int:
    checks: list[BackendCheck] = []

    compile_check = _compile_backend()
    checks.append(compile_check)
    checks.extend(_run_local_tests())
    if not live_only:
        checks.append(await _run_smoke("archive"))
    if include_live or live_only:
        if strict_live:
            checks.append(await _run_smoke_strict_live())
        else:
            checks.append(await _run_smoke("live"))

    print("")
    print("HELIOGUARD BACKEND TEST SUITE")
    print("=============================")
    for check in checks:
        print(f"{_status(check.ok)} {check.label}: {check.detail}")

    failed = [check for check in checks if not check.ok]
    print("")
    if failed:
        print(f"Sonuc: {len(failed)} adim basarisiz.")
        return 1

    if strict_live and (include_live or live_only):
        print("Sonuc: tum backend kontrolleri (unit + strict live) basarili.")
    elif include_live and not live_only:
        print("Sonuc: tum backend kontrolleri (unit + archive + live) basarili.")
    elif live_only:
        print("Sonuc: tum backend kontrolleri (unit + live) basarili.")
    else:
        print("Sonuc: tum backend kontrolleri (unit + archive) basarili.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full HELIOGUARD backend verification suite.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Canli veri baglantilarini da test et.",
    )
    parser.add_argument(
        "--live-only",
        action="store_true",
        help="Archive smoke testini atla, sadece canli veri akisini test et.",
    )
    parser.add_argument(
        "--strict-live",
        action="store_true",
        help="Canli modda tum kaynaklarin state=live olmasini zorunlu kil.",
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            run_backend_suite(
                include_live=args.live,
                live_only=args.live_only,
                strict_live=args.strict_live,
            )
        )
    )


if __name__ == "__main__":
    main()
