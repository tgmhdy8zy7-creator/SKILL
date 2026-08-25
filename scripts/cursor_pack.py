from __future__ import annotations

from collections import deque
from io import BytesIO
import re
import struct
import zipfile

from PIL import Image, ImageDraw


SIZE = 128
ROLES = [
    "normal", "help", "working", "busy", "precision", "text", "handwriting",
    "unavailable", "vertical", "horizontal", "diagonal1", "diagonal2", "move",
    "alternate", "link", "person", "location",
]
ROLE_TO_FILE = {
    "busy": 1, "alternate": 2, "link": 3, "text": 4, "precision": 5,
    "unavailable": 6, "working": 7, "help": 8, "normal": 9,
    "horizontal": 10, "vertical": 11, "move": 12, "diagonal2": 13,
    "diagonal1": 14, "handwriting": 15, "person": 16, "location": 17,
}
REGISTRY_NAMES = {
    "normal": "Arrow", "help": "Help", "working": "AppStarting", "busy": "Wait",
    "precision": "Crosshair", "text": "IBeam", "handwriting": "NWPen", "unavailable": "No",
    "vertical": "SizeNS", "horizontal": "SizeWE", "diagonal1": "SizeNWSE",
    "diagonal2": "SizeNESW", "move": "SizeAll", "alternate": "UpArrow", "link": "Hand",
    "location": "Pin", "person": "Person",
}
SYSTEM_IDS = {
    "normal": 32512, "text": 32513, "busy": 32514, "precision": 32515, "alternate": 32516,
    "diagonal1": 32642, "diagonal2": 32643, "horizontal": 32644, "vertical": 32645,
    "move": 32646, "unavailable": 32648, "link": 32649, "working": 32650,
    "help": 32651, "location": 32671, "person": 32672,
}
HOTSPOTS = {
    "normal": (.08, .08), "help": (.10, .10), "working": (.10, .10), "busy": (.5, .5),
    "precision": (.5, .5), "text": (.5, .5), "handwriting": (.12, .85),
    "unavailable": (.5, .5), "vertical": (.5, .5), "horizontal": (.5, .5),
    "diagonal1": (.5, .5), "diagonal2": (.5, .5), "move": (.5, .5),
    "alternate": (.10, .10), "link": (.72, .22), "person": (.5, .5), "location": (.5, .72),
}


def safe_id(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "", name)
    return (value[:42] or "Custom") + "CursorTheme"


def remove_outer_background(image: Image.Image, threshold: int = 238) -> Image.Image:
    image = image.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    seen = bytearray(width * height)
    queue = deque()
    for x in range(width):
        queue.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        queue.extend(((0, y), (width - 1, y)))
    while queue:
        x, y = queue.popleft()
        index = y * width + x
        if seen[index]:
            continue
        seen[index] = 1
        red, green, blue, _ = pixels[x, y]
        if min(red, green, blue) < threshold or max(red, green, blue) - min(red, green, blue) > 12:
            continue
        pixels[x, y] = (255, 255, 255, 0)
        if x: queue.append((x - 1, y))
        if x + 1 < width: queue.append((x + 1, y))
        if y: queue.append((x, y - 1))
        if y + 1 < height: queue.append((x, y + 1))
    return image


def split_grid(sheet: Image.Image) -> list[Image.Image]:
    width, height = sheet.size
    cell_width, cell_height = width / 5, height / 4
    cells = []
    for index in range(17):
        column, row = index % 5, index // 5
        margin_x, margin_y = cell_width * .045, cell_height * .045
        crop = (
            round(column * cell_width + margin_x), round(row * cell_height + margin_y),
            round((column + 1) * cell_width - margin_x), round((row + 1) * cell_height - margin_y),
        )
        cells.append(sheet.crop(crop))
    return cells


def prepare(cell: Image.Image, role: str) -> tuple[Image.Image, tuple[int, int]]:
    piece = remove_outer_background(cell)
    alpha_box = piece.getchannel("A").getbbox()
    if not alpha_box:
        raise ValueError(f"Empty generated cell for role: {role}")
    piece = piece.crop(alpha_box)
    scale = min((SIZE - 8) / piece.width, (SIZE - 8) / piece.height)
    piece = piece.resize((max(1, round(piece.width * scale)), max(1, round(piece.height * scale))), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    offset = ((SIZE - piece.width) // 2, (SIZE - piece.height) // 2)
    canvas.alpha_composite(piece, offset)
    hotspot = HOTSPOTS[role]
    return canvas, (round(hotspot[0] * (SIZE - 1)), round(hotspot[1] * (SIZE - 1)))


def cur_bytes(image: Image.Image, hotspot: tuple[int, int]) -> bytes:
    stream = BytesIO()
    image.save(stream, "PNG")
    payload = stream.getvalue()
    return struct.pack("<HHH", 0, 2, 1) + struct.pack(
        "<BBBBHHII", SIZE, SIZE, 0, 0, hotspot[0], hotspot[1], len(payload), 22
    ) + payload


def chunk(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) & 1 else b"")


def ani_bytes(image: Image.Image, hotspot: tuple[int, int]) -> bytes:
    icon = cur_bytes(image, hotspot)
    anih = struct.pack("<9I", 36, 1, 1, SIZE, SIZE, 32, 1, 8, 1)
    body = b"ACON" + chunk(b"anih", anih) + chunk(b"rate", struct.pack("<I", 8))
    body += chunk(b"seq ", struct.pack("<I", 0)) + chunk(b"LIST", b"fram" + chunk(b"icon", icon))
    return b"RIFF" + struct.pack("<I", len(body)) + body


def installer(name: str, target: str) -> str:
    paths = "\n".join(f'    {REGISTRY_NAMES[role]} = "{ROLE_TO_FILE[role]}.ani"' for role in ROLES)
    ids = "; ".join(f"{REGISTRY_NAMES[role]}={value}" for role, value in SYSTEM_IDS.items())
    ordered = ",".join(f'"{REGISTRY_NAMES[role]}"' for role in ROLES)
    return f'''$ErrorActionPreference = "Stop"
$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetDir = Join-Path $env:LOCALAPPDATA "{target}"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Copy-Item -Path (Join-Path $sourceDir "*.ani") -Destination $targetDir -Force
$cursorKey = "HKCU:\\Control Panel\\Cursors"
$paths = @{{
{paths}
}}
Set-Item -LiteralPath $cursorKey -Value "{name}"
Set-ItemProperty -LiteralPath $cursorKey -Name "Scheme Source" -Value 1 -Type DWord
foreach ($entry in $paths.GetEnumerator()) {{ Set-ItemProperty -LiteralPath $cursorKey -Name $entry.Key -Value (Join-Path $targetDir $entry.Value) -Type ExpandString }}
$ordered = @({ordered})
$schemeValue = ($ordered | ForEach-Object {{ Join-Path $targetDir $paths[$_] }}) -join ","
$schemeKey = Join-Path $cursorKey "Schemes"
New-Item -Path $schemeKey -Force | Out-Null
Set-ItemProperty -LiteralPath $schemeKey -Name "{name}" -Value $schemeValue -Type String
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class CursorApply {{
 [DllImport("user32.dll", SetLastError=true)] public static extern bool SystemParametersInfo(uint a,uint p,IntPtr v,uint f);
 [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern IntPtr LoadCursorFromFile(string p);
 [DllImport("user32.dll", SetLastError=true)] public static extern bool SetSystemCursor(IntPtr c,uint id);
}}
"@
if (-not [CursorApply]::SystemParametersInfo(0x0057,0,[IntPtr]::Zero,0x0003)) {{ throw "Cursor refresh failed." }}
$systemIds = @{{ {ids} }}
$failed = @()
foreach ($entry in $systemIds.GetEnumerator()) {{
 $handle = [CursorApply]::LoadCursorFromFile((Join-Path $targetDir $paths[$entry.Key]))
 if ($handle -eq [IntPtr]::Zero -or -not [CursorApply]::SetSystemCursor($handle,[uint32]$entry.Value)) {{ $failed += $entry.Key }}
}}
if ($failed.Count) {{ throw "Immediate replacement failed: $($failed -join ', ')" }}
[System.Windows.Forms.MessageBox]::Show("{name} 已安装并立即启用。", "安装完成") | Out-Null
'''


def build_zip(sheet_bytes: bytes, theme_name: str) -> bytes:
    source = Image.open(BytesIO(sheet_bytes)).convert("RGBA")
    cells = split_grid(source)
    target = safe_id(theme_name)
    files: dict[str, bytes] = {}
    preview = Image.new("RGB", (5 * 210, 4 * 190), "#f1edf4")
    draw = ImageDraw.Draw(preview)
    for index, role in enumerate(ROLES):
        icon, hotspot = prepare(cells[index], role)
        files[f"{ROLE_TO_FILE[role]}.ani"] = ani_bytes(icon, hotspot)
        x, y = (index % 5) * 210, (index // 5) * 190
        draw.rectangle((x+4, y+4, x+206, y+186), fill="white", outline="#d8cddd", width=2)
        draw.text((x+12, y+10), f"{ROLE_TO_FILE[role]}. {role}", fill="#261c2b")
        preview.paste(icon, (x+41, y+40), icon)
    stream = BytesIO()
    preview.save(stream, "PNG")
    files["预览图.png"] = stream.getvalue()
    files["Install.ps1"] = installer(theme_name, target).encode("utf-8-sig")
    files["一键安装.cmd"] = (
        '@echo off\nsetlocal\npowershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; & \'%~dp0Install.ps1\'"\nif errorlevel 1 (echo Installation failed.& pause)\n'
    ).encode("utf-8")
    files["使用说明.txt"] = (
        f"{theme_name}\n\n完整解压后双击‘一键安装.cmd’。无需先安装 INF，也无需打开鼠标设置。\n"
    ).encode("utf-8-sig")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, payload in files.items():
            archive.writestr(f"{target}/{filename}", payload)
    return output.getvalue()


