from __future__ import annotations

import argparse
import ctypes
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import zipfile

from cursor_pack import build_zip, safe_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Windows cursor pack from an approved 5x4 sheet")
    parser.add_argument("--sheet", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    sheet = Path(args.sheet).resolve()
    output = Path(args.out_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / f"{safe_id(args.name)}.zip"
    archive_path.write_bytes(build_zip(sheet.read_bytes(), args.name))

    extract_dir = output / f"{safe_id(args.name)}-preview"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity validation failed")
        archive.extractall(extract_dir)

    pack_dir = next(path for path in extract_dir.iterdir() if path.is_dir())
    failures = []
    if sys.platform == "win32":
        user32 = ctypes.windll.user32
        for path in sorted(pack_dir.glob("*.ani"), key=lambda item: int(item.stem)):
            handle = user32.LoadCursorFromFileW(str(path.resolve()))
            if handle:
                user32.DestroyCursor(handle)
            else:
                failures.append(path.name)

        install_path = str(pack_dir / "Install.ps1").replace("'", "''")
        command = (
            f"$e=$null;[System.Management.Automation.Language.Parser]::ParseFile('{install_path}',"
            "[ref]$null,[ref]$e)|Out-Null;if($e.Count){exit 1}"
        )
        ps_result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command], capture_output=True
        )
        ps_ok = ps_result.returncode == 0
    else:
        ps_ok = False

    print("PowerShell syntax:", "PASS" if ps_ok else "FAIL")
    print("Windows cursor loading:", "PASS" if not failures and sys.platform == "win32" else f"FAIL {failures}")
    print("ZIP integrity: PASS")
    print("Preview:", pack_dir / "预览图.png")
    print("Package:", archive_path)
    if failures or not ps_ok or sys.platform != "win32":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

