---
name: image-to-windows-cursor-pack
description: Turn one uploaded character, creature, object, or themed reference image into a reusable 17-role Windows mouse cursor theme. Generate a concept sheet first; after approval, create transparent ANI files, an immediate-apply installer, and a verified ZIP package. Designed for any Agent Skills-compatible agent with image generation, local file access, and Python execution. Use for requests such as “根据图片制作鼠标指针”, “先出图”, “制作可安装光标包”, “一键更换鼠标”, “make a Windows cursor theme”, or “build ANI cursors from this image”.
---

# Image to Windows Cursor Pack

Use a strict two-stage workflow. Do not build the package before the user approves the concept sheet unless explicitly asked to skip approval.

## Portability contract

- Follow the open Agent Skills `SKILL.md` convention; do not assume a specific model, vendor, app, tool name, home directory, or Skill installation path.
- Resolve every bundled path relative to this `SKILL.md` directory.
- Use any image-generation facility exposed by the host agent. If none exists, stop after writing the concept-sheet specification and ask the user to provide a completed sheet.
- Use any local-file sharing mechanism exposed by the host agent. If files cannot be attached, return their absolute output paths.
- Require Python 3.10+ and Pillow. Prefer an existing isolated or bundled runtime; do not modify the machine-wide Python installation without permission.

## Stage 1: concept sheet

1. Inspect the reference image and identify the subject's silhouette, face, accessories, palette, and signature motifs.
2. Use the host agent's available image-generation capability to create one landscape 5-column × 4-row contact sheet.
3. Use a pure-white background. Put one complete icon in each cell. Do not add borders, numbers, titles, prose, or watermarks. Leave the final three cells blank.
4. Populate the first 17 cells left-to-right and top-to-bottom in this exact order:
   `normal`, `help`, `working`, `busy`, `precision`, `text`, `handwriting`, `unavailable`, `vertical`, `horizontal`, `diagonal1`, `diagonal2`, `move`, `alternate`, `link`, `person`, `location`.
5. Preserve subject identity across every character-bearing cursor. Use one shared pixel lattice, consistent scale, clear outlines, and recognizable functional symbols: arrow, question mark, spinner, hourglass, crosshair, I-beam, pencil, prohibited sign, resize arrows, four-way move, hand/link, person badge, and map pin.
6. Show the sheet and ask for approval. If the user requests changes, revise only the sheet. Continue only after explicit confirmation.

## Stage 2: package

1. Save the approved sheet as a local PNG and treat it as locked artwork. Do not redraw it.
2. Locate Python 3 in the host environment. If Pillow is missing, install the version declared in `requirements.txt` into a task-local environment.
3. Run from this Skill directory with `python`, `python3`, or the host's Python 3 executable:

   ```text
   python scripts/build_cursor_pack.py --sheet "<absolute-approved-sheet.png>" --name "<theme name>" --out-dir "<output directory>"
   ```

   When the host provides a bundled Python runtime, prefer that executable over a system-wide installation.
4. Inspect the generated preview. Reject and regenerate the source sheet if cells contain labels, neighboring artwork, clipped identity features, or connected artwork across cells.
5. Require all three validations to pass: `PowerShell syntax: PASS`, `Windows cursor loading: PASS`, and `ZIP integrity: PASS`.
6. Deliver the ZIP and preview using the host platform's file-sharing mechanism. Tell the user to fully extract the ZIP and double-click `一键安装.cmd`. Do not tell them to install INF first or open Mouse Settings.

## Invariants

- Support Windows only.
- Generate exactly 17 ANI files with the fixed Windows role mapping in the bundled script.
- Use 128×128 transparent RGBA cursor canvases.
- Preserve enclosed white subject areas while removing only edge-connected near-white background.
- Install beneath `%LOCALAPPDATA%` and write only current-user cursor settings under HKCU.
- Apply immediately with both `SPI_SETCURSORS` and `SetSystemCursor` to bypass Windows cursor caching.
- Never silently execute the finished installer; the user must initiate installation.
- Never use paths from the Skill author's computer.
- Never claim completion when any packaged ANI fails Windows `LoadCursorFromFileW` validation.
- Do not silently replace missing host capabilities with fabricated outputs.

