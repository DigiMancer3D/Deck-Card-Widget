#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, colorchooser
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from urllib.parse import urlparse

try:
    import qrcode
    from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageFont
    QR_AVAILABLE = True
except Exception:
    qrcode = None
    Image = None
    ImageTk = None
    ImageOps = None
    ImageDraw = None
    ImageFont = None
    QR_AVAILABLE = False

APP_NAME = "Deck Card Widget"
THEME_NAME = "Deck Card Widget Lab"
APP_VERSION = "1.3.2-de1"
BUTTSTORE_FORMAT = "3DCP-BUTTSTORE"
BUTTSTORE_ABI = "3dcp.perspective_console.buttstore.v0"

PROJECT_DIR = Path(__file__).resolve().parent

# Version folders should be disposable. Runtime state should not be.
# By default, active .buttstore files and dependency-state files live beside all version folders:
#   ~/3DCP_Perspective_Console_MVP_v0_1/_3dcp_console_user_data/
# This prevents app updates/unzips from overwriting or hiding saved episode files.
INSTALL_ROOT = PROJECT_DIR.parent

DEFAULT_USER_DATA_DIR = INSTALL_ROOT / "user_data"
LEGACY_USER_DATA_DIR = INSTALL_ROOT / "_3dcp_console_user_data"

def file_sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def merge_legacy_user_data(legacy_dir: Path, target_dir: Path) -> None:
    """Merge missing runtime files from _3dcp_console_user_data into user_data.

    Existing files in user_data are preserved. ButtStore files are hash-checked so
    exact duplicates are not copied again under migrated_N names.
    """
    if not legacy_dir.exists() or not legacy_dir.is_dir():
        return

    target_dir.mkdir(parents=True, exist_ok=True)

    existing_butt_hashes = set()
    target_buttstores = target_dir / "buttstores"
    if target_buttstores.exists():
        for path in target_buttstores.glob("*.buttstore"):
            try:
                existing_butt_hashes.add(file_sha256(path))
            except Exception:
                pass

    for item in legacy_dir.iterdir():
        dest = target_dir / item.name
        if item.name == "buttstores" and item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            for src_butt in item.glob("*.buttstore"):
                try:
                    src_hash = file_sha256(src_butt)
                except Exception:
                    continue
                if src_hash in existing_butt_hashes:
                    continue
                target = dest / src_butt.name
                if target.exists():
                    n = 1
                    while True:
                        candidate = dest / f"{src_butt.stem}_legacy_{n}{src_butt.suffix}"
                        if not candidate.exists():
                            target = candidate
                            break
                        n += 1
                shutil.copy2(src_butt, target)
                existing_butt_hashes.add(src_hash)
            continue

        if dest.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

def resolve_user_data_dir() -> Path:
    env_path = os.environ.get("DCP3_CONSOLE_USER_DATA")
    if env_path:
        return Path(env_path).expanduser()

    # v0.8.1 rename: _3dcp_console_user_data -> user_data.
    if LEGACY_USER_DATA_DIR.exists() and not DEFAULT_USER_DATA_DIR.exists():
        shutil.move(str(LEGACY_USER_DATA_DIR), str(DEFAULT_USER_DATA_DIR))
    elif LEGACY_USER_DATA_DIR.exists() and DEFAULT_USER_DATA_DIR.exists():
        merge_legacy_user_data(LEGACY_USER_DATA_DIR, DEFAULT_USER_DATA_DIR)

    return DEFAULT_USER_DATA_DIR

USER_DATA_DIR = resolve_user_data_dir()
BUTTSTORE_DIR = USER_DATA_DIR / "buttstores"
RUNTIME_DIR = USER_DATA_DIR / "runtime"
IMPORTED_PNG_DIR = USER_DATA_DIR / "imported_pngs"
DECKBUTT_DIR = USER_DATA_DIR / "deckbutts"
EXPORT_ROOT_DIR = USER_DATA_DIR / "exports"
DUPLICATE_ARCHIVE_ROOT = USER_DATA_DIR / "archived_duplicate_buttstores"

PACKAGE_DATA_DIR = PROJECT_DIR / "data"
TEMPLATE_DIR = PACKAGE_DATA_DIR / "templates"
EMOJI_PRESET_DIR = PACKAGE_DATA_DIR / "emoji_presets"
DEFAULT_TEMPLATE_PATH = TEMPLATE_DIR / "default_episode_template.buttstore"
DEFAULT_EMOJI_PRESET_PATH = EMOJI_PRESET_DIR / "default_presets.emoji"
DEFAULT_BUTTSTORE_PATH = BUTTSTORE_DIR / "default_episode.buttstore"

OUTPUT_TITLE = "Deck Card Widget - Output"
CONTROLLER_TITLE = "Deck Card Widget - Controller"

OUTPUT_WIDTH = 960
OUTPUT_HEIGHT = 500
DEFAULT_CONTROLLER_GEOMETRY = "1083x874+80+80"
DEFAULT_OUTPUT_GEOMETRY = f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}+80+80"

MAX_DECK_BUTTONS = 8
DECK_BORDER_STYLES = {
    "SPONSOR": {"color": "#ff2424", "label": "SPONSOR"},
    "PARTNER": {"color": "#2f78ff", "label": "PARTNER"},
    "DEETS": {"color": "#a34dff", "label": "DEETS"},
    "FAN": {"color": "#38b86b", "label": "FAN"},
    "SPECIAL": {"color": "#ff5ca8", "label": "SPECIAL"},
    "UNI": {"color": "#26d9e8", "label": "UNI"},
    "OBS": {"color": "#ff00ff", "label": "OBS"},
}
DECK_BORDER_WIDTH = 5

QR_GROUP_DEFAULTS = {
    # Top-left of the QR square. These values reproduce the pre-v1.2 layout.
    "x": 542,
    "y": 92,
    "size": 92,
    "foreground": "#000000",
    "background": "#ffffff",
    "outline": "#d8e2de",
    # QR label is a linked vector from the QR square's top-left point.
    "label_offset_x": 46,
    "label_offset_y": -8,
    # Default z=0 preserves the old behavior: above the base card, below stickers.
    "z": 0,
    "default_z": 0,
}

# Bitninja Dark is the original Deck Card Widget output theme. Theme roles are
# stored globally in each .buttstore and repaired additively so older data keeps
# working without replacing cards, layers, or user-authored text.
BITNINJA_DARK_THEME = {
    "output_background": {"label": "Output background", "color": "#121418", "group": "Canvas"},
    "main_panel_background": {"label": "Main console panel", "color": "#10151b", "group": "Canvas"},
    "info_panel_background": {"label": "Top rows panel", "color": "#0c1116", "group": "Canvas"},
    "blank_background": {"label": "Blank card background", "color": "#07090c", "group": "Canvas"},
    "main_border": {"label": "Main console border", "color": "#26333a", "group": "Lines"},
    "standard_line": {"label": "Standard divider line", "color": "#203037", "group": "Lines"},
    "top_row_line": {"label": "Top Rows underline", "color": "#1b2f2b", "group": "Lines"},
    "box_background": {"label": "Boxed content background", "color": "#111920", "group": "Boxes"},
    "box_border": {"label": "Boxed content border", "color": "#203037", "group": "Boxes"},
    "standard_text": {"label": "Standard text", "color": "#e8fff5", "group": "Text"},
    "secondary_text": {"label": "Secondary text", "color": "#8aa39b", "group": "Text"},
    "muted_text": {"label": "Muted text", "color": "#668078", "group": "Text"},
    "dim_text": {"label": "Dim text", "color": "#445953", "group": "Text"},
    "box_text": {"label": "Boxed content text", "color": "#f1fff9", "group": "Text"},
    "top_row_text": {"label": "Top Rows value text", "color": "#f0fff8", "group": "Text"},
    "accent": {"label": "Accent / scanner", "color": "#00ff99", "group": "Accent"},
    "scan_trail": {"label": "Scanner trail", "color": "#17362b", "group": "Accent"},
    "qr_outline": {"label": "QR outline", "color": "#d8e2de", "group": "Accent"},
}
THEME_PRESET_COLORS = {
    "Bitninja Green": "#00ff99",
    "Main Charcoal": "#121418",
    "Panel Charcoal": "#10151b",
    "Standard Text": "#e8fff5",
    "Secondary Text": "#8aa39b",
    "Standard Line": "#203037",
    "Top Row Line": "#1b2f2b",
    "Top Row Text": "#f0fff8",
    "Scanner Trail": "#17362b",
    "White": "#ffffff",
    "Black": "#000000",
    "Sponsor Red": "#ff2424",
    "Partner Blue": "#2f78ff",
    "Deets Purple": "#a34dff",
    "Fan Green": "#38b86b",
    "Special Pink": "#ff5ca8",
    "Uni Cyan": "#26d9e8",
    "OBS Magenta": "#ff00ff",
}
# Boxed-content geometry is derived from the real output region instead of a
# historical fixed 830 px ceiling. Decorative/sticker/image/text layers are
# intentionally ignored: they may cover content for live reveals, but they do
# not reduce the boxed content region itself.
BOX_WRAP_MIN = 120
BOX_WRAP_LEGACY_MAX = 830
BOX_WRAP_MODEL = "output-region-v2-canvas-native"
BOXED_CONTENT_TEXT_LEFT_PAD = 14
BOXED_CONTENT_TEXT_RIGHT_PAD = 12
BOXED_CONTENT_LAYOUTS = {
    "claim": {"x": 52, "y": 232, "height": 62, "right_margin": 24, "label_id": "box_claim_label", "field": "claim"},
    "evidence": {"x": 52, "y": 322, "height": 62, "right_margin": 24, "label_id": "box_evidence_label", "field": "evidence"},
    "openQuestion": {"x": 52, "y": 412, "height": 58, "right_margin": 24, "label_id": "box_question_label", "field": "openQuestion"},
}

def boxed_content_geometry(key: str) -> dict:
    base = BOXED_CONTENT_LAYOUTS[key]
    x = int(base["x"])
    right_x = OUTPUT_WIDTH - int(base["right_margin"])
    width = max(1, right_x - x)
    return {**base, "x": x, "right_x": right_x, "width": width}

def boxed_content_wrap_limit(key: str) -> int:
    geometry = boxed_content_geometry(key)
    text_start_x = geometry["x"] + BOXED_CONTENT_TEXT_LEFT_PAD
    text_end_x = geometry["right_x"] - BOXED_CONTENT_TEXT_RIGHT_PAD
    return max(BOX_WRAP_MIN, text_end_x - text_start_x)

def normalize_box_wrap_width(key: str, value) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = boxed_content_wrap_limit(key)
    return max(BOX_WRAP_MIN, min(boxed_content_wrap_limit(key), numeric))

BOX_WRAP_MAXES = {key: boxed_content_wrap_limit(key) for key in BOXED_CONTENT_LAYOUTS}
BOX_WRAP_DEFAULTS = copy.deepcopy(BOX_WRAP_MAXES)

RESOURCE_PROFILES = {
    "low": {"label": "Low resources", "scan_ms": 67, "max_scan_fps": 15, "autosave_delay_ms": 1500},
    "normal": {"label": "Normal resources", "scan_ms": 42, "max_scan_fps": 24, "autosave_delay_ms": 1000},
    "full": {"label": "Full performance", "scan_ms": 33, "max_scan_fps": 30, "autosave_delay_ms": 600},
}
SOURCE_TYPES = ["Official", "Primary", "Secondary", "Unknown"]
CONFIDENCE_LEVELS = ["High", "Medium", "Low", "Still Checking"]
VERDICTS = ["Supported", "Partial", "Unsupported", "Needs Proof", "Still Checking"]

FALLBACK_EMOJI_PRESETS = [
    {"emoji": "✅", "name": "Check", "category": "Status"},
    {"emoji": "❌", "name": "Cross", "category": "Status"},
    {"emoji": "✨", "name": "Sparkles", "category": "Lab"},
    {"emoji": "🔥", "name": "Fire", "category": "Lab"},
    {"emoji": "🔍", "name": "Magnifier", "category": "Lab"},
    {"emoji": "👀", "name": "Eyes", "category": "People"},
    {"emoji": "💀", "name": "Skull", "category": "People"},
    {"emoji": "🫠", "name": "Melting Face", "category": "People"},
    {"emoji": "📍", "name": "Pin", "category": "Places"},
    {"emoji": "👉", "name": "Point Right", "category": "Arrows"},
    {"emoji": "👇", "name": "Point Down", "category": "Arrows"},
    {"emoji": "➡️", "name": "Arrow Right", "category": "Arrows"},
    {"emoji": "⬇️", "name": "Arrow Down", "category": "Arrows"},
    {"emoji": "⬅️", "name": "Arrow Left", "category": "Arrows"},
    {"emoji": "🔜", "name": "Soon", "category": "Arrows"},
    {"emoji": "🔙", "name": "Back", "category": "Arrows"},
    {"emoji": "🔚", "name": "End", "category": "Arrows"},
    {"emoji": "💚", "name": "Green Heart", "category": "Shapes"},
    {"emoji": "🟢", "name": "Green Circle", "category": "Shapes"},
    {"emoji": "🟩", "name": "Green Square", "category": "Shapes"},
    {"emoji": "9️⃣", "name": "Number Nine", "category": "Numbers"},
    {"emoji": "📱", "name": "Phone", "category": "Objects"},
    {"emoji": "☢️", "name": "Radioactive", "category": "Symbols"},
    {"emoji": "🔗", "name": "Link", "category": "Objects"},
    {"emoji": "⛓️", "name": "Chains", "category": "Objects"},
    {"emoji": "🧠", "name": "Brain", "category": "Lab"},
    {"emoji": "🧪", "name": "Test Tube", "category": "Lab"},
    {"emoji": "🧾", "name": "Receipt", "category": "Objects"},
    {"emoji": "🛰️", "name": "Satellite", "category": "Objects"},
    {"emoji": "📊", "name": "Chart", "category": "Objects"},
    {"emoji": "📈", "name": "Up Chart", "category": "Objects"},
    {"emoji": "📉", "name": "Down Chart", "category": "Objects"},
    {"emoji": "₿", "name": "Bitcoin", "category": "Crypto"},
    {"emoji": "🪙", "name": "Coin", "category": "Crypto"},
    {"emoji": "🔒", "name": "Lock", "category": "Crypto"},
    {"emoji": "🔓", "name": "Unlock", "category": "Crypto"},
    {"emoji": "🐂", "name": "Bull", "category": "Animals"},
    {"emoji": "🐻", "name": "Bear", "category": "Animals"},
    {"emoji": "🌍", "name": "Globe", "category": "Places"},
    {"emoji": "🏛️", "name": "Bank", "category": "Places"},
    {"emoji": "🍞", "name": "Bread", "category": "Food"},
    {"emoji": "🍕", "name": "Pizza", "category": "Food"},
    {"emoji": "☕", "name": "Coffee", "category": "Food"},
]

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def safe_read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def safe_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    temp_path.replace(path)


def load_emoji_presets_from_file(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    items: list[dict] = []
    for record in raw.split("/,"):
        record = record.strip()
        if not record:
            continue
        parts = [part.strip() for part in record.split("|")]
        emoji = parts[0] if len(parts) >= 1 else ""
        name = parts[1] if len(parts) >= 2 and parts[1] else f"Emoji {len(items) + 1}"
        category = parts[2] if len(parts) >= 3 and parts[2] else "General"
        if emoji:
            items.append({"emoji": emoji, "name": name[:32], "category": category[:24]})
    return items

def normalize_hex_color(value: str, fallback: str = "#e8fff5") -> str:
    value = (value or "").strip()
    if re.match(r"^#[0-9a-fA-F]{6}$", value):
        return value.lower()
    return fallback.lower()

def blend_hex_colors(fg_hex: str, bg_hex: str, opacity: float) -> str:
    fg_hex = normalize_hex_color(fg_hex, "#e8fff5")
    bg_hex = normalize_hex_color(bg_hex, "#121418")
    opacity = max(0.0, min(1.0, float(opacity)))

    def parts(h: str) -> tuple[int, int, int]:
        return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)

    fr, fg, fb = parts(fg_hex)
    br, bg, bb = parts(bg_hex)
    r = int((fr * opacity) + (br * (1.0 - opacity)))
    g = int((fg * opacity) + (bg * (1.0 - opacity)))
    b = int((fb * opacity) + (bb * (1.0 - opacity)))
    return f"#{r:02x}{g:02x}{b:02x}"

def new_card(card_type: str = "source_analyzer", label: str = "Widget Card") -> dict:
    if card_type == "blank":
        return {"id": "blank-hide", "label": "Blank / Hide", "type": "blank", "fields": {}, "layers": [], "deck_border_type": "", "box_wrap_widths": copy.deepcopy(BOX_WRAP_DEFAULTS), "box_wrap_model": BOX_WRAP_MODEL}
    return {
        "id": "source-analyzer",
        "label": label,
        "type": "source_analyzer",
        "deck_border_type": "",
        "box_wrap_widths": copy.deepcopy(BOX_WRAP_DEFAULTS),
        "box_wrap_model": BOX_WRAP_MODEL,
        "fields": {
            "sourceType": "Primary",
            "confidence": "Medium",
            "sourceLink": "",
            "claim": "Current claim goes here.",
            "evidence": "Evidence shown on browser or cited source.",
            "openQuestion": "What still needs checking?",
            "verdict": "Still Checking",
        },
        "layers": [
            {"id": "emoji-default-scan", "type": "emoji", "name": "Scan Magnifier", "text": "🔍", "x": 900, "y": 210, "size": 26, "opacity": 1.0, "z": 10}
        ],
    }


DISPLAY_TEXT_DEFAULTS = [
    {
        "id": "title_main",
        "label": "Top Title",
        "text": "DECK CARD WIDGET",
        "old_text": "3DCP SOURCE ANALYZER",
        "x": 34,
        "y": 38,
        "anchor": "w",
        "color": "#e8fff5",
        "font_family": "TkDefaultFont",
        "font_size": 19,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#26333a",
        "visible": True,
        "notes": "Old private default: 3DCP SOURCE ANALYZER",
    },
    {
        "id": "status_live",
        "label": "Status Live",
        "text": "STATUS: LIVE",
        "old_text": "STATUS: LIVE",
        "x": 922,
        "y": 38,
        "anchor": "e",
        "color": "#00ff99",
        "font_family": "TkDefaultFont",
        "font_size": 12,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#00ff99",
        "visible": True,
        "notes": "Previously used the scanner/accent color.",
    },
    {
        "id": "row_source_type",
        "label": "Row Label - Source Type",
        "text": "CARD TYPE",
        "old_text": "SOURCE TYPE:",
        "x": 52,
        "y": 96,
        "anchor": "w",
        "color": "#8aa39b",
        "font_family": "TkDefaultFont",
        "font_size": 12,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#8aa39b",
        "visible": True,
    },
    {
        "id": "row_confidence",
        "label": "Row Label - Confidence",
        "text": "CONFIDENCE",
        "old_text": "CONFIDENCE:",
        "x": 52,
        "y": 128,
        "anchor": "w",
        "color": "#8aa39b",
        "font_family": "TkDefaultFont",
        "font_size": 12,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#8aa39b",
        "visible": True,
    },
    {
        "id": "row_verdict",
        "label": "Row Label - Verdict",
        "text": "STATUS",
        "old_text": "VERDICT:",
        "x": 52,
        "y": 160,
        "anchor": "w",
        "color": "#8aa39b",
        "font_family": "TkDefaultFont",
        "font_size": 12,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#8aa39b",
        "visible": True,
    },
    {
        "id": "qr_label",
        "label": "QR Label",
        "text": "LINK QR",
        "old_text": "SOURCE QR",
        "x": 0,
        "y": 84,
        "anchor": "center",
        "color": "#8aa39b",
        "font_family": "TkDefaultFont",
        "font_size": 10,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#8aa39b",
        "visible": True,
        "notes": "X is computed from the QR column when a link exists; saved X is a fallback.",
    },
    {
        "id": "right_brand",
        "label": "Right Brand",
        "text": "DECK CARD WIDGET",
        "old_text": "THE PERSPECTIVE LAB",
        "x": 898,
        "y": 106,
        "anchor": "e",
        "color": "#668078",
        "font_family": "TkDefaultFont",
        "font_size": 10,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#668078",
        "visible": True,
    },
    {
        "id": "right_subtitle",
        "label": "Right Subtitle",
        "text": "STREAM CARD CONSOLE",
        "old_text": "PROOF ANALYSIS CONSOLE",
        "x": 898,
        "y": 126,
        "anchor": "e",
        "color": "#445953",
        "font_family": "TkDefaultFont",
        "font_size": 10,
        "font_weight": "normal",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#445953",
        "visible": True,
    },
    {
        "id": "activity_label",
        "label": "Activity Label",
        "text": "ACTIVITY: LINK READY",
        "old_text": "ACTIVITY: LINK READY",
        "x": 898,
        "y": 154,
        "anchor": "e",
        "color": "#00ff99",
        "font_family": "TkDefaultFont",
        "font_size": 10,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#00ff99",
        "visible": True,
        "notes": "Only shown when the active card has a source/link URL.",
    },
    {
        "id": "host_label",
        "label": "QR Location",
        "text": "QR LOC: {host}",
        "old_text": "HOST: {host}",
        "x": 898,
        "y": 172,
        "anchor": "e",
        "color": "#8aa39b",
        "font_family": "TkDefaultFont",
        "font_size": 9,
        "font_weight": "normal",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#8aa39b",
        "visible": True,
        "notes": "Use {host} to insert the domain parsed from the card link.",
    },
    {
        "id": "box_claim_label",
        "label": "Box Label #1",
        "text": "CARD CLAIM:",
        "old_text": "CURRENT CLAIM:",
        "x": 52,
        "y": 216,
        "anchor": "w",
        "color": "#8aa39b",
        "font_family": "TkDefaultFont",
        "font_size": 11,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#8aa39b",
        "visible": True,
    },
    {
        "id": "box_evidence_label",
        "label": "Box Label #2",
        "text": "CARD EVIDENCE:",
        "old_text": "EVIDENCE SHOWN:",
        "x": 52,
        "y": 306,
        "anchor": "w",
        "color": "#8aa39b",
        "font_family": "TkDefaultFont",
        "font_size": 11,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#8aa39b",
        "visible": True,
    },
    {
        "id": "box_question_label",
        "label": "Box Label #3",
        "text": "OPEN QUESTION:",
        "old_text": "OPEN QUESTION:",
        "x": 52,
        "y": 396,
        "anchor": "w",
        "color": "#8aa39b",
        "font_family": "TkDefaultFont",
        "font_size": 11,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#8aa39b",
        "visible": True,
    },
    {
        "id": "scan_label",
        "label": "Scanner Label",
        "text": "ANALYZING...",
        "old_text": "ANALYZING...",
        "x": 835,
        "y": 210,
        "anchor": "center",
        "color": "#00ff99",
        "font_family": "TkDefaultFont",
        "font_size": 10,
        "font_weight": "bold",
        "font_slant": "roman",
        "border_enabled": False,
        "border_color": "#00ff99",
        "visible": True,
        "notes": "Only drawn while the scan animation is visible.",
    },
]

DISPLAY_TEXT_DEFAULTS_BY_ID = {item["id"]: item for item in DISPLAY_TEXT_DEFAULTS}


TOP_ROW_DEFAULTS = [
    {
        "id": "sourceType",
        "label": "Row 1 - CARD TYPE",
        "field": "sourceType",
        "display_label_id": "row_source_type",
        "default_value": "Primary",
        "default_option_label": "CARD TYPE",
        "value_x": 200,
        "value_y": 96,
        "line_color": "#1b2f2b",
        "options": SOURCE_TYPES,
    },
    {
        "id": "confidence",
        "label": "Row 2 - CONFIDENCE",
        "field": "confidence",
        "display_label_id": "row_confidence",
        "default_value": "Medium",
        "default_option_label": "CONFIDENCE",
        "value_x": 200,
        "value_y": 128,
        "line_color": "#1b2f2b",
        "options": CONFIDENCE_LEVELS,
    },
    {
        "id": "verdict",
        "label": "Row 3 - STATUS",
        "field": "verdict",
        "display_label_id": "row_verdict",
        "default_value": "Still Checking",
        "default_option_label": "STATUS",
        "value_x": 200,
        "value_y": 160,
        "line_color": "#1b2f2b",
        "options": VERDICTS,
    },
]
TOP_ROW_DEFAULTS_BY_ID = {item["id"]: item for item in TOP_ROW_DEFAULTS}
TOP_ROW_FIELD_TO_ID = {item["field"]: item["id"] for item in TOP_ROW_DEFAULTS}
TOP_ROW_LABEL_TO_ID = {item["display_label_id"]: item["id"] for item in TOP_ROW_DEFAULTS}


def top_row_option_id(text: str, prefix: str = "option") -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", (text or "option").strip().lower()).strip("-") or "option"
    return f"{prefix}-{base[:36]}"


def make_top_row_option(row_default: dict, text: str, index: int = 0) -> dict:
    text = (text or "Option").strip() or "Option"
    row_id = str(row_default.get("id", "row"))
    return {
        "id": top_row_option_id(text, row_id),
        "text": text,
        "x": int(row_default.get("value_x", 200)),
        "y": int(row_default.get("value_y", 96)),
        "color": "#f0fff8",
        "bar_color": "#00ff99",
        "font_family": "TkDefaultFont",
        "font_size": 15,
        "font_weight": "bold",
        "font_slant": "roman",
        "visible": True,
        "default_text": text,
        "default_color": "#f0fff8",
        "default_bar_color": "#00ff99",
        "default_font_size": 15,
        "created_from_default_index": index,
    }


def default_top_rows() -> list[dict]:
    rows = []
    for row_default in TOP_ROW_DEFAULTS:
        row = copy.deepcopy(row_default)
        options = [make_top_row_option(row_default, text, idx) for idx, text in enumerate(row_default.get("options", []))]
        row["options"] = options
        row["default_options"] = [copy.deepcopy(option) for option in options]
        rows.append(row)
    return rows


def ensure_top_row_storage(data: dict) -> list[dict]:
    """Repair editable dropdown option storage without touching user cards.

    The Top Rows tab edits the option sets for the three top output rows. Older
    .buttstore files only stored card field values, so this function creates the
    missing global option records and preserves any custom values already present.
    """
    header = data.setdefault("header", {})
    stored = header.setdefault("top_rows", [])
    if not isinstance(stored, list):
        stored = []
        header["top_rows"] = stored

    stored_by_id = {str(row.get("id", "")): row for row in stored if isinstance(row, dict)}
    repaired = []
    for default_row in default_top_rows():
        existing = stored_by_id.get(default_row["id"])
        if not existing:
            repaired.append(default_row)
            continue

        merged = copy.deepcopy(default_row)
        # Preserve user-level row settings except immutable identity plumbing.
        for key, value in existing.items():
            if key in {"id", "field", "display_label_id", "default_options"}:
                continue
            if key == "options":
                continue
            merged[key] = value

        existing_options = existing.get("options", [])
        if not isinstance(existing_options, list):
            existing_options = []
        normalized_options = []
        seen_ids = set()
        for idx, opt in enumerate(existing_options):
            if not isinstance(opt, dict):
                continue
            text = str(opt.get("text", "")).strip()
            if not text:
                continue
            fallback = make_top_row_option(default_row, text, idx)
            fixed = copy.deepcopy(fallback)
            for key, value in opt.items():
                if key == "id":
                    continue
                fixed[key] = value
            fixed["id"] = str(opt.get("id") or top_row_option_id(text, default_row["id"]))
            base_id = fixed["id"]
            counter = 2
            while fixed["id"] in seen_ids:
                fixed["id"] = f"{base_id}-{counter}"
                counter += 1
            fixed["color"] = normalize_hex_color(str(fixed.get("color", "#f0fff8")), "#f0fff8")
            fixed["bar_color"] = normalize_hex_color(str(fixed.get("bar_color", "#00ff99")), "#00ff99")
            fixed["font_size"] = max(6, min(96, int(fixed.get("font_size", 15))))
            fixed["visible"] = bool(fixed.get("visible", True))
            normalized_options.append(fixed)
            seen_ids.add(fixed["id"])

        # Bring in any newly-added baseline defaults, but do not duplicate text values.
        known_text = {str(opt.get("text", "")).strip().casefold() for opt in normalized_options}
        for default_option in default_row.get("default_options", []):
            text_key = str(default_option.get("text", "")).strip().casefold()
            if text_key and text_key not in known_text:
                normalized_options.append(copy.deepcopy(default_option))
                known_text.add(text_key)

        if not normalized_options:
            normalized_options = [make_top_row_option(default_row, str(default_row.get("default_value", "Option")), 0)]
        merged["options"] = normalized_options
        repaired.append(merged)

    header["top_rows"] = repaired
    return repaired


def default_display_text_objects() -> list[dict]:
    objects = []
    for item in DISPLAY_TEXT_DEFAULTS:
        obj = copy.deepcopy(item)
        obj.setdefault("default_text", obj.get("text", ""))
        obj.setdefault("default_color", obj.get("color", "#e8fff5"))
        obj.setdefault("default_border_color", obj.get("border_color", obj.get("color", "#e8fff5")))
        obj.setdefault("default_font_family", obj.get("font_family", "TkDefaultFont"))
        obj.setdefault("default_font_size", obj.get("font_size", 12))
        obj.setdefault("default_font_weight", obj.get("font_weight", "normal"))
        obj.setdefault("default_font_slant", obj.get("font_slant", "roman"))
        objects.append(obj)
    return objects


def ensure_display_text_storage(data: dict) -> list[dict]:
    header = data.setdefault("header", {})
    stored = header.setdefault("display_text", [])
    if not isinstance(stored, list):
        stored = []
        header["display_text"] = stored

    by_id = {str(obj.get("id", "")): obj for obj in stored if isinstance(obj, dict)}
    repaired = []
    for default in default_display_text_objects():
        existing = by_id.get(default["id"])
        if existing is None:
            repaired.append(default)
            continue
        merged = copy.deepcopy(default)
        for key, value in existing.items():
            if key in {"id", "label", "old_text", "notes", "default_text", "default_color", "default_border_color", "default_font_family", "default_font_size", "default_font_weight", "default_font_slant"}:
                continue
            merged[key] = value
        # Keep defaults fresh for new public baseline while preserving user edits above.
        repaired.append(merged)
    # v1.3 naming migration: preserve genuine custom text, but upgrade the
    # untouched historical HOST template to the requested QR LOC wording.
    for obj in repaired:
        if obj.get("id") == "host_label" and str(obj.get("text", "")).strip() == "HOST: {host}":
            obj["text"] = "QR LOC: {host}"
    header["display_text"] = repaired
    return repaired


def default_theme_colors() -> dict:
    return {role: spec["color"] for role, spec in BITNINJA_DARK_THEME.items()}


def ensure_theme_color_storage(data: dict) -> dict:
    header = data.setdefault("header", {})
    stored = header.get("theme_colors")
    repaired = default_theme_colors()
    if isinstance(stored, dict):
        for role, value in stored.items():
            if role in repaired:
                repaired[role] = normalize_hex_color(str(value), repaired[role])
    # The output background predates theme storage; keep a genuinely customized
    # value during first migration instead of replacing it with the default.
    output = header.setdefault("output", {"width": OUTPUT_WIDTH, "height": OUTPUT_HEIGHT, "background": "#121418", "title": OUTPUT_TITLE})
    if not isinstance(stored, dict):
        repaired["output_background"] = normalize_hex_color(str(output.get("background", repaired["output_background"])), repaired["output_background"])
    output["background"] = repaired["output_background"]
    header["theme_colors"] = repaired
    return repaired


def ensure_box_wrap_storage(card: dict) -> dict:
    stored = card.get("box_wrap_widths")
    prior_model = str(card.get("box_wrap_model", ""))
    repaired = copy.deepcopy(BOX_WRAP_DEFAULTS)
    if isinstance(stored, dict):
        for key in repaired:
            raw_value = stored.get(key, repaired[key])
            try:
                numeric = int(raw_value)
            except (TypeError, ValueError):
                numeric = repaired[key]
            # v1.3.1 migration: 830 represented "use all available room" in
            # the old fixed-ceiling model. Carry that intent forward to the
            # new geometry-derived maximum; preserve every narrower custom value.
            if prior_model != BOX_WRAP_MODEL and numeric == BOX_WRAP_LEGACY_MAX:
                numeric = boxed_content_wrap_limit(key)
            repaired[key] = normalize_box_wrap_width(key, numeric)
    card["box_wrap_widths"] = repaired
    card["box_wrap_model"] = BOX_WRAP_MODEL
    return repaired


def ensure_qr_group_storage(data: dict) -> dict:
    """Create/repair global QR layout settings without replacing user card data."""
    header = data.setdefault("header", {})
    existing = header.get("qr_group")
    first_migration = not isinstance(existing, dict)
    merged = copy.deepcopy(QR_GROUP_DEFAULTS)
    if isinstance(existing, dict):
        merged.update(existing)

    try:
        size = max(48, min(260, int(merged.get("size", QR_GROUP_DEFAULTS["size"]))))
    except (TypeError, ValueError):
        size = QR_GROUP_DEFAULTS["size"]
    try:
        x = max(0, min(OUTPUT_WIDTH - size, int(merged.get("x", QR_GROUP_DEFAULTS["x"]))))
        y = max(0, min(OUTPUT_HEIGHT - size, int(merged.get("y", QR_GROUP_DEFAULTS["y"]))))
    except (TypeError, ValueError):
        x, y = QR_GROUP_DEFAULTS["x"], QR_GROUP_DEFAULTS["y"]
    try:
        z = max(-1000, min(1000, int(merged.get("z", QR_GROUP_DEFAULTS["z"]))))
    except (TypeError, ValueError):
        z = QR_GROUP_DEFAULTS["z"]
    try:
        default_z = max(-1000, min(1000, int(merged.get("default_z", QR_GROUP_DEFAULTS["default_z"]))))
    except (TypeError, ValueError):
        default_z = QR_GROUP_DEFAULTS["default_z"]

    merged.update({
        "x": x,
        "y": y,
        "size": size,
        "z": z,
        "default_z": default_z,
        "foreground": normalize_hex_color(str(merged.get("foreground", "#000000")), "#000000"),
        "background": normalize_hex_color(str(merged.get("background", "#ffffff")), "#ffffff"),
        "outline": normalize_hex_color(str(merged.get("outline", "#d8e2de")), "#d8e2de"),
    })

    # Existing v1.1 QR-label X was a fallback (normally 0) because render-time code
    # overrode it. Honor a genuinely edited X/Y during first migration; otherwise
    # reconstruct the historical centered-above-QR vector.
    label_obj = None
    for obj in header.get("display_text", []):
        if isinstance(obj, dict) and obj.get("id") == "qr_label":
            label_obj = obj
            break
    if first_migration and label_obj is not None:
        try:
            old_x = int(label_obj.get("x", 0))
            old_y = int(label_obj.get("y", 84))
        except (TypeError, ValueError):
            old_x, old_y = 0, 84
        if old_x != 0:
            merged["label_offset_x"] = old_x - x
            merged["label_offset_y"] = old_y - y

    try:
        merged["label_offset_x"] = max(-OUTPUT_WIDTH, min(OUTPUT_WIDTH, int(merged.get("label_offset_x", QR_GROUP_DEFAULTS["label_offset_x"]))))
        merged["label_offset_y"] = max(-OUTPUT_HEIGHT, min(OUTPUT_HEIGHT, int(merged.get("label_offset_y", QR_GROUP_DEFAULTS["label_offset_y"]))))
    except (TypeError, ValueError):
        merged["label_offset_x"] = QR_GROUP_DEFAULTS["label_offset_x"]
        merged["label_offset_y"] = QR_GROUP_DEFAULTS["label_offset_y"]

    header["qr_group"] = merged
    if label_obj is not None:
        label_obj["x"] = x + int(merged["label_offset_x"])
        label_obj["y"] = y + int(merged["label_offset_y"])
        label_obj["notes"] = "Position is linked to header.qr_group through label_offset_x/label_offset_y."
    return merged


def normalize_deck_border_type(value: str) -> str:
    value = str(value or "").strip().upper()
    return value if value in DECK_BORDER_STYLES else ""


def make_default_buttstore(preserve_footer: dict | None = None) -> dict:
    now = utc_now()
    footer = {
        "serial": 1, "high_water_serial": 1, "save_count": 0, "created_serial": 1,
        "last_wipe_serial": 0, "public_clean_ready": False, "history": [],
        "notes": "Footer values are forward-only unless the user performs a to-default wipe.",
    }
    if preserve_footer:
        previous_high = int(preserve_footer.get("high_water_serial", 1))
        previous_save_count = int(preserve_footer.get("save_count", 0))
        previous_history = list(preserve_footer.get("history", []))[-20:]
        footer.update({
            "serial": previous_high + 1,
            "high_water_serial": previous_high + 1,
            "save_count": previous_save_count,
            "created_serial": preserve_footer.get("created_serial", 1),
            "last_wipe_serial": previous_high + 1,
            "history": previous_history,
        })
    cards = [new_card(), new_card("blank", "Blank / Hide")]
    return {
        "buttstore_format": BUTTSTORE_FORMAT,
        "version": APP_VERSION,
        "header": {
            "magic": "3DCP_BUTTSTORE", "abi": BUTTSTORE_ABI, "project": APP_NAME, "theme": THEME_NAME,
            "created_at": now, "modified_at": now, "active_card_id": "source-analyzer",
            "resource_profile": "low",
            "output": {"width": OUTPUT_WIDTH, "height": OUTPUT_HEIGHT, "background": "#121418", "title": OUTPUT_TITLE},
            "display_text": default_display_text_objects(),
            "top_rows": default_top_rows(),
            "qr_group": copy.deepcopy(QR_GROUP_DEFAULTS),
            "theme_colors": default_theme_colors(),
            "quick_cards": [{"id": c["id"], "label": c["label"], "type": c["type"]} for c in cards],
        },
        "under_header": {
            "dirty": False, "output_visible": True, "output_topmost": False, "output_borderless": False,
            "controller_geometry": DEFAULT_CONTROLLER_GEOMETRY,
            "output_geometry": DEFAULT_OUTPUT_GEOMETRY,
            "scan_loop": False, "scan_speed_ms": 67, "scanner_color": "#00ff99",
            "last_loaded_path": str(DEFAULT_BUTTSTORE_PATH), "last_runtime_event": "default-created",
            "scratch": {"selected_layer_id": None, "unsaved_note": ""},
        },
        "stage": {"abi_style": "draft values live here before they are applied into body/cards", "draft_cards": {}, "save_body_pending": False},
        "body": {"cards": cards},
        "footer": footer,
    }

def is_safe_geometry(geometry: str, min_w: int = 320, min_h: int = 200) -> bool:
    """Basic guard against invisible/off-screen saved geometry.

    Tk geometry examples:
      960x500+80+80
      960x500-32000+40
    """
    if not geometry or not isinstance(geometry, str):
        return False

    import re
    m = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry.strip())
    if not m:
        return False

    width = int(m.group(1))
    height = int(m.group(2))
    x = int(m.group(3))
    y = int(m.group(4))

    if width < min_w or height < min_h:
        return False

    # Multi-monitor safe guard: allow reasonable negative X, but reject huge phantom coordinates.
    if x < -5000 or x > 10000 or y < -1000 or y > 5000:
        return False

    return True


def repair_runtime_visibility(data: dict) -> bool:
    """Repair output visibility/geometry without deleting user card content.

    Returns True if changes were made.
    """
    changed = False
    under = data.setdefault("under_header", {})

    if under.get("output_visible") is not True:
        under["output_visible"] = True
        changed = True

    output_geo = under.get("output_geometry", "")
    if not is_safe_geometry(output_geo, 320, 200):
        under["output_geometry"] = DEFAULT_OUTPUT_GEOMETRY
        changed = True

    controller_geo = under.get("controller_geometry", "")
    if under.get("controller_geometry_migrated_v082") is not True:
        under["controller_geometry"] = DEFAULT_CONTROLLER_GEOMETRY
        under["controller_geometry_migrated_v082"] = True
        changed = True
    elif controller_geo and not is_safe_geometry(controller_geo, 320, 200):
        under["controller_geometry"] = DEFAULT_CONTROLLER_GEOMETRY
        changed = True

    if under.get("scan_loop") is True:
        under["scan_loop"] = False
        changed = True

    if changed:
        under["last_runtime_event"] = "auto-visibility-geometry-repair"

    return changed


def discover_legacy_buttstores() -> list[Path]:
    """Find .buttstore files saved inside older version folders.

    This is read-only discovery. It never deletes or modifies legacy files.
    """
    candidates: list[Path] = []
    search_roots = [INSTALL_ROOT, PROJECT_DIR]
    seen: set[Path] = set()

    for root in search_roots:
        if not root.exists():
            continue
        for path in root.glob("**/*.buttstore"):
            try:
                resolved = path.resolve()
            except Exception:
                resolved = path
            if resolved in seen:
                continue
            seen.add(resolved)

            # Skip files already in shared user data and package templates.
            # Also skip templates from older version folders; those are package defaults, not user saves.
            if USER_DATA_DIR in path.parents:
                continue
            if TEMPLATE_DIR in path.parents:
                continue
            if path.name.endswith(".tmp"):
                continue
            if "template" in path.name.lower():
                continue
            if any(part.lower() == "templates" for part in path.parts):
                continue
            candidates.append(path)

    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return candidates


def migrate_legacy_buttstores() -> list[Path]:
    """Conservative no-op migration inside the app.

    Older builds copied .buttstore files from every old version folder, which could
    re-create duplicates after the user had cleaned them up. v0.8.3 keeps app launch
    safe and non-copying. The standalone migration script only merges the old shared
    data folder and no longer imports old version-folder .buttstore files by default.
    """
    BUTTSTORE_DIR.mkdir(parents=True, exist_ok=True)
    return []


def ensure_default_buttstore_exists() -> None:
    """Create the shared default .buttstore only if missing.

    Priority:
    1. If old version folders contain default_episode.buttstore, migrate/copy the newest one.
    2. Else use the package template.
    3. Else generate a default from code.

    Existing shared .buttstore files are never replaced here.
    """
    BUTTSTORE_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    IMPORTED_PNG_DIR.mkdir(parents=True, exist_ok=True)
    DECKBUTT_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_ROOT_DIR.mkdir(parents=True, exist_ok=True)

    copied = migrate_legacy_buttstores()

    if DEFAULT_BUTTSTORE_PATH.exists():
        data = safe_read_json(DEFAULT_BUTTSTORE_PATH)
        ButtStore.validate_or_repair(data)
        if repair_runtime_visibility(data):
            safe_write_json(DEFAULT_BUTTSTORE_PATH, data)
        return

    # Prefer a migrated old default_episode.buttstore if one exists.
    migrated_defaults = [p for p in copied if p.name == "default_episode.buttstore"]
    if migrated_defaults:
        newest = max(migrated_defaults, key=lambda p: p.stat().st_mtime if p.exists() else 0)
        if newest != DEFAULT_BUTTSTORE_PATH:
            shutil.copy2(newest, DEFAULT_BUTTSTORE_PATH)
        return

    # If migration copied only custom names, leave them intact and create a runtime default.
    if DEFAULT_TEMPLATE_PATH.exists():
        data = safe_read_json(DEFAULT_TEMPLATE_PATH)
        ButtStore.validate_or_repair(data)
        data["under_header"]["last_runtime_event"] = "created-from-template-shared-user-data"
        repair_runtime_visibility(data)
        safe_write_json(DEFAULT_BUTTSTORE_PATH, data)
        return

    safe_write_json(DEFAULT_BUTTSTORE_PATH, make_default_buttstore())



@dataclass
class ButtStore:
    path: Path
    data: dict

    @classmethod
    def load_or_create(cls, path: Path) -> "ButtStore":
        path.parent.mkdir(parents=True, exist_ok=True)

        # Safety rule:
        # Loading or updating the app must never delete, wipe, or overwrite an existing .buttstore.
        if path == DEFAULT_BUTTSTORE_PATH:
            ensure_default_buttstore_exists()

        if not path.exists():
            data = make_default_buttstore()
            safe_write_json(path, data)
            return cls(path=path, data=data)

        data = safe_read_json(path)
        cls.validate_or_repair(data)
        if path == DEFAULT_BUTTSTORE_PATH and repair_runtime_visibility(data):
            safe_write_json(path, data)
        return cls(path=path, data=data)

    @staticmethod
    def validate_or_repair(data: dict) -> None:
        changed = False
        if data.get("buttstore_format") != BUTTSTORE_FORMAT:
            raise ValueError("This file is not a 3DCP .buttstore file.")
        data.setdefault("version", APP_VERSION)
        data.setdefault("header", {})
        data.setdefault("under_header", {})
        data.setdefault("stage", {})
        data.setdefault("body", {})
        data.setdefault("footer", {})
        header = data["header"]
        header.setdefault("magic", "3DCP_BUTTSTORE")
        header.setdefault("abi", BUTTSTORE_ABI)
        header.setdefault("project", APP_NAME)
        header.setdefault("theme", THEME_NAME)
        header.setdefault("created_at", utc_now())
        header.setdefault("modified_at", utc_now())
        header.setdefault("active_card_id", "source-analyzer")
        header.setdefault("resource_profile", "low")
        header.setdefault("output", {"width": OUTPUT_WIDTH, "height": OUTPUT_HEIGHT, "background": "#121418", "title": OUTPUT_TITLE})
        ensure_display_text_storage(data)
        ensure_top_row_storage(data)
        ensure_qr_group_storage(data)
        ensure_theme_color_storage(data)
        under = data["under_header"]
        under.setdefault("dirty", False)
        under.setdefault("output_visible", True)
        under.setdefault("output_topmost", False)
        under.setdefault("output_borderless", False)
        # v0.9.2 safety: never restore borderless/topmost automatically at launch.
        # Apply OBS Mode can still enable it during a session.
        if under.get("output_borderless") is True or under.get("output_topmost") is True:
            under["output_borderless"] = False
            under["output_topmost"] = False
            changed = True
        under.setdefault("controller_geometry", DEFAULT_CONTROLLER_GEOMETRY)
        under.setdefault("output_geometry", DEFAULT_OUTPUT_GEOMETRY)
        under.setdefault("scan_loop", False)
        under.setdefault("scan_speed_ms", RESOURCE_PROFILES["low"]["scan_ms"])
        under.setdefault("scanner_color", "#00ff99")
        under.setdefault("scratch", {})
        stage = data["stage"]
        stage.setdefault("draft_cards", {})
        stage.setdefault("save_body_pending", False)
        body = data["body"]
        if not body.get("cards"):
            body["cards"] = [new_card(), new_card("blank", "Blank / Hide")]
        for card in body["cards"]:
            fields = card.setdefault("fields", {})
            card.setdefault("layers", [])
            card["deck_border_type"] = normalize_deck_border_type(card.get("deck_border_type", ""))
            ensure_box_wrap_storage(card)
            if card.get("type") == "source_analyzer":
                fields.setdefault("sourceType", "Unknown")
                fields.setdefault("confidence", "Still Checking")
                fields.setdefault("sourceLink", "")
                fields.setdefault("claim", "")
                fields.setdefault("evidence", "")
                fields.setdefault("openQuestion", "")
                fields.setdefault("verdict", "Still Checking")
            emoji_index = 1
            image_index = 1
            text_index = 1
            for layer in card.get("layers", []):
                if layer.get("type") == "emoji":
                    layer.setdefault("visible", True)
                    if not str(layer.get("name", "")).strip():
                        if layer.get("id") == "emoji-default-scan":
                            layer["name"] = "Scan Magnifier"
                        else:
                            layer["name"] = f"Emoji {emoji_index}"
                    emoji_index += 1
                elif layer.get("type") == "image":
                    layer.setdefault("visible", True)
                    if not str(layer.get("name", "")).strip():
                        layer["name"] = f"Image {image_index}"
                    layer.setdefault("source_path", "")
                    layer.setdefault("scale", 100)
                    layer.setdefault("opacity", 1.0)
                    layer.setdefault("rotation", 0)
                    layer.setdefault("flip_x", False)
                    layer.setdefault("flip_y", False)
                    layer.setdefault("z", 0)
                    image_index += 1
                elif layer.get("type") == "text":
                    layer.setdefault("visible", True)
                    if not str(layer.get("name", "")).strip():
                        layer["name"] = f"Text {text_index}"
                    layer.setdefault("text", "New text layer")
                    layer.setdefault("size", 22)
                    layer.setdefault("color", "#e8fff5")
                    layer.setdefault("opacity", 1.0)
                    layer.setdefault("wrap_width", 260)
                    layer.setdefault("rotation", 0)
                    layer.setdefault("flip_x", False)
                    layer.setdefault("flip_y", False)
                    layer.setdefault("z", 0)
                    text_index += 1
        footer = data["footer"]
        footer.setdefault("serial", 1)
        footer.setdefault("high_water_serial", max(1, int(footer.get("serial", 1))))
        footer.setdefault("save_count", 0)
        footer.setdefault("created_serial", 1)
        footer.setdefault("last_wipe_serial", 0)
        footer.setdefault("public_clean_ready", False)
        footer.setdefault("history", [])
        header["quick_cards"] = [{"id": c.get("id"), "label": c.get("label"), "type": c.get("type")} for c in body["cards"]]

    def cards(self) -> list[dict]:
        return self.data["body"]["cards"]

    def get_card(self, card_id: str) -> dict | None:
        for card in self.cards():
            if card.get("id") == card_id:
                return card
        return None

    def active_card(self) -> dict:
        active_id = self.data["header"].get("active_card_id", "source-analyzer")
        card = self.get_card(active_id)
        if card is None:
            card = self.cards()[0]
            self.data["header"]["active_card_id"] = card.get("id")
        return card

    def set_active_card(self, card_id: str) -> None:
        if self.get_card(card_id) is None:
            return
        self.data["header"]["active_card_id"] = card_id
        self.mark_dirty("active-card-changed")

    def mark_dirty(self, event: str = "changed") -> None:
        self.data["under_header"]["dirty"] = True
        self.data["under_header"]["last_runtime_event"] = event
        self.data["header"]["modified_at"] = utc_now()

    def bump_footer_for_save(self, reason: str) -> None:
        footer = self.data["footer"]
        high = int(footer.get("high_water_serial", 1)) + 1
        footer["serial"] = high
        footer["high_water_serial"] = high
        footer["save_count"] = int(footer.get("save_count", 0)) + 1
        footer.setdefault("history", [])
        footer["history"].append({"serial": high, "at": utc_now(), "reason": reason, "path": str(self.path)})
        footer["history"] = footer["history"][-50:]

    def save(self, reason: str = "manual-save") -> None:
        self.data["header"]["modified_at"] = utc_now()
        self.data["under_header"]["dirty"] = False
        self.data["stage"]["save_body_pending"] = False
        self.data["header"]["quick_cards"] = [{"id": c.get("id"), "label": c.get("label"), "type": c.get("type")} for c in self.cards()]
        self.bump_footer_for_save(reason)
        safe_write_json(self.path, self.data)

    def save_as(self, path: Path) -> None:
        self.path = path
        self.data["under_header"]["last_loaded_path"] = str(path)
        self.save("save-as")

    def wipe_to_default(self) -> None:
        preserved_footer = copy.deepcopy(self.data.get("footer", {}))
        self.data = make_default_buttstore(preserve_footer=preserved_footer)
        self.data["under_header"]["last_runtime_event"] = "to-default-wipe"
        self.data["footer"]["public_clean_ready"] = True
        self.save("to-default-wipe")

class PerspectiveConsoleApp:
    def __init__(self) -> None:
        self.store = ButtStore.load_or_create(DEFAULT_BUTTSTORE_PATH)
        self.root = tk.Tk()
        self.root.title(f"{CONTROLLER_TITLE} v{APP_VERSION}")
        self.root.minsize(1080, 760)
        saved_controller_geo = self.store.data["under_header"].get("controller_geometry") or DEFAULT_CONTROLLER_GEOMETRY
        try:
            self.root.geometry(saved_controller_geo)
        except tk.TclError:
            self.root.geometry(DEFAULT_CONTROLLER_GEOMETRY)
        self.output = tk.Toplevel(self.root)
        self.output.title(OUTPUT_TITLE)
        self.output.geometry(self.store.data["under_header"].get("output_geometry", f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}+960+80"))
        self.output.resizable(False, False)
        self.output.protocol("WM_DELETE_WINDOW", self.hide_output)
        self.output_canvas = tk.Canvas(self.output, width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT, bg=self.store.data["header"]["output"].get("background", "#121418"), highlightthickness=0)
        self.output_canvas.pack(fill="both", expand=True)

        self.scan_y = 0
        self.scan_active = False
        self.scan_token = 0
        self.scan_loop_var = tk.BooleanVar(value=bool(self.store.data["under_header"].get("scan_loop", False)))
        self.output_visible_var = tk.BooleanVar(value=bool(self.store.data["under_header"].get("output_visible", True)))
        # v0.9.2 output recovery: always start in normal framed mode.
        # Borderless/topmost can be re-enabled from Output Tools after the window is visible.
        self.output_topmost_var = tk.BooleanVar(value=False)
        self.output_borderless_var = tk.BooleanVar(value=False)
        self.resource_profile_var = tk.StringVar(value=self.store.data["header"].get("resource_profile", "low"))
        if self.resource_profile_var.get() not in RESOURCE_PROFILES:
            self.resource_profile_var.set("low")
        self.scan_speed_var = tk.IntVar(value=int(self.store.data["under_header"].get("scan_speed_ms", RESOURCE_PROFILES["low"]["scan_ms"])))
        self.scanner_color_var = tk.StringVar(value=self.store.data["under_header"].get("scanner_color", "#00ff99"))
        self.source_type_var = tk.StringVar()
        self.confidence_var = tk.StringVar()
        self.verdict_var = tk.StringVar()
        self.source_link_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.card_label_var = tk.StringVar(value="Widget Card")
        self.claim_wrap_var = tk.IntVar(value=BOX_WRAP_DEFAULTS["claim"])
        self.evidence_wrap_var = tk.IntVar(value=BOX_WRAP_DEFAULTS["evidence"])
        self.question_wrap_var = tk.IntVar(value=BOX_WRAP_DEFAULTS["openQuestion"])

        # v0.3.1 emoji sticker editor state
        self.selected_sticker_id_var = tk.StringVar(value="")
        self.selected_sticker_label_var = tk.StringVar(value="")
        self.sticker_text_var = tk.StringVar(value="🧪")
        self.sticker_name_var = tk.StringVar(value="Emoji 1")
        self.sticker_x_var = tk.IntVar(value=820)
        self.sticker_y_var = tk.IntVar(value=340)
        self.sticker_size_var = tk.IntVar(value=28)
        self.sticker_opacity_var = tk.DoubleVar(value=1.0)
        self.sticker_label_to_id = {}
        self.emoji_preset_items = []
        self.emoji_preset_listbox = None

        # v0.4 image layer editor state
        self.selected_image_id_var = tk.StringVar(value="")
        self.selected_image_label_var = tk.StringVar(value="")
        self.image_name_var = tk.StringVar(value="Image 1")
        self.image_x_var = tk.IntVar(value=760)
        self.image_y_var = tk.IntVar(value=245)
        self.image_scale_var = tk.IntVar(value=100)
        self.image_opacity_var = tk.DoubleVar(value=1.0)
        self.image_rotation_var = tk.IntVar(value=0)
        self.image_flip_x_var = tk.BooleanVar(value=False)
        self.image_flip_y_var = tk.BooleanVar(value=False)
        self.image_z_var = tk.IntVar(value=0)
        self.image_path_var = tk.StringVar(value="")
        self.imported_image_library_var = tk.StringVar(value="")
        self.image_label_to_id = {}
        self.image_selector = None
        self.imported_image_selector = None
        self.render_image_refs = []
        self.base_image_cache = {}
        self.rendered_image_cache = {}

        # v0.5 text layer editor state
        self.selected_text_layer_id_var = tk.StringVar(value="")
        self.selected_text_layer_label_var = tk.StringVar(value="")
        self.text_layer_name_var = tk.StringVar(value="Text 1")
        self.text_layer_x_var = tk.IntVar(value=740)
        self.text_layer_y_var = tk.IntVar(value=185)
        self.text_layer_size_var = tk.IntVar(value=22)
        self.text_layer_opacity_var = tk.DoubleVar(value=1.0)
        self.text_layer_color_var = tk.StringVar(value="#e8fff5")
        self.text_layer_wrap_var = tk.IntVar(value=260)
        self.text_layer_rotation_var = tk.IntVar(value=0)
        self.text_layer_flip_x_var = tk.BooleanVar(value=False)
        self.text_layer_flip_y_var = tk.BooleanVar(value=False)
        self.text_layer_z_var = tk.IntVar(value=0)
        self.text_layer_label_to_id = {}
        self.text_layer_selector = None
        self.text_layer_text = None
        self.rendered_text_cache = {}

        # v1.1 public display-text editor state. These are global output labels
        # that used to be hard-coded inside draw_source_analyzer().
        ensure_display_text_storage(self.store.data)
        self.selected_display_text_id_var = tk.StringVar(value="")
        self.selected_display_text_label_var = tk.StringVar(value="")
        self.display_text_x_var = tk.IntVar(value=34)
        self.display_text_y_var = tk.IntVar(value=38)
        self.display_text_color_var = tk.StringVar(value="#e8fff5")
        self.display_text_border_enabled_var = tk.BooleanVar(value=False)
        self.display_text_border_color_var = tk.StringVar(value="#26333a")
        self.display_text_font_family_var = tk.StringVar(value="TkDefaultFont")
        self.display_text_font_size_var = tk.IntVar(value=12)
        self.display_text_font_weight_var = tk.StringVar(value="normal")
        self.display_text_font_slant_var = tk.StringVar(value="roman")
        self.display_text_visible_var = tk.BooleanVar(value=True)
        self.display_text_label_to_id = {}
        self.display_text_storage_listbox = None
        self.display_text_value_text = None

        # v1.1.1 Top Rows editor state. These records control the three
        # dropdown option sets and how selected row values render on output.
        ensure_top_row_storage(self.store.data)
        self.top_row_label_to_id = {}
        self.top_row_option_label_to_id = {}
        self.selected_top_row_label_var = tk.StringVar(value="")
        self.selected_top_row_id_var = tk.StringVar(value="sourceType")
        self.selected_top_row_option_label_var = tk.StringVar(value="")
        self.selected_top_row_option_id_var = tk.StringVar(value="")
        self.top_row_option_text_var = tk.StringVar(value="")
        self.top_row_font_size_var = tk.IntVar(value=15)
        self.top_row_text_color_var = tk.StringVar(value="#f0fff8")
        self.top_row_bar_color_var = tk.StringVar(value="#00ff99")
        self.top_row_x_var = tk.IntVar(value=200)
        self.top_row_y_var = tk.IntVar(value=96)
        self.top_row_visible_var = tk.BooleanVar(value=True)
        self.top_row_selector = None
        self.top_row_option_selector = None

        # v1.2 QR Group editor state. The QR label remains a Display Text object,
        # but its position is stored as a vector linked to this QR group.
        qr_group = ensure_qr_group_storage(self.store.data)
        self.qr_x_var = tk.IntVar(value=int(qr_group["x"]))
        self.qr_y_var = tk.IntVar(value=int(qr_group["y"]))
        self.qr_size_var = tk.IntVar(value=int(qr_group["size"]))
        self.qr_foreground_var = tk.StringVar(value=str(qr_group["foreground"]))
        self.qr_background_var = tk.StringVar(value=str(qr_group["background"]))
        self.qr_label_offset_x_var = tk.IntVar(value=int(qr_group["label_offset_x"]))
        self.qr_label_offset_y_var = tk.IntVar(value=int(qr_group["label_offset_y"]))
        self.qr_z_var = tk.IntVar(value=int(qr_group["z"]))
        self._syncing_qr_vars = False

        # v1.3 Colors tab state. Selection is event-driven and persisted only as
        # a lightweight scratch pointer; no polling loop runs while the tab waits.
        theme_colors = ensure_theme_color_storage(self.store.data)
        self.theme_color_vars = {role: tk.StringVar(value=color) for role, color in theme_colors.items()}
        self.theme_role_selected_vars = {role: tk.BooleanVar(value=False) for role in BITNINJA_DARK_THEME}
        scratch = self.store.data.setdefault("under_header", {}).setdefault("scratch", {})
        self.selected_theme_role_var = tk.StringVar(value=str(scratch.get("color_selected_role", "")))
        self.color_status_var = tk.StringVar(value=str(scratch.get("color_last_action", "No color selected")))
        self.color_cancel_button = None
        self.theme_swatch_labels = {}
        self._syncing_theme_selection = False

        # v1.2 mutually-exclusive per-card Deck button border classifications.
        self.deck_border_vars = {key: tk.BooleanVar(value=False) for key in DECK_BORDER_STYLES}
        self._syncing_deck_border_vars = False
        self.card_buttons = {}
        self.card_button_frames = {}
        self.deck_button_frame = None
        self.deck_storage_listbox = None
        self.deck_storage_ids = []
        self.pending_deck_swap = None
        self.max_deck_buttons = MAX_DECK_BUTTONS
        self.hotkeys_enabled_var = tk.BooleanVar(value=True)
        self.sticker_selector = None
        self.autosave_after_id = None
        self.qr_photo = None
        self.qr_cache_key = None
        self.build_controller()
        self.restore_theme_selection()
        self.load_active_card_into_editor()
        self.redraw_output()
        self.recover_output_window_on_launch()
        if not self.output_visible_var.get():
            self.output.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_controller_hotkeys()
        # Archive duplicate-looking buttstores after the UI is ready so the user can review them during the session.
        self.root.after(1200, self.archive_duplicate_buttstores_after_load)

    def hotkey_should_run(self) -> bool:
        if not self.hotkeys_enabled_var.get():
            return False
        focused = self.root.focus_get()
        # Let normal text entry/editing widgets keep their expected typing shortcuts.
        if focused is not None and isinstance(focused, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox, ttk.Spinbox)):
            return False
        return True

    def run_hotkey(self, callback) -> str:
        if self.hotkey_should_run():
            callback()
            return "break"
        return ""

    def select_deck_hotkey(self, index: int) -> None:
        cards = self.store.cards()
        if 0 <= index < min(len(cards), self.max_deck_buttons):
            self.select_card(cards[index]["id"])

    def toggle_scan_loop_hotkey(self) -> None:
        self.scan_loop_var.set(not bool(self.scan_loop_var.get()))
        self.toggle_scan_loop()

    def delete_active_card_hotkey(self) -> None:
        # Safer hotkey delete: still asks through the normal delete path.
        self.delete_active_card()

    def bind_controller_hotkeys(self) -> None:
        # Deck/card selection.
        for n in range(1, self.max_deck_buttons + 1):
            self.root.bind_all(f"<Control-Key-{n}>", lambda _event, idx=n-1: self.run_hotkey(lambda: self.select_deck_hotkey(idx)))

        self.root.bind_all("<Control-b>", lambda _event: self.run_hotkey(lambda: self.select_card("blank-hide")))
        self.root.bind_all("<Control-B>", lambda _event: self.run_hotkey(lambda: self.select_card("blank-hide")))

        # Card management.
        self.root.bind_all("<Control-d>", lambda _event: self.run_hotkey(self.duplicate_active_card))
        self.root.bind_all("<Control-D>", lambda _event: self.run_hotkey(self.duplicate_active_card))
        self.root.bind_all("<Control-Shift-D>", lambda _event: self.run_hotkey(self.delete_active_card_hotkey))

        # Output / scanner.
        self.root.bind_all("<Control-o>", lambda _event: self.run_hotkey(self.show_output))
        self.root.bind_all("<Control-O>", lambda _event: self.run_hotkey(self.show_output))
        self.root.bind_all("<Control-Shift-O>", lambda _event: self.run_hotkey(self.hide_output))
        self.root.bind_all("<Control-r>", lambda _event: self.run_hotkey(self.scan_once))
        self.root.bind_all("<Control-R>", lambda _event: self.run_hotkey(self.scan_once))
        self.root.bind_all("<Control-l>", lambda _event: self.run_hotkey(self.toggle_scan_loop_hotkey))
        self.root.bind_all("<Control-L>", lambda _event: self.run_hotkey(self.toggle_scan_loop_hotkey))

        # Save / load / export.
        self.root.bind_all("<Control-s>", lambda _event: self.run_hotkey(self.save_now))
        self.root.bind_all("<Control-S>", lambda _event: self.run_hotkey(self.save_now))
        self.root.bind_all("<Control-Shift-S>", lambda _event: self.run_hotkey(self.save_as))
        self.root.bind_all("<Control-Shift-L>", lambda _event: self.run_hotkey(self.load_buttstore))
        self.root.bind_all("<Control-e>", lambda _event: self.run_hotkey(self.export_current_card_png))
        self.root.bind_all("<Control-E>", lambda _event: self.run_hotkey(self.export_current_card_png))
        self.root.bind_all("<Control-Shift-E>", lambda _event: self.run_hotkey(self.export_all_cards_png))
        self.root.bind_all("<Control-Shift-R>", lambda _event: self.run_hotkey(self.reset_output_window_position))
        self.root.bind_all("<Control-Alt-r>", lambda _event: self.run_hotkey(self.rescue_output_window))
        self.root.bind_all("<Control-Alt-R>", lambda _event: self.run_hotkey(self.rescue_output_window))
        self.root.bind_all("<Control-Alt-o>", lambda _event: self.run_hotkey(lambda: self.disable_obs_output_mode() if self.output_borderless_var.get() else self.enable_obs_output_mode()))
        self.root.bind_all("<Control-Alt-O>", lambda _event: self.run_hotkey(lambda: self.disable_obs_output_mode() if self.output_borderless_var.get() else self.enable_obs_output_mode()))

    def build_controller(self) -> None:
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        left = ttk.Frame(self.root, padding=10)
        left.grid(row=0, column=0, sticky="ns")
        right = ttk.Frame(self.root, padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)
        right.rowconfigure(8, weight=1)
        right.rowconfigure(10, weight=1)
        right.rowconfigure(12, weight=1)
        ttk.Label(left, text="Deck Card Widget", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(left, text="Deck buttons").pack(anchor="w", pady=(8, 4))
        self.deck_button_frame = ttk.Frame(left)
        self.deck_button_frame.pack(fill="x")
        self.refresh_deck_buttons()

        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Button(left, text="Show Output", command=self.show_output).pack(fill="x", pady=2)
        ttk.Button(left, text="Hide Output", command=self.hide_output).pack(fill="x", pady=2)
        ttk.Checkbutton(left, text="Output visible on restart", variable=self.output_visible_var, command=self.on_setting_changed).pack(anchor="w", pady=(6, 2))
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Button(left, text="Scan Once", command=self.scan_once).pack(fill="x", pady=2)
        ttk.Checkbutton(left, text="Scan Loop", variable=self.scan_loop_var, command=self.toggle_scan_loop).pack(anchor="w", pady=(6, 2))
        ttk.Label(left, text="Resource profile").pack(anchor="w", pady=(10, 2))
        profile_combo = ttk.Combobox(left, state="readonly", textvariable=self.resource_profile_var, values=list(RESOURCE_PROFILES.keys()), width=21)
        profile_combo.pack(fill="x")
        profile_combo.bind("<<ComboboxSelected>>", self.on_resource_profile_changed)
        ttk.Label(left, text="Scan frame delay ms").pack(anchor="w", pady=(10, 2))
        speed = ttk.Scale(left, from_=20, to=120, orient="horizontal", command=self.on_scan_speed_drag)
        speed.set(self.scan_speed_var.get())
        speed.pack(fill="x")
        self.speed_scale = speed
        self.speed_label = ttk.Label(left, text=f"{self.scan_speed_var.get()} ms")
        self.speed_label.pack(anchor="w")
        ttk.Label(left, text="Scanner color").pack(anchor="w", pady=(8, 2))
        ttk.Entry(left, textvariable=self.scanner_color_var, width=22).pack(fill="x")
        ttk.Button(left, text="Apply Style", command=self.apply_editor_to_card).pack(fill="x", pady=(8, 2))
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="PNG export").pack(anchor="w", pady=(0, 4))
        ttk.Button(left, text="Export Card PNG", command=self.export_current_card_png).pack(fill="x", pady=2)
        ttk.Button(left, text="Export All PNGs", command=self.export_all_cards_png).pack(fill="x", pady=2)

        ttk.Label(right, text="Deck Card Editor", font=("TkDefaultFont", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(right, text="Source Type").grid(row=1, column=0, sticky="w", pady=(12, 2))
        self.source_type_combo = ttk.Combobox(right, state="readonly", textvariable=self.source_type_var, values=self.visible_top_row_values("sourceType"))
        self.source_type_combo.grid(row=1, column=1, sticky="ew", pady=(12, 2))
        ttk.Label(right, text="Confidence").grid(row=2, column=0, sticky="w", pady=2)
        self.confidence_combo = ttk.Combobox(right, state="readonly", textvariable=self.confidence_var, values=self.visible_top_row_values("confidence"))
        self.confidence_combo.grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(right, text="Verdict").grid(row=3, column=0, sticky="w", pady=2)
        self.verdict_combo = ttk.Combobox(right, state="readonly", textvariable=self.verdict_var, values=self.visible_top_row_values("verdict"))
        self.verdict_combo.grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Label(right, text="Source Link (for QR)").grid(row=4, column=0, sticky="w", pady=(6, 2))
        ttk.Entry(right, textvariable=self.source_link_var).grid(row=4, column=1, sticky="ew", pady=(6, 2))
        claim_header = ttk.Frame(right)
        claim_header.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(12, 2))
        claim_header.columnconfigure(0, weight=1)
        ttk.Label(claim_header, text="Boxed Content #1").grid(row=0, column=0, sticky="w")
        ttk.Label(claim_header, text=f"Wrap px (max {BOX_WRAP_MAXES['claim']})").grid(row=0, column=1, sticky="e", padx=(12, 4))
        ttk.Spinbox(claim_header, from_=BOX_WRAP_MIN, to=BOX_WRAP_MAXES["claim"], textvariable=self.claim_wrap_var, width=7, command=self.apply_editor_to_card).grid(row=0, column=2, sticky="e")
        ttk.Button(claim_header, text="MAX", width=5, command=lambda: self.set_box_wrap_to_max("claim", self.claim_wrap_var)).grid(row=0, column=3, sticky="e", padx=(4, 0))
        self.claim_text = tk.Text(right, height=4, wrap="word", undo=True)
        self.claim_text.grid(row=8, column=0, columnspan=2, sticky="nsew")

        evidence_header = ttk.Frame(right)
        evidence_header.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(12, 2))
        evidence_header.columnconfigure(0, weight=1)
        ttk.Label(evidence_header, text="Boxed Content #2").grid(row=0, column=0, sticky="w")
        ttk.Label(evidence_header, text=f"Wrap px (max {BOX_WRAP_MAXES['evidence']})").grid(row=0, column=1, sticky="e", padx=(12, 4))
        ttk.Spinbox(evidence_header, from_=BOX_WRAP_MIN, to=BOX_WRAP_MAXES["evidence"], textvariable=self.evidence_wrap_var, width=7, command=self.apply_editor_to_card).grid(row=0, column=2, sticky="e")
        ttk.Button(evidence_header, text="MAX", width=5, command=lambda: self.set_box_wrap_to_max("evidence", self.evidence_wrap_var)).grid(row=0, column=3, sticky="e", padx=(4, 0))
        self.evidence_text = tk.Text(right, height=4, wrap="word", undo=True)
        self.evidence_text.grid(row=10, column=0, columnspan=2, sticky="nsew")

        question_header = ttk.Frame(right)
        question_header.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(12, 2))
        question_header.columnconfigure(0, weight=1)
        ttk.Label(question_header, text="Boxed Content #3").grid(row=0, column=0, sticky="w")
        ttk.Label(question_header, text=f"Wrap px (max {BOX_WRAP_MAXES['openQuestion']})").grid(row=0, column=1, sticky="e", padx=(12, 4))
        ttk.Spinbox(question_header, from_=BOX_WRAP_MIN, to=BOX_WRAP_MAXES["openQuestion"], textvariable=self.question_wrap_var, width=7, command=self.apply_editor_to_card).grid(row=0, column=2, sticky="e")
        ttk.Button(question_header, text="MAX", width=5, command=lambda: self.set_box_wrap_to_max("openQuestion", self.question_wrap_var)).grid(row=0, column=3, sticky="e", padx=(4, 0))
        self.open_question_text = tk.Text(right, height=4, wrap="word", undo=True)
        self.open_question_text.grid(row=12, column=0, columnspan=2, sticky="nsew")
        layer_notebook = ttk.Notebook(right)
        layer_notebook.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        deck_frame = ttk.Frame(layer_notebook, padding=8)
        sticker_frame = ttk.Frame(layer_notebook, padding=8)
        image_frame = ttk.Frame(layer_notebook, padding=8)
        text_layer_frame = ttk.Frame(layer_notebook, padding=8)
        output_tools_frame = ttk.Frame(layer_notebook, padding=8)
        hotkeys_frame = ttk.Frame(layer_notebook, padding=8)
        display_edit_frame = ttk.Frame(layer_notebook, padding=8)
        top_rows_frame = ttk.Frame(layer_notebook, padding=8)
        qr_group_frame = ttk.Frame(layer_notebook, padding=8)
        colors_frame = ttk.Frame(layer_notebook, padding=8)
        layer_notebook.add(deck_frame, text="Deck Cards")
        layer_notebook.add(sticker_frame, text="Emoji Stickers")
        layer_notebook.add(image_frame, text="PNG Images")
        layer_notebook.add(text_layer_frame, text="Text Layers")
        layer_notebook.add(output_tools_frame, text="Output Tools")
        layer_notebook.add(hotkeys_frame, text="Hotkeys")
        layer_notebook.add(display_edit_frame, text="Display Edit")
        layer_notebook.add(top_rows_frame, text="Top Rows")
        layer_notebook.add(qr_group_frame, text="QR Group")
        layer_notebook.add(colors_frame, text="Colors")
        self.build_colors_tab(colors_frame)

        deck_frame.columnconfigure(0, weight=0, minsize=452)
        deck_frame.columnconfigure(1, weight=1)
        deck_left = ttk.Frame(deck_frame)
        deck_left.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        deck_right = ttk.Frame(deck_frame)
        deck_right.grid(row=0, column=1, sticky="nsew")
        deck_right.columnconfigure(0, weight=1)
        deck_right.rowconfigure(1, weight=1)

        ttk.Label(deck_left, text="Card Label").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(deck_left, textvariable=self.card_label_var, width=26).grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Button(deck_left, text="Rename Card", command=self.rename_active_card).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 2))

        deck_add_buttons = ttk.Frame(deck_left)
        deck_add_buttons.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Button(deck_add_buttons, text="Add Source", command=self.add_source_card).pack(side="left")
        ttk.Button(deck_add_buttons, text="Add Blank", command=self.add_blank_card).pack(side="left", padx=6)
        ttk.Button(deck_add_buttons, text="Duplicate Card", command=self.duplicate_active_card).pack(side="left", padx=6)
        ttk.Button(deck_add_buttons, text="Delete Card", command=self.delete_active_card).pack(side="left", padx=6)

        deck_file_buttons = ttk.Frame(deck_left)
        deck_file_buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Button(deck_file_buttons, text="Save Card", command=self.save_card_deckbutt).pack(side="left")
        ttk.Button(deck_file_buttons, text="Load Card", command=self.load_card_deckbutt).pack(side="left", padx=6)

        deck_export_buttons = ttk.Frame(deck_left)
        deck_export_buttons.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Button(deck_export_buttons, text="Export Card PNG", command=self.export_current_card_png).pack(side="left")
        ttk.Button(deck_export_buttons, text="Export All PNGs", command=self.export_all_cards_png).pack(side="left", padx=6)

        deck_border_box = ttk.LabelFrame(deck_left, text="Deck Button Information Border", padding=6)
        deck_border_box.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        for idx, key in enumerate(DECK_BORDER_STYLES):
            ttk.Checkbutton(
                deck_border_box,
                text=key,
                variable=self.deck_border_vars[key],
                command=lambda selected=key: self.on_deck_border_checkbox(selected),
            ).grid(row=idx // 4, column=idx % 4, sticky="w", padx=(0, 10), pady=2)
        ttk.Button(deck_border_box, text="Clear Border", command=self.clear_deck_border).grid(row=2, column=0, columnspan=4, sticky="w", pady=(5, 0))

        deck_note = ttk.Label(deck_left, text="Deck buttons on the sidebar show the first 8 cards. Extra cards stay in storage. Border choices are mutually exclusive per card.", wraplength=430)
        deck_note.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Label(deck_right, text="Deck Card Storage", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        deck_storage_frame = ttk.Frame(deck_right)
        deck_storage_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        deck_storage_frame.rowconfigure(0, weight=1)
        deck_storage_frame.columnconfigure(0, weight=1)
        self.deck_storage_listbox = tk.Listbox(deck_storage_frame, height=8, exportselection=False)
        self.deck_storage_listbox.grid(row=0, column=0, sticky="nsew")
        deck_storage_scroll = ttk.Scrollbar(deck_storage_frame, orient="vertical", command=self.deck_storage_listbox.yview)
        deck_storage_scroll.grid(row=0, column=1, sticky="ns")
        self.deck_storage_listbox.configure(yscrollcommand=deck_storage_scroll.set)

        deck_swap_buttons = ttk.Frame(deck_right)
        deck_swap_buttons.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(deck_swap_buttons, text="Swap Active", command=self.swap_storage_with_active).pack(side="left")
        ttk.Button(deck_swap_buttons, text="Swap Click", command=lambda: self.arm_storage_swap(True)).pack(side="left", padx=6)

        deck_silent_swap_buttons = ttk.Frame(deck_right)
        deck_silent_swap_buttons.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(deck_silent_swap_buttons, text="Silent Swap Click", command=lambda: self.arm_storage_swap(False)).pack(side="left")

        display_edit_frame.columnconfigure(0, weight=0, minsize=452)
        display_edit_frame.columnconfigure(1, weight=1)
        display_left = ttk.Frame(display_edit_frame)
        display_left.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        display_right = ttk.Frame(display_edit_frame)
        display_right.grid(row=0, column=1, sticky="nsew")
        display_right.columnconfigure(0, weight=1)
        display_right.rowconfigure(1, weight=1)

        ttk.Label(display_left, text="Display text object").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Label(display_left, textvariable=self.selected_display_text_label_var, width=34).grid(row=0, column=1, columnspan=5, sticky="w", pady=2)

        ttk.Label(display_left, text="Text").grid(row=1, column=0, sticky="nw", padx=(0, 6), pady=2)
        self.display_text_value_text = tk.Text(display_left, height=3, width=44, wrap="word", undo=True)
        self.display_text_value_text.grid(row=1, column=1, columnspan=5, sticky="ew", pady=2)

        ttk.Label(display_left, text="X").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(display_left, from_=0, to=960, textvariable=self.display_text_x_var, width=7, command=self.apply_display_text_editor).grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(display_left, text="Y").grid(row=2, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(display_left, from_=0, to=500, textvariable=self.display_text_y_var, width=7, command=self.apply_display_text_editor).grid(row=2, column=3, sticky="w", pady=2)
        ttk.Label(display_left, text="Font px").grid(row=2, column=4, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(display_left, from_=6, to=96, textvariable=self.display_text_font_size_var, width=7, command=self.apply_display_text_editor).grid(row=2, column=5, sticky="w", pady=2)

        ttk.Label(display_left, text="Text RGB").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(display_left, textvariable=self.display_text_color_var, width=10).grid(row=3, column=1, sticky="w", pady=2)
        ttk.Button(display_left, text="Pick Text RGB", command=lambda: self.choose_display_color("text")).grid(row=3, column=2, columnspan=2, sticky="w", padx=(6, 0), pady=2)
        ttk.Button(display_left, text="Default Color", command=self.default_display_color).grid(row=3, column=4, columnspan=2, sticky="w", padx=(6, 0), pady=2)

        ttk.Checkbutton(display_left, text="Border ON", variable=self.display_text_border_enabled_var, command=self.apply_display_text_editor).grid(row=4, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Label(display_left, text="Border RGB").grid(row=4, column=1, sticky="w", pady=2)
        ttk.Entry(display_left, textvariable=self.display_text_border_color_var, width=10).grid(row=4, column=2, sticky="w", pady=2)
        ttk.Button(display_left, text="Pick Border RGB", command=lambda: self.choose_display_color("border")).grid(row=4, column=3, columnspan=3, sticky="w", padx=(6, 0), pady=2)

        display_font_row = ttk.Frame(display_left)
        display_font_row.grid(row=5, column=0, columnspan=6, sticky="ew", pady=(6, 0))
        ttk.Button(display_font_row, text="Font Change", command=self.choose_display_font).pack(side="left")
        ttk.Button(display_font_row, text="Default Text", command=self.default_display_text).pack(side="left", padx=4)
        ttk.Button(display_font_row, text="Default Font", command=self.default_display_font).pack(side="left", padx=4)
        ttk.Button(display_font_row, text="Apply Now", command=self.apply_display_text_editor).pack(side="left", padx=12)

        display_visibility_row = ttk.Frame(display_left)
        display_visibility_row.grid(row=6, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Button(display_visibility_row, text="Show Text", command=self.show_display_text).pack(side="left")
        ttk.Button(display_visibility_row, text="Hide Text", command=self.hide_display_text).pack(side="left", padx=4)
        ttk.Label(display_visibility_row, textvariable=self.display_text_font_family_var).pack(side="left", padx=(18, 4))
        ttk.Label(display_visibility_row, textvariable=self.display_text_font_weight_var).pack(side="left", padx=4)
        ttk.Label(display_visibility_row, textvariable=self.display_text_font_slant_var).pack(side="left", padx=4)

        display_nudge_row = ttk.Frame(display_left)
        display_nudge_row.grid(row=7, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(display_nudge_row, text="Nudge").pack(side="left", padx=(0, 4))
        ttk.Button(display_nudge_row, text="←", width=3, command=lambda: self.nudge_display_text(-1, 0)).pack(side="left")
        ttk.Button(display_nudge_row, text="↑", width=3, command=lambda: self.nudge_display_text(0, -1)).pack(side="left")
        ttk.Button(display_nudge_row, text="↓", width=3, command=lambda: self.nudge_display_text(0, 1)).pack(side="left")
        ttk.Button(display_nudge_row, text="→", width=3, command=lambda: self.nudge_display_text(1, 0)).pack(side="left")
        ttk.Button(display_nudge_row, text="←10", width=5, command=lambda: self.nudge_display_text(-10, 0)).pack(side="left", padx=(8, 0))
        ttk.Button(display_nudge_row, text="↑10", width=5, command=lambda: self.nudge_display_text(0, -10)).pack(side="left")
        ttk.Button(display_nudge_row, text="↓10", width=5, command=lambda: self.nudge_display_text(0, 10)).pack(side="left")
        ttk.Button(display_nudge_row, text="→10", width=5, command=lambda: self.nudge_display_text(10, 0)).pack(side="left")

        display_snap_row = ttk.Frame(display_left)
        display_snap_row.grid(row=8, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(display_snap_row, text="Move").pack(side="left", padx=(0, 4))
        ttk.Button(display_snap_row, text="L", width=4, command=lambda: self.snap_display_text("left")).pack(side="left")
        ttk.Button(display_snap_row, text="CX", width=4, command=lambda: self.snap_display_text("center_x")).pack(side="left")
        ttk.Button(display_snap_row, text="R", width=4, command=lambda: self.snap_display_text("right")).pack(side="left")
        ttk.Button(display_snap_row, text="T", width=4, command=lambda: self.snap_display_text("top")).pack(side="left", padx=(8, 0))
        ttk.Button(display_snap_row, text="CY", width=4, command=lambda: self.snap_display_text("center_y")).pack(side="left")
        ttk.Button(display_snap_row, text="B", width=4, command=lambda: self.snap_display_text("bottom")).pack(side="left")

        display_note = ttk.Label(display_left, text="Display Edit controls the output labels that were previously hard-coded. Use {host} only in the Host Label object.", wraplength=430)
        display_note.grid(row=9, column=0, columnspan=6, sticky="w", pady=(10, 0))

        ttk.Label(display_right, text="Display Text Storage", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        display_storage_frame = ttk.Frame(display_right)
        display_storage_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        display_storage_frame.rowconfigure(0, weight=1)
        display_storage_frame.columnconfigure(0, weight=1)
        self.display_text_storage_listbox = tk.Listbox(display_storage_frame, height=8, exportselection=False)
        self.display_text_storage_listbox.grid(row=0, column=0, sticky="nsew")
        display_storage_scroll = ttk.Scrollbar(display_storage_frame, orient="vertical", command=self.display_text_storage_listbox.yview)
        display_storage_scroll.grid(row=0, column=1, sticky="ns")
        self.display_text_storage_listbox.configure(yscrollcommand=display_storage_scroll.set)
        self.display_text_storage_listbox.bind("<<ListboxSelect>>", self.on_display_text_selected)

        top_rows_frame.columnconfigure(0, weight=1)
        top_rows_frame.rowconfigure(7, weight=1)
        ttk.Label(top_rows_frame, text="Top row picker").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.top_row_selector = ttk.Combobox(top_rows_frame, state="readonly", textvariable=self.selected_top_row_label_var, values=[], width=34)
        self.top_row_selector.grid(row=0, column=1, columnspan=5, sticky="ew", pady=2)
        self.top_row_selector.bind("<<ComboboxSelected>>", self.on_top_row_selected)

        ttk.Label(top_rows_frame, text="Option picker").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        self.top_row_option_selector = ttk.Combobox(top_rows_frame, state="readonly", textvariable=self.selected_top_row_option_label_var, values=[], width=34)
        self.top_row_option_selector.grid(row=1, column=1, columnspan=5, sticky="ew", pady=2)
        self.top_row_option_selector.bind("<<ComboboxSelected>>", self.on_top_row_option_selected)

        ttk.Label(top_rows_frame, text="Text").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(top_rows_frame, textvariable=self.top_row_option_text_var, width=28).grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(top_rows_frame, text="Size").grid(row=2, column=2, sticky="e", padx=(10, 4), pady=2)
        ttk.Spinbox(top_rows_frame, from_=6, to=96, textvariable=self.top_row_font_size_var, width=7, command=self.apply_top_row_option).grid(row=2, column=3, sticky="w", pady=2)
        ttk.Label(top_rows_frame, text="Text RGB").grid(row=2, column=4, sticky="e", padx=(10, 4), pady=2)
        ttk.Entry(top_rows_frame, textvariable=self.top_row_text_color_var, width=10).grid(row=2, column=5, sticky="w", pady=2)

        ttk.Label(top_rows_frame, text="Bar RGB").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(top_rows_frame, textvariable=self.top_row_bar_color_var, width=10).grid(row=3, column=1, sticky="w", pady=2)
        ttk.Button(top_rows_frame, text="Pick Text RGB", command=lambda: self.choose_top_row_color("text")).grid(row=3, column=2, sticky="w", padx=(8, 0), pady=2)
        ttk.Button(top_rows_frame, text="Pick Bar RGB", command=lambda: self.choose_top_row_color("bar")).grid(row=3, column=3, sticky="w", padx=(8, 0), pady=2)
        ttk.Label(top_rows_frame, text="X").grid(row=3, column=4, sticky="e", padx=(10, 4), pady=2)
        ttk.Spinbox(top_rows_frame, from_=0, to=960, textvariable=self.top_row_x_var, width=7, command=self.apply_top_row_option).grid(row=3, column=5, sticky="w", pady=2)
        ttk.Label(top_rows_frame, text="Y").grid(row=3, column=6, sticky="e", padx=(10, 4), pady=2)
        ttk.Spinbox(top_rows_frame, from_=0, to=500, textvariable=self.top_row_y_var, width=7, command=self.apply_top_row_option).grid(row=3, column=7, sticky="w", pady=2)

        top_button_row = ttk.Frame(top_rows_frame)
        top_button_row.grid(row=4, column=0, columnspan=8, sticky="ew", pady=(6, 0))
        ttk.Button(top_button_row, text="Add Text", command=self.add_top_row_option).pack(side="left")
        ttk.Button(top_button_row, text="Duplicate", command=self.duplicate_top_row_option).pack(side="left", padx=4)
        ttk.Button(top_button_row, text="Apply Dropdown", command=self.apply_top_row_option).pack(side="left", padx=4)
        ttk.Button(top_button_row, text="Move Up", command=lambda: self.move_top_row_option(-1)).pack(side="left", padx=4)
        ttk.Button(top_button_row, text="Move Down", command=lambda: self.move_top_row_option(1)).pack(side="left", padx=4)
        ttk.Button(top_button_row, text="Delete", command=self.delete_top_row_option).pack(side="left", padx=4)
        ttk.Button(top_button_row, text="Show", command=self.show_top_row_option).pack(side="left", padx=4)
        ttk.Button(top_button_row, text="Hide", command=self.hide_top_row_option).pack(side="left", padx=4)

        top_nudge_row = ttk.Frame(top_rows_frame)
        top_nudge_row.grid(row=5, column=0, columnspan=8, sticky="ew", pady=(4, 0))
        ttk.Label(top_nudge_row, text="Nudge value + bar").pack(side="left", padx=(0, 4))
        ttk.Button(top_nudge_row, text="←", width=3, command=lambda: self.nudge_top_row_option(-1, 0)).pack(side="left")
        ttk.Button(top_nudge_row, text="↑", width=3, command=lambda: self.nudge_top_row_option(0, -1)).pack(side="left")
        ttk.Button(top_nudge_row, text="↓", width=3, command=lambda: self.nudge_top_row_option(0, 1)).pack(side="left")
        ttk.Button(top_nudge_row, text="→", width=3, command=lambda: self.nudge_top_row_option(1, 0)).pack(side="left")
        ttk.Button(top_nudge_row, text="←10", width=5, command=lambda: self.nudge_top_row_option(-10, 0)).pack(side="left", padx=(8, 0))
        ttk.Button(top_nudge_row, text="↑10", width=5, command=lambda: self.nudge_top_row_option(0, -10)).pack(side="left")
        ttk.Button(top_nudge_row, text="↓10", width=5, command=lambda: self.nudge_top_row_option(0, 10)).pack(side="left")
        ttk.Button(top_nudge_row, text="→10", width=5, command=lambda: self.nudge_top_row_option(10, 0)).pack(side="left")

        top_extra_row = ttk.Frame(top_rows_frame)
        top_extra_row.grid(row=6, column=0, columnspan=8, sticky="ew", pady=(4, 0))
        ttk.Button(top_extra_row, text="Use Option On Active Card", command=self.use_selected_top_row_option_on_card).pack(side="left")
        ttk.Button(top_extra_row, text="Default Selected Option", command=self.default_top_row_option).pack(side="left", padx=4)
        ttk.Button(top_extra_row, text="Reset This Row Defaults", command=self.reset_selected_top_row_defaults).pack(side="left", padx=4)
        ttk.Checkbutton(top_extra_row, text="Option visible in dropdown/output", variable=self.top_row_visible_var, command=self.apply_top_row_option).pack(side="left", padx=(14, 0))

        top_note = ttk.Label(
            top_rows_frame,
            text="Top Rows controls the three main dropdown data sets and their output value styling. Display Edit still controls the row labels: CARD TYPE, CONFIDENCE, and STATUS.",
            wraplength=780,
        )
        top_note.grid(row=7, column=0, columnspan=8, sticky="w", pady=(10, 0))

        qr_group_frame.columnconfigure(1, weight=1)
        ttk.Label(qr_group_frame, text="QR X").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(qr_group_frame, from_=0, to=960, textvariable=self.qr_x_var, width=8, command=self.apply_qr_group).grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(qr_group_frame, text="QR Y").grid(row=0, column=2, sticky="e", padx=(12, 6), pady=2)
        ttk.Spinbox(qr_group_frame, from_=0, to=500, textvariable=self.qr_y_var, width=8, command=self.apply_qr_group).grid(row=0, column=3, sticky="w", pady=2)
        ttk.Label(qr_group_frame, text="QR size").grid(row=0, column=4, sticky="e", padx=(12, 6), pady=2)
        ttk.Spinbox(qr_group_frame, from_=48, to=260, textvariable=self.qr_size_var, width=8, command=self.apply_qr_group).grid(row=0, column=5, sticky="w", pady=2)
        ttk.Label(qr_group_frame, text="Z").grid(row=0, column=6, sticky="e", padx=(12, 6), pady=2)
        ttk.Spinbox(qr_group_frame, from_=-1000, to=1000, textvariable=self.qr_z_var, width=8, command=self.apply_qr_group).grid(row=0, column=7, sticky="w", pady=2)

        ttk.Label(qr_group_frame, text="Foreground RGB").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(qr_group_frame, textvariable=self.qr_foreground_var, width=12).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Button(qr_group_frame, text="Pick Foreground", command=lambda: self.choose_qr_color("foreground")).grid(row=1, column=2, columnspan=2, sticky="w", padx=(8, 0), pady=2)
        ttk.Label(qr_group_frame, text="Background RGB").grid(row=1, column=4, sticky="e", padx=(12, 6), pady=2)
        ttk.Entry(qr_group_frame, textvariable=self.qr_background_var, width=12).grid(row=1, column=5, sticky="w", pady=2)
        ttk.Button(qr_group_frame, text="Pick Background", command=lambda: self.choose_qr_color("background")).grid(row=1, column=6, columnspan=2, sticky="w", padx=(8, 0), pady=2)

        ttk.Label(qr_group_frame, text="Label vector X").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(qr_group_frame, from_=-960, to=960, textvariable=self.qr_label_offset_x_var, width=8, command=self.apply_qr_group).grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(qr_group_frame, text="Label vector Y").grid(row=2, column=2, sticky="e", padx=(12, 6), pady=2)
        ttk.Spinbox(qr_group_frame, from_=-500, to=500, textvariable=self.qr_label_offset_y_var, width=8, command=self.apply_qr_group).grid(row=2, column=3, sticky="w", pady=2)
        ttk.Button(qr_group_frame, text="Apply QR Group", command=self.apply_qr_group).grid(row=2, column=4, columnspan=2, sticky="w", padx=(12, 0), pady=2)
        ttk.Button(qr_group_frame, text="Reset QR Defaults", command=self.reset_qr_group_defaults).grid(row=2, column=6, columnspan=2, sticky="w", padx=(8, 0), pady=2)

        qr_nudge_row = ttk.Frame(qr_group_frame)
        qr_nudge_row.grid(row=3, column=0, columnspan=8, sticky="ew", pady=(7, 0))
        ttk.Label(qr_nudge_row, text="QR single move (1 px)").pack(side="left", padx=(0, 4))
        ttk.Button(qr_nudge_row, text="←", width=3, command=lambda: self.nudge_qr_group(-1, 0)).pack(side="left")
        ttk.Button(qr_nudge_row, text="↑", width=3, command=lambda: self.nudge_qr_group(0, -1)).pack(side="left")
        ttk.Button(qr_nudge_row, text="↓", width=3, command=lambda: self.nudge_qr_group(0, 1)).pack(side="left")
        ttk.Button(qr_nudge_row, text="→", width=3, command=lambda: self.nudge_qr_group(1, 0)).pack(side="left")
        ttk.Label(qr_nudge_row, text="QR nudge (10 px)").pack(side="left", padx=(12, 4))
        ttk.Button(qr_nudge_row, text="←10", width=5, command=lambda: self.nudge_qr_group(-10, 0)).pack(side="left")
        ttk.Button(qr_nudge_row, text="↑10", width=5, command=lambda: self.nudge_qr_group(0, -10)).pack(side="left")
        ttk.Button(qr_nudge_row, text="↓10", width=5, command=lambda: self.nudge_qr_group(0, 10)).pack(side="left")
        ttk.Button(qr_nudge_row, text="→10", width=5, command=lambda: self.nudge_qr_group(10, 0)).pack(side="left")

        qr_label_nudge_row = ttk.Frame(qr_group_frame)
        qr_label_nudge_row.grid(row=4, column=0, columnspan=8, sticky="ew", pady=(4, 0))
        ttk.Label(qr_label_nudge_row, text="Label single move (1 px)").pack(side="left", padx=(0, 4))
        ttk.Button(qr_label_nudge_row, text="←", width=3, command=lambda: self.nudge_qr_label(-1, 0)).pack(side="left")
        ttk.Button(qr_label_nudge_row, text="↑", width=3, command=lambda: self.nudge_qr_label(0, -1)).pack(side="left")
        ttk.Button(qr_label_nudge_row, text="↓", width=3, command=lambda: self.nudge_qr_label(0, 1)).pack(side="left")
        ttk.Button(qr_label_nudge_row, text="→", width=3, command=lambda: self.nudge_qr_label(1, 0)).pack(side="left")
        ttk.Label(qr_label_nudge_row, text="Label nudge (10 px)").pack(side="left", padx=(12, 4))
        ttk.Button(qr_label_nudge_row, text="←10", width=5, command=lambda: self.nudge_qr_label(-10, 0)).pack(side="left")
        ttk.Button(qr_label_nudge_row, text="↑10", width=5, command=lambda: self.nudge_qr_label(0, -10)).pack(side="left")
        ttk.Button(qr_label_nudge_row, text="↓10", width=5, command=lambda: self.nudge_qr_label(0, 10)).pack(side="left")
        ttk.Button(qr_label_nudge_row, text="→10", width=5, command=lambda: self.nudge_qr_label(10, 0)).pack(side="left")

        qr_z_row = ttk.Frame(qr_group_frame)
        qr_z_row.grid(row=5, column=0, columnspan=8, sticky="ew", pady=(4, 0))
        ttk.Label(qr_z_row, text="Z-axis fine tuning").pack(side="left", padx=(0, 4))
        ttk.Button(qr_z_row, text="Z Down", command=lambda: self.nudge_qr_z(-1)).pack(side="left")
        ttk.Button(qr_z_row, text="Z Up", command=lambda: self.nudge_qr_z(1)).pack(side="left", padx=4)
        ttk.Button(qr_z_row, text="Bring to Front", command=self.bring_qr_to_front).pack(side="left", padx=(14, 4))
        ttk.Button(qr_z_row, text="Pull to Back", command=self.pull_qr_to_back).pack(side="left", padx=4)

        qr_note = ttk.Label(
            qr_group_frame,
            text="The QR label uses a saved vector from the QR square. Moving the QR section keeps the label attached; moving QR Label in Display Edit updates the same vector. Pull to Back restores the original z-axis position below sticker/image/text layers.",
            wraplength=790,
        )
        qr_note.grid(row=6, column=0, columnspan=8, sticky="w", pady=(10, 0))

        sticker_frame.columnconfigure(0, weight=0)
        sticker_frame.columnconfigure(1, weight=1)

        sticker_left = ttk.Frame(sticker_frame)
        sticker_left.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        sticker_right = ttk.Frame(sticker_frame)
        sticker_right.grid(row=0, column=1, sticky="nsew")
        sticker_right.columnconfigure(0, weight=1)
        sticker_right.rowconfigure(1, weight=1)

        ttk.Label(sticker_left, text="Sticker").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.sticker_selector = ttk.Combobox(
            sticker_left,
            state="readonly",
            textvariable=self.selected_sticker_label_var,
            values=[],
            width=38,
        )
        self.sticker_selector.grid(row=0, column=1, columnspan=3, sticky="ew", pady=2)
        self.sticker_selector.bind("<<ComboboxSelected>>", self.on_sticker_selected)

        ttk.Label(sticker_left, text="Emoji").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(sticker_left, textvariable=self.sticker_text_var, width=12).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(sticker_left, text="X").grid(row=1, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(sticker_left, from_=0, to=960, textvariable=self.sticker_x_var, width=7, command=self.apply_sticker_editor).grid(row=1, column=3, sticky="w", pady=2)

        ttk.Label(sticker_left, text="Y").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(sticker_left, from_=0, to=500, textvariable=self.sticker_y_var, width=7, command=self.apply_sticker_editor).grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(sticker_left, text="Size").grid(row=2, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(sticker_left, from_=8, to=96, textvariable=self.sticker_size_var, width=7, command=self.apply_sticker_editor).grid(row=2, column=3, sticky="w", pady=2)

        ttk.Label(sticker_left, text="Opacity").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(sticker_left, from_=0.1, to=1.0, increment=0.1, textvariable=self.sticker_opacity_var, width=7, command=self.apply_sticker_editor).grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(sticker_left, text="Name").grid(row=3, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Entry(sticker_left, textvariable=self.sticker_name_var, width=21).grid(row=3, column=3, sticky="w", pady=2)

        sticker_buttons = ttk.Frame(sticker_left)
        sticker_buttons.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Button(sticker_buttons, text="Add Emoji", command=self.add_emoji_sticker).pack(side="left")
        ttk.Button(sticker_buttons, text="Duplicate", command=self.duplicate_sticker).pack(side="left", padx=4)
        ttk.Button(sticker_buttons, text="Apply Sticker", command=self.apply_sticker_editor).pack(side="left", padx=4)
        ttk.Button(sticker_buttons, text="Delete", command=self.delete_sticker).pack(side="left", padx=4)

        sticker_visibility_buttons = ttk.Frame(sticker_left)
        sticker_visibility_buttons.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Button(sticker_visibility_buttons, text="Show", command=self.show_sticker).pack(side="left")
        ttk.Button(sticker_visibility_buttons, text="Hide", command=self.hide_sticker).pack(side="left", padx=4)
        ttk.Button(sticker_visibility_buttons, text="Layer Up", command=self.layer_sticker_up).pack(side="left", padx=(28, 4))
        ttk.Button(sticker_visibility_buttons, text="Layer Down", command=self.layer_sticker_down).pack(side="left", padx=4)

        sticker_nudge_buttons = ttk.Frame(sticker_left)
        sticker_nudge_buttons.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Label(sticker_nudge_buttons, text="Nudge").pack(side="left", padx=(0, 4))
        ttk.Button(sticker_nudge_buttons, text="←", width=3, command=lambda: self.nudge_sticker(-1, 0)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="↑", width=3, command=lambda: self.nudge_sticker(0, -1)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="↓", width=3, command=lambda: self.nudge_sticker(0, 1)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="→", width=3, command=lambda: self.nudge_sticker(1, 0)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="←10", width=5, command=lambda: self.nudge_sticker(-10, 0)).pack(side="left", padx=(8, 0))
        ttk.Button(sticker_nudge_buttons, text="↑10", width=5, command=lambda: self.nudge_sticker(0, -10)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="↓10", width=5, command=lambda: self.nudge_sticker(0, 10)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="→10", width=5, command=lambda: self.nudge_sticker(10, 0)).pack(side="left")

        sticker_snap_buttons = ttk.Frame(sticker_left)
        sticker_snap_buttons.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Label(sticker_snap_buttons, text="Snap").pack(side="left", padx=(0, 4))
        ttk.Button(sticker_snap_buttons, text="L", width=4, command=lambda: self.snap_sticker("left")).pack(side="left")
        ttk.Button(sticker_snap_buttons, text="CX", width=4, command=lambda: self.snap_sticker("center_x")).pack(side="left")
        ttk.Button(sticker_snap_buttons, text="R", width=4, command=lambda: self.snap_sticker("right")).pack(side="left")
        ttk.Button(sticker_snap_buttons, text="T", width=4, command=lambda: self.snap_sticker("top")).pack(side="left", padx=(8, 0))
        ttk.Button(sticker_snap_buttons, text="CY", width=4, command=lambda: self.snap_sticker("center_y")).pack(side="left")
        ttk.Button(sticker_snap_buttons, text="B", width=4, command=lambda: self.snap_sticker("bottom")).pack(side="left")

        ttk.Label(sticker_right, text="Emoji Presets", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        preset_list_frame = ttk.Frame(sticker_right)
        preset_list_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        preset_list_frame.rowconfigure(0, weight=1)
        preset_list_frame.columnconfigure(0, weight=1)
        self.emoji_preset_listbox = tk.Listbox(preset_list_frame, height=9, exportselection=False)
        self.emoji_preset_listbox.grid(row=0, column=0, sticky="nsew")
        preset_scroll = ttk.Scrollbar(preset_list_frame, orient="vertical", command=self.emoji_preset_listbox.yview)
        preset_scroll.grid(row=0, column=1, sticky="ns")
        self.emoji_preset_listbox.configure(yscrollcommand=preset_scroll.set)
        self.emoji_preset_listbox.bind("<<ListboxSelect>>", self.on_emoji_preset_selected)
        self.emoji_preset_listbox.bind("<Double-Button-1>", lambda _e: self.use_selected_emoji_preset())

        preset_buttons = ttk.Frame(sticker_right)
        preset_buttons.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(preset_buttons, text="Use Selected", command=self.use_selected_emoji_preset).pack(side="left")
        ttk.Button(preset_buttons, text="Copy Selected", command=self.copy_selected_emoji_preset).pack(side="left", padx=4)
        preset_load_buttons = ttk.Frame(sticker_right)
        preset_load_buttons.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(preset_load_buttons, text="Load .emoji", command=self.load_custom_emoji_file).pack(side="left")

        self.load_emoji_presets()

        image_frame.columnconfigure(1, weight=1)
        ttk.Label(image_frame, text="Image Layer").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.image_selector = ttk.Combobox(image_frame, state="readonly", textvariable=self.selected_image_label_var, values=[], width=38)
        self.image_selector.grid(row=0, column=1, columnspan=5, sticky="ew", pady=2)
        self.image_selector.bind("<<ComboboxSelected>>", self.on_image_layer_selected)

        ttk.Label(image_frame, text="Name").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(image_frame, textvariable=self.image_name_var, width=22).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(image_frame, text="X").grid(row=1, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(image_frame, from_=0, to=960, textvariable=self.image_x_var, width=7, command=self.apply_image_editor).grid(row=1, column=3, sticky="w", pady=2)
        ttk.Label(image_frame, text="Y").grid(row=1, column=4, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(image_frame, from_=0, to=500, textvariable=self.image_y_var, width=7, command=self.apply_image_editor).grid(row=1, column=5, sticky="w", pady=2)

        ttk.Label(image_frame, text="Scale %").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(image_frame, from_=10, to=400, textvariable=self.image_scale_var, width=7, command=self.apply_image_editor).grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(image_frame, text="Opacity").grid(row=2, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(image_frame, from_=0.1, to=1.0, increment=0.1, textvariable=self.image_opacity_var, width=7, command=self.apply_image_editor).grid(row=2, column=3, sticky="w", pady=2)
        ttk.Label(image_frame, text="Rotation °").grid(row=2, column=4, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(image_frame, from_=-359, to=359, textvariable=self.image_rotation_var, width=7, command=self.apply_image_editor).grid(row=2, column=5, sticky="w", pady=2)

        transform_row = ttk.Frame(image_frame)
        transform_row.grid(row=3, column=0, columnspan=6, sticky="ew", pady=2)
        ttk.Checkbutton(transform_row, text="X Flip", variable=self.image_flip_x_var, command=self.apply_image_editor).pack(side="left")
        ttk.Checkbutton(transform_row, text="Y Flip", variable=self.image_flip_y_var, command=self.apply_image_editor).pack(side="left", padx=(8, 0))
        ttk.Label(transform_row, text="Z").pack(side="left", padx=(18, 4))
        ttk.Spinbox(transform_row, from_=-1000, to=1000, textvariable=self.image_z_var, width=7, command=self.apply_image_editor).pack(side="left")
        ttk.Label(transform_row, text="Source:").pack(side="left", padx=(18, 4))
        ttk.Label(transform_row, textvariable=self.image_path_var).pack(side="left")

        library_row = ttk.Frame(image_frame)
        library_row.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(library_row, text="Imported image library").pack(side="left", padx=(0, 6))
        self.imported_image_selector = ttk.Combobox(library_row, state="readonly", textvariable=self.imported_image_library_var, values=[], width=34)
        self.imported_image_selector.pack(side="left", fill="x", expand=True)
        ttk.Button(library_row, text="Reuse Selected", command=self.reuse_imported_png_layer).pack(side="left", padx=4)
        ttk.Button(library_row, text="Refresh", command=self.refresh_imported_image_library).pack(side="left")

        image_buttons = ttk.Frame(image_frame)
        image_buttons.grid(row=5, column=0, columnspan=6, sticky="ew", pady=(6, 0))
        ttk.Button(image_buttons, text="Import New PNG", command=self.import_png_layer).pack(side="left")
        ttk.Button(image_buttons, text="Duplicate", command=self.duplicate_image_layer).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Apply Image", command=self.apply_image_editor).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Delete", command=self.delete_image_layer).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Show", command=self.show_image_layer).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Hide", command=self.hide_image_layer).pack(side="left", padx=4)

        image_nudge_buttons = ttk.Frame(image_frame)
        image_nudge_buttons.grid(row=6, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(image_nudge_buttons, text="Move 1 px").pack(side="left", padx=(0, 4))
        ttk.Button(image_nudge_buttons, text="←", width=3, command=lambda: self.nudge_image_layer(-1, 0)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="↑", width=3, command=lambda: self.nudge_image_layer(0, -1)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="↓", width=3, command=lambda: self.nudge_image_layer(0, 1)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="→", width=3, command=lambda: self.nudge_image_layer(1, 0)).pack(side="left")
        ttk.Label(image_nudge_buttons, text="Nudge 10 px").pack(side="left", padx=(10, 4))
        ttk.Button(image_nudge_buttons, text="←10", width=5, command=lambda: self.nudge_image_layer(-10, 0)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="↑10", width=5, command=lambda: self.nudge_image_layer(0, -10)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="↓10", width=5, command=lambda: self.nudge_image_layer(0, 10)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="→10", width=5, command=lambda: self.nudge_image_layer(10, 0)).pack(side="left")

        image_z_buttons = ttk.Frame(image_frame)
        image_z_buttons.grid(row=7, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(image_z_buttons, text="Z-axis fine tuning").pack(side="left", padx=(0, 4))
        ttk.Button(image_z_buttons, text="Z Down", command=lambda: self.nudge_image_z(-1)).pack(side="left")
        ttk.Button(image_z_buttons, text="Z Up", command=lambda: self.nudge_image_z(1)).pack(side="left", padx=4)
        ttk.Button(image_z_buttons, text="Bring to Front", command=self.bring_image_to_front).pack(side="left", padx=(12, 4))
        ttk.Button(image_z_buttons, text="Pull to Back", command=self.pull_image_to_back).pack(side="left", padx=4)

        image_snap_buttons = ttk.Frame(image_frame)
        image_snap_buttons.grid(row=8, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(image_snap_buttons, text="Snap").pack(side="left", padx=(0, 4))
        ttk.Button(image_snap_buttons, text="L", width=4, command=lambda: self.snap_image_layer("left")).pack(side="left")
        ttk.Button(image_snap_buttons, text="CX", width=4, command=lambda: self.snap_image_layer("center_x")).pack(side="left")
        ttk.Button(image_snap_buttons, text="R", width=4, command=lambda: self.snap_image_layer("right")).pack(side="left")
        ttk.Button(image_snap_buttons, text="T", width=4, command=lambda: self.snap_image_layer("top")).pack(side="left", padx=(8, 0))
        ttk.Button(image_snap_buttons, text="CY", width=4, command=lambda: self.snap_image_layer("center_y")).pack(side="left")
        ttk.Button(image_snap_buttons, text="B", width=4, command=lambda: self.snap_image_layer("bottom")).pack(side="left")
        self.refresh_imported_image_library()

        text_layer_frame.columnconfigure(1, weight=1)
        ttk.Label(text_layer_frame, text="Text Layer").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.text_layer_selector = ttk.Combobox(text_layer_frame, state="readonly", textvariable=self.selected_text_layer_label_var, values=[], width=38)
        self.text_layer_selector.grid(row=0, column=1, columnspan=5, sticky="ew", pady=2)
        self.text_layer_selector.bind("<<ComboboxSelected>>", self.on_text_layer_selected)

        ttk.Label(text_layer_frame, text="Name").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(text_layer_frame, textvariable=self.text_layer_name_var, width=22).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(text_layer_frame, text="X").grid(row=1, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(text_layer_frame, from_=0, to=960, textvariable=self.text_layer_x_var, width=7, command=self.apply_text_layer_editor).grid(row=1, column=3, sticky="w", pady=2)
        ttk.Label(text_layer_frame, text="Y").grid(row=1, column=4, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(text_layer_frame, from_=0, to=500, textvariable=self.text_layer_y_var, width=7, command=self.apply_text_layer_editor).grid(row=1, column=5, sticky="w", pady=2)

        ttk.Label(text_layer_frame, text="Size").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(text_layer_frame, from_=8, to=72, textvariable=self.text_layer_size_var, width=7, command=self.apply_text_layer_editor).grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(text_layer_frame, text="Opacity").grid(row=2, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(text_layer_frame, from_=0.1, to=1.0, increment=0.1, textvariable=self.text_layer_opacity_var, width=7, command=self.apply_text_layer_editor).grid(row=2, column=3, sticky="w", pady=2)
        ttk.Label(text_layer_frame, text="Color").grid(row=2, column=4, sticky="e", padx=(12, 4), pady=2)
        ttk.Entry(text_layer_frame, textvariable=self.text_layer_color_var, width=10).grid(row=2, column=5, sticky="w", pady=2)

        ttk.Label(text_layer_frame, text="Wrap px").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(text_layer_frame, from_=80, to=900, textvariable=self.text_layer_wrap_var, width=8, command=self.apply_text_layer_editor).grid(row=3, column=1, sticky="w", pady=2)
        ttk.Label(text_layer_frame, text="Rotation °").grid(row=3, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(text_layer_frame, from_=-359, to=359, textvariable=self.text_layer_rotation_var, width=7, command=self.apply_text_layer_editor).grid(row=3, column=3, sticky="w", pady=2)
        text_transform = ttk.Frame(text_layer_frame)
        text_transform.grid(row=3, column=4, columnspan=2, sticky="w", padx=(12, 0))
        ttk.Checkbutton(text_transform, text="X Flip", variable=self.text_layer_flip_x_var, command=self.apply_text_layer_editor).pack(side="left")
        ttk.Checkbutton(text_transform, text="Y Flip", variable=self.text_layer_flip_y_var, command=self.apply_text_layer_editor).pack(side="left", padx=(6, 0))
        ttk.Label(text_transform, text="Z").pack(side="left", padx=(10, 3))
        ttk.Spinbox(text_transform, from_=-1000, to=1000, textvariable=self.text_layer_z_var, width=6, command=self.apply_text_layer_editor).pack(side="left")

        ttk.Label(text_layer_frame, text="Text").grid(row=4, column=0, sticky="nw", padx=(0, 6), pady=2)
        self.text_layer_text = tk.Text(text_layer_frame, height=4, width=58, wrap="word")
        self.text_layer_text.grid(row=4, column=1, columnspan=5, sticky="ew", pady=2)

        text_layer_buttons = ttk.Frame(text_layer_frame)
        text_layer_buttons.grid(row=5, column=0, columnspan=6, sticky="ew", pady=(6, 0))
        ttk.Button(text_layer_buttons, text="Add Text", command=self.add_text_layer).pack(side="left")
        ttk.Button(text_layer_buttons, text="Duplicate", command=self.duplicate_text_layer).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Apply Text", command=self.apply_text_layer_editor).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Delete", command=self.delete_text_layer).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Show", command=self.show_text_layer).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Hide", command=self.hide_text_layer).pack(side="left", padx=4)

        text_nudge_buttons = ttk.Frame(text_layer_frame)
        text_nudge_buttons.grid(row=6, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(text_nudge_buttons, text="Move 1 px").pack(side="left", padx=(0, 4))
        ttk.Button(text_nudge_buttons, text="←", width=3, command=lambda: self.nudge_text_layer(-1, 0)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="↑", width=3, command=lambda: self.nudge_text_layer(0, -1)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="↓", width=3, command=lambda: self.nudge_text_layer(0, 1)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="→", width=3, command=lambda: self.nudge_text_layer(1, 0)).pack(side="left")
        ttk.Label(text_nudge_buttons, text="Nudge 10 px").pack(side="left", padx=(10, 4))
        ttk.Button(text_nudge_buttons, text="←10", width=5, command=lambda: self.nudge_text_layer(-10, 0)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="↑10", width=5, command=lambda: self.nudge_text_layer(0, -10)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="↓10", width=5, command=lambda: self.nudge_text_layer(0, 10)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="→10", width=5, command=lambda: self.nudge_text_layer(10, 0)).pack(side="left")

        text_z_buttons = ttk.Frame(text_layer_frame)
        text_z_buttons.grid(row=7, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(text_z_buttons, text="Z-axis fine tuning").pack(side="left", padx=(0, 4))
        ttk.Button(text_z_buttons, text="Z Down", command=lambda: self.nudge_text_z(-1)).pack(side="left")
        ttk.Button(text_z_buttons, text="Z Up", command=lambda: self.nudge_text_z(1)).pack(side="left", padx=4)
        ttk.Button(text_z_buttons, text="Bring to Front", command=self.bring_text_to_front).pack(side="left", padx=(12, 4))
        ttk.Button(text_z_buttons, text="Pull to Back", command=self.pull_text_to_back).pack(side="left", padx=4)

        text_snap_buttons = ttk.Frame(text_layer_frame)
        text_snap_buttons.grid(row=8, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(text_snap_buttons, text="Snap").pack(side="left", padx=(0, 4))
        ttk.Button(text_snap_buttons, text="L", width=4, command=lambda: self.snap_text_layer("left")).pack(side="left")
        ttk.Button(text_snap_buttons, text="CX", width=4, command=lambda: self.snap_text_layer("center_x")).pack(side="left")
        ttk.Button(text_snap_buttons, text="R", width=4, command=lambda: self.snap_text_layer("right")).pack(side="left")
        ttk.Button(text_snap_buttons, text="T", width=4, command=lambda: self.snap_text_layer("top")).pack(side="left", padx=(8, 0))
        ttk.Button(text_snap_buttons, text="CY", width=4, command=lambda: self.snap_text_layer("center_y")).pack(side="left")
        ttk.Button(text_snap_buttons, text="B", width=4, command=lambda: self.snap_text_layer("bottom")).pack(side="left")

        output_tools_frame.columnconfigure(0, weight=1)
        ttk.Label(output_tools_frame, text="OBS Output Tools", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(output_tools_frame, text="Stable OBS capture title: 3DCP Perspective Console - Output").grid(row=1, column=0, sticky="w", pady=(0, 8))

        output_checks = ttk.Frame(output_tools_frame)
        output_checks.grid(row=2, column=0, sticky="w", pady=(0, 8))
        ttk.Checkbutton(output_checks, text="Always on top", variable=self.output_topmost_var, command=self.apply_output_window_style).pack(side="left")
        ttk.Checkbutton(output_checks, text="Borderless OBS mode", variable=self.output_borderless_var, command=self.apply_output_window_style).pack(side="left", padx=14)

        output_buttons_row1 = ttk.Frame(output_tools_frame)
        output_buttons_row1.grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Button(output_buttons_row1, text="Apply OBS Mode", command=self.enable_obs_output_mode).pack(side="left")
        ttk.Button(output_buttons_row1, text="Normal Output", command=self.disable_obs_output_mode).pack(side="left", padx=6)
        ttk.Button(output_buttons_row1, text="Bring Output Front", command=self.bring_output_front).pack(side="left", padx=6)

        output_buttons_row2 = ttk.Frame(output_tools_frame)
        output_buttons_row2.grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Button(output_buttons_row2, text="Rescue Output Window", command=self.rescue_output_window).pack(side="left")
        ttk.Button(output_buttons_row2, text="Reset Output Window", command=self.reset_output_window_position).pack(side="left", padx=6)
        ttk.Button(output_buttons_row2, text="Show Output", command=self.show_output).pack(side="left", padx=6)
        ttk.Button(output_buttons_row2, text="Hide Output", command=self.hide_output).pack(side="left", padx=6)
        ttk.Button(output_buttons_row2, text="Save Output Settings", command=self.save_output_settings).pack(side="left", padx=6)

        output_notes = tk.Text(output_tools_frame, height=8, width=78, wrap="word")
        output_notes.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        output_notes.insert("1.0",
            "OBS Output Notes\n"
            "- The output window title is now stable between app versions.\n"
            "- Borderless OBS mode removes the window frame for cleaner capture.\n"
            "- Always on top is useful while arranging OBS/window capture.\n"
            "- Normal Output restores the frame so you can move the window normally.\n"
            "- Rescue Output Window forces normal framed mode at 960x500+80+80.\n"
            "- Reset Output Window places the OBS output at 960x500+80+80."
        )
        output_notes.configure(state="disabled")

        hotkeys_frame.columnconfigure(0, weight=1)
        ttk.Label(hotkeys_frame, text="Controller Hotkeys", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Checkbutton(hotkeys_frame, text="Enable controller hotkeys", variable=self.hotkeys_enabled_var).grid(row=1, column=0, sticky="w", pady=(0, 8))

        hotkey_text = (
            "Deck/Card\n"
            "  Ctrl+1 ... Ctrl+8    Select sidebar deck card 1-8\n"
            "  Ctrl+B               Blank / Hide\n"
            "  Ctrl+D               Duplicate active card\n"
            "  Ctrl+Shift+D         Delete active card\n"
            "\nOutput / Stream\n"
            "  Ctrl+O               Show output\n"
            "  Ctrl+Shift+O         Hide output\n"
            "  Ctrl+R               Scan Once / reset scan instantly\n"
            "  Ctrl+L               Toggle Scan Loop\n"
            "\nSave / Load / Export\n"
            "  Ctrl+S               Save + Apply\n"
            "  Ctrl+Shift+S         Save As .buttstore\n"
            "  Ctrl+Shift+L         Load .buttstore\n"
            "  Ctrl+E               Export Card PNG\n"
            "  Ctrl+Shift+E         Export All PNGs\n"
            "  Ctrl+Shift+R         Reset Output Window\n"
            "  Ctrl+Alt+R           Rescue Output Window\n"
            "  Ctrl+Alt+O           Toggle OBS output mode\n"
            "\nNotes\n"
            "  Hotkeys work while the controller window has focus.\n"
            "  Text boxes keep normal typing behavior; hotkeys are ignored while typing in text fields."
        )
        hotkey_box = tk.Text(hotkeys_frame, height=20, width=76, wrap="word")
        hotkey_box.grid(row=2, column=0, sticky="nsew")
        hotkey_box.insert("1.0", hotkey_text)
        hotkey_box.configure(state="disabled")

        controls = ttk.Frame(right)
        controls.grid(row=14, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(controls, text="Apply to Output", command=self.apply_editor_to_card).pack(side="left")
        ttk.Button(controls, text="Save + Apply", command=self.save_now).pack(side="left", padx=6)
        ttk.Label(controls, textvariable=self.status_var, width=25, anchor="w").pack(side="left", padx=10)
        tk.Button(controls, text="Wipe 2 Default", command=self.to_default_wipe, bg="#650000", fg="white", activebackground="#8b0000", activeforeground="white").pack(side="right", padx=(8, 0))
        ttk.Button(controls, text="Load .buttstore", command=self.load_buttstore).pack(side="right", padx=4)
        ttk.Button(controls, text="Save As .buttstore", command=self.save_as).pack(side="right", padx=4)

        for widget in [self.claim_text, self.evidence_text, self.open_question_text]:
            widget.bind("<FocusOut>", self.on_editor_focus_out)
            widget.bind("<<Modified>>", self.on_text_modified)

        self.text_layer_text.bind("<FocusOut>", self.on_text_layer_focus_out)
        self.text_layer_text.bind("<<Modified>>", self.on_text_layer_modified)

        if self.display_text_value_text is not None:
            self.display_text_value_text.bind("<FocusOut>", self.on_display_text_focus_out)
            self.display_text_value_text.bind("<<Modified>>", self.on_display_text_modified)

        for var in [self.source_type_var, self.confidence_var, self.verdict_var, self.source_link_var, self.scanner_color_var, self.claim_wrap_var, self.evidence_wrap_var, self.question_wrap_var]:
            var.trace_add("write", lambda *_: self.schedule_autosave_stage_only())

        for var in [self.sticker_text_var, self.sticker_name_var, self.sticker_x_var, self.sticker_y_var, self.sticker_size_var, self.sticker_opacity_var]:
            var.trace_add("write", lambda *_: self.schedule_sticker_stage_only())

        for var in [self.image_name_var, self.image_x_var, self.image_y_var, self.image_scale_var, self.image_opacity_var, self.image_rotation_var, self.image_flip_x_var, self.image_flip_y_var, self.image_z_var]:
            var.trace_add("write", lambda *_: self.schedule_image_stage_only())

        for var in [self.text_layer_name_var, self.text_layer_x_var, self.text_layer_y_var, self.text_layer_size_var, self.text_layer_opacity_var, self.text_layer_color_var, self.text_layer_wrap_var, self.text_layer_rotation_var, self.text_layer_flip_x_var, self.text_layer_flip_y_var, self.text_layer_z_var]:
            var.trace_add("write", lambda *_: self.schedule_text_layer_stage_only())

        for var in [self.display_text_x_var, self.display_text_y_var, self.display_text_color_var, self.display_text_border_enabled_var, self.display_text_border_color_var, self.display_text_font_size_var]:
            var.trace_add("write", lambda *_: self.schedule_display_text_stage_only())

        for var in [self.top_row_option_text_var, self.top_row_font_size_var, self.top_row_text_color_var, self.top_row_bar_color_var, self.top_row_x_var, self.top_row_y_var, self.top_row_visible_var]:
            var.trace_add("write", lambda *_: self.schedule_top_row_stage_only())

        for var in [self.qr_x_var, self.qr_y_var, self.qr_size_var, self.qr_foreground_var, self.qr_background_var, self.qr_label_offset_x_var, self.qr_label_offset_y_var, self.qr_z_var]:
            var.trace_add("write", lambda *_: self.schedule_qr_group_stage_only())

        self.refresh_display_text_storage()
        self.refresh_top_row_editor()
        self.load_qr_group_into_controls()
        self.refresh_top_dropdown_values()

    def theme_colors(self) -> dict:
        return ensure_theme_color_storage(self.store.data)

    def theme_color(self, role: str) -> str:
        defaults = default_theme_colors()
        return normalize_hex_color(str(self.theme_colors().get(role, defaults.get(role, "#ffffff"))), defaults.get(role, "#ffffff"))

    def build_colors_tab(self, frame: ttk.Frame) -> None:
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        canvas = tk.Canvas(frame, width=790, height=390, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        content = ttk.Frame(canvas, padding=(2, 0, 8, 6))
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def sync_scrollregion(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(window_id, width=max(760, canvas.winfo_width()))
        content.bind("<Configure>", sync_scrollregion)
        canvas.bind("<Configure>", sync_scrollregion)

        content.columnconfigure(0, weight=1)
        ttk.Label(content, text="Bitninja Dark Theme Colors", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            content,
            text="Select one source color, edit its hex value if needed, then use the action buttons below to apply that color to a console role. The selection is held without a polling loop when you switch tabs.",
            wraplength=750,
        ).grid(row=1, column=0, sticky="w", pady=(2, 7))

        palette = ttk.Frame(content)
        palette.grid(row=2, column=0, sticky="ew")
        palette.columnconfigure(0, weight=1)
        palette.columnconfigure(1, weight=1)
        roles = list(BITNINJA_DARK_THEME)
        split = (len(roles) + 1) // 2
        for idx, role in enumerate(roles):
            column_group = 0 if idx < split else 1
            local_row = idx if idx < split else idx - split
            cell = ttk.Frame(palette)
            cell.grid(row=local_row, column=column_group, sticky="ew", padx=(0, 10) if column_group == 0 else (10, 0), pady=1)
            cell.columnconfigure(1, weight=1)
            ttk.Checkbutton(cell, variable=self.theme_role_selected_vars[role], command=lambda r=role: self.on_theme_role_checkbox(r)).grid(row=0, column=0, sticky="w")
            ttk.Label(cell, text=BITNINJA_DARK_THEME[role]["label"], width=21).grid(row=0, column=1, sticky="w")
            entry = ttk.Entry(cell, textvariable=self.theme_color_vars[role], width=9)
            entry.grid(row=0, column=2, sticky="e", padx=(4, 3))
            entry.bind("<Return>", lambda _event, r=role: self.apply_theme_entry_role(r))
            swatch = tk.Label(cell, width=2, relief="sunken", bg=self.theme_color_vars[role].get())
            swatch.grid(row=0, column=3, sticky="e")
            self.theme_swatch_labels[role] = swatch

        center = ttk.LabelFrame(content, text="Color Selection / Last Action", padding=6)
        center.grid(row=3, column=0, sticky="ew", pady=(8, 6))
        center.columnconfigure(0, weight=1)
        ttk.Label(center, textvariable=self.color_status_var, wraplength=470).grid(row=0, column=0, sticky="w")
        ttk.Button(center, text="Apply Edited Color", command=self.apply_selected_theme_entry).grid(row=0, column=1, padx=(6, 3))
        self.color_cancel_button = ttk.Button(center, text="Cancel", command=self.cancel_theme_selection, state="disabled")
        self.color_cancel_button.grid(row=0, column=2, padx=(3, 0))

        actions = ttk.LabelFrame(content, text="Apply selected color to console element", padding=6)
        actions.grid(row=4, column=0, sticky="ew")
        action_labels = {
            "output_background": "Output BG", "main_panel_background": "Main Panel", "info_panel_background": "Top Rows Panel", "blank_background": "Blank BG",
            "main_border": "Main Border", "standard_line": "Divider Line", "top_row_line": "Top Row Line",
            "box_background": "Box BG", "box_border": "Box Border",
            "standard_text": "Standard Text", "secondary_text": "Secondary Text", "muted_text": "Muted Text", "dim_text": "Dim Text", "box_text": "Box Text", "top_row_text": "Top Row Text",
            "accent": "Accent / Scanner", "scan_trail": "Scan Trail", "qr_outline": "QR Outline",
        }
        groups = ["Canvas", "Lines", "Boxes", "Text", "Accent"]
        grouped = {group: [] for group in groups}
        for role, spec in BITNINJA_DARK_THEME.items():
            grouped.setdefault(spec["group"], []).append(role)
        row = 0
        for group in groups:
            ttk.Label(actions, text=group, width=8).grid(row=row, column=0, sticky="nw", pady=2)
            button_box = ttk.Frame(actions)
            button_box.grid(row=row, column=1, sticky="w", pady=2)
            for idx, role in enumerate(grouped.get(group, [])):
                ttk.Button(button_box, text=action_labels[role], command=lambda r=role: self.apply_selected_theme_color_to_role(r)).grid(row=idx // 4, column=idx % 4, sticky="ew", padx=(0, 3), pady=1)
            row += 1

        reset_row = ttk.Frame(content)
        reset_row.grid(row=5, column=0, sticky="ew", pady=(7, 0))
        ttk.Button(reset_row, text="Reset Full Theme: Bitninja Dark", command=self.reset_bitninja_dark_theme).pack(side="left")
        ttk.Label(reset_row, text="Colors only; content and positions stay intact.").pack(side="left", padx=8)

    def refresh_theme_swatch(self, role: str) -> None:
        swatch = self.theme_swatch_labels.get(role)
        if swatch is not None:
            swatch.configure(bg=normalize_hex_color(self.theme_color_vars[role].get(), self.theme_color(role)))

    def restore_theme_selection(self) -> None:
        role = self.selected_theme_role_var.get()
        self._syncing_theme_selection = True
        try:
            for key, var in self.theme_role_selected_vars.items():
                var.set(key == role and key in BITNINJA_DARK_THEME)
        finally:
            self._syncing_theme_selection = False
        if role in BITNINJA_DARK_THEME:
            self.color_cancel_button.configure(state="normal")
        else:
            self.selected_theme_role_var.set("")
            self.color_cancel_button.configure(state="disabled")
        for key in BITNINJA_DARK_THEME:
            self.refresh_theme_swatch(key)

    def on_theme_role_checkbox(self, role: str) -> None:
        if self._syncing_theme_selection:
            return
        selected = bool(self.theme_role_selected_vars[role].get())
        self._syncing_theme_selection = True
        try:
            for key, var in self.theme_role_selected_vars.items():
                var.set(selected and key == role)
        finally:
            self._syncing_theme_selection = False
        if selected:
            self.selected_theme_role_var.set(role)
            text = f"Selected source color: {BITNINJA_DARK_THEME[role]['label']} {self.theme_color_vars[role].get()}"
            self.color_cancel_button.configure(state="normal")
        else:
            self.selected_theme_role_var.set("")
            text = "No color selected"
            self.color_cancel_button.configure(state="disabled")
        scratch = self.store.data["under_header"].setdefault("scratch", {})
        scratch["color_selected_role"] = self.selected_theme_role_var.get()
        scratch["color_last_action"] = text
        self.color_status_var.set(text)

    def cancel_theme_selection(self) -> None:
        self._syncing_theme_selection = True
        try:
            for var in self.theme_role_selected_vars.values():
                var.set(False)
        finally:
            self._syncing_theme_selection = False
        self.selected_theme_role_var.set("")
        self.color_status_var.set("Selection cancelled; theme colors were not changed")
        self.color_cancel_button.configure(state="disabled")
        scratch = self.store.data["under_header"].setdefault("scratch", {})
        scratch["color_selected_role"] = ""
        scratch["color_last_action"] = self.color_status_var.get()

    def apply_theme_entry_role(self, role: str) -> None:
        self._syncing_theme_selection = True
        try:
            for key, var in self.theme_role_selected_vars.items():
                var.set(key == role)
        finally:
            self._syncing_theme_selection = False
        self.selected_theme_role_var.set(role)
        self.apply_selected_theme_entry()

    def apply_selected_theme_entry(self) -> None:
        role = self.selected_theme_role_var.get()
        if role not in BITNINJA_DARK_THEME:
            self.color_status_var.set("Select a color checkbox first, or use an element action button to open the picker")
            return
        self.apply_theme_role_color(role, self.theme_color_vars[role].get(), f"Edited {BITNINJA_DARK_THEME[role]['label']}")

    def apply_selected_theme_color_to_role(self, target_role: str) -> None:
        source_role = self.selected_theme_role_var.get()
        if source_role in BITNINJA_DARK_THEME:
            color = self.theme_color_vars[source_role].get()
            self.apply_theme_role_color(target_role, color, f"Copied {BITNINJA_DARK_THEME[source_role]['label']} to {BITNINJA_DARK_THEME[target_role]['label']}")
            return
        self.prompt_theme_color_for_role(target_role)

    def prompt_theme_color_for_role(self, target_role: str) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Apply color to {BITNINJA_DARK_THEME[target_role]['label']}")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill="both", expand=True)
        preset_var = tk.StringVar(value=next(iter(THEME_PRESET_COLORS)))
        color_var = tk.StringVar(value=self.theme_color(target_role))
        ttk.Label(frame, text="Preset color").grid(row=0, column=0, sticky="w", pady=2)
        preset = ttk.Combobox(frame, state="readonly", values=list(THEME_PRESET_COLORS), textvariable=preset_var, width=24)
        preset.grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(frame, text="Hex color").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(frame, textvariable=color_var, width=14).grid(row=1, column=1, sticky="w", pady=2)

        def preset_changed(_event=None):
            color_var.set(THEME_PRESET_COLORS.get(preset_var.get(), color_var.get()))
        preset.bind("<<ComboboxSelected>>", preset_changed)

        def choose_custom():
            _rgb, chosen = colorchooser.askcolor(color=color_var.get(), title="Choose console color")
            if chosen:
                color_var.set(chosen.lower())

        def accept():
            self.apply_theme_role_color(target_role, color_var.get(), f"Applied picker color to {BITNINJA_DARK_THEME[target_role]['label']}")
            dlg.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(9, 0))
        ttk.Button(buttons, text="Choose Custom", command=choose_custom).pack(side="left")
        ttk.Button(buttons, text="Accept", command=accept).pack(side="left", padx=(10, 4))
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side="left", padx=4)

    def apply_theme_role_color(self, role: str, color: str, message: str = "Theme color applied") -> None:
        if role not in BITNINJA_DARK_THEME:
            return
        color = normalize_hex_color(color, BITNINJA_DARK_THEME[role]["color"])
        colors = self.theme_colors()
        colors[role] = color
        self.theme_color_vars[role].set(color)
        self.refresh_theme_swatch(role)
        self.apply_theme_role_mappings(role, color)
        self.store.mark_dirty("theme-color-updated")
        self.redraw_output()
        self.color_status_var.set(f"{message}: {color}")
        scratch = self.store.data["under_header"].setdefault("scratch", {})
        scratch["color_last_action"] = self.color_status_var.get()
        self.schedule_autosave()

    def apply_theme_role_mappings(self, role: str, color: str) -> None:
        if role == "output_background":
            self.store.data["header"]["output"]["background"] = color
        elif role == "top_row_line":
            for row in self.top_rows():
                row["line_color"] = color
        elif role == "standard_text":
            obj = self.display_text_object_by_id("title_main")
            if obj:
                obj["color"] = color
        elif role == "top_row_text":
            for row in self.top_rows():
                for option in row.get("options", []):
                    option["color"] = color
        elif role == "secondary_text":
            for object_id in ["row_source_type", "row_confidence", "row_verdict", "qr_label", "host_label", "box_claim_label", "box_evidence_label", "box_question_label"]:
                obj = self.display_text_object_by_id(object_id)
                if obj:
                    obj["color"] = color
        elif role == "muted_text":
            obj = self.display_text_object_by_id("right_brand")
            if obj:
                obj["color"] = color
        elif role == "dim_text":
            obj = self.display_text_object_by_id("right_subtitle")
            if obj:
                obj["color"] = color
        elif role == "accent":
            self.scanner_color_var.set(color)
            self.store.data["under_header"]["scanner_color"] = color
            for object_id in ["status_live", "activity_label", "scan_label"]:
                obj = self.display_text_object_by_id(object_id)
                if obj:
                    obj["color"] = color
            for row in self.top_rows():
                for option in row.get("options", []):
                    option["bar_color"] = color
        elif role == "qr_outline":
            self.qr_group()["outline"] = color
            self.qr_cache_key = None

    def reset_bitninja_dark_theme(self) -> None:
        colors = default_theme_colors()
        self.store.data["header"]["theme_colors"] = colors
        for role, spec in BITNINJA_DARK_THEME.items():
            self.theme_color_vars[role].set(spec["color"])
            self.refresh_theme_swatch(role)
            self.apply_theme_role_mappings(role, spec["color"])
        self.store.data["header"]["output"]["background"] = colors["output_background"]
        self.store.mark_dirty("theme-reset-bitninja-dark")
        self.redraw_output()
        self.color_status_var.set("Full output theme reset to Bitninja Dark")
        self.store.data["under_header"].setdefault("scratch", {})["color_last_action"] = self.color_status_var.get()
        self.schedule_autosave()

    def qr_group(self) -> dict:
        return ensure_qr_group_storage(self.store.data)

    def qr_label_position(self) -> tuple[int, int]:
        qr = self.qr_group()
        return (
            int(qr.get("x", QR_GROUP_DEFAULTS["x"])) + int(qr.get("label_offset_x", QR_GROUP_DEFAULTS["label_offset_x"])),
            int(qr.get("y", QR_GROUP_DEFAULTS["y"])) + int(qr.get("label_offset_y", QR_GROUP_DEFAULTS["label_offset_y"])),
        )

    def sync_qr_label_absolute_storage(self) -> None:
        label_obj = self.display_text_object_by_id("qr_label")
        if label_obj is None:
            return
        x, y = self.qr_label_position()
        label_obj["x"] = x
        label_obj["y"] = y

    def load_qr_group_into_controls(self) -> None:
        qr = self.qr_group()
        self._syncing_qr_vars = True
        try:
            self.qr_x_var.set(int(qr["x"]))
            self.qr_y_var.set(int(qr["y"]))
            self.qr_size_var.set(int(qr["size"]))
            self.qr_foreground_var.set(str(qr["foreground"]))
            self.qr_background_var.set(str(qr["background"]))
            self._syncing_qr_vars = True
            try:
                self.qr_label_offset_x_var.set(int(qr["label_offset_x"]))
                self.qr_label_offset_y_var.set(int(qr["label_offset_y"]))
            finally:
                self._syncing_qr_vars = False
            self.qr_z_var.set(int(qr["z"]))
        finally:
            self._syncing_qr_vars = False
        self.sync_qr_label_absolute_storage()

    def schedule_qr_group_stage_only(self) -> None:
        if self._syncing_qr_vars:
            return
        self.store.data["stage"]["save_body_pending"] = True
        self.store.mark_dirty("qr-group-stage-updated")
        self.schedule_autosave()

    def apply_qr_group_without_reschedule(self) -> bool:
        qr = self.qr_group()
        try:
            size = max(48, min(260, int(self.qr_size_var.get())))
            x = max(0, min(OUTPUT_WIDTH - size, int(self.qr_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT - size, int(self.qr_y_var.get())))
            offset_x = max(-OUTPUT_WIDTH, min(OUTPUT_WIDTH, int(self.qr_label_offset_x_var.get())))
            offset_y = max(-OUTPUT_HEIGHT, min(OUTPUT_HEIGHT, int(self.qr_label_offset_y_var.get())))
            z = max(-1000, min(1000, int(self.qr_z_var.get())))
        except (tk.TclError, ValueError):
            return False
        qr.update({
            "x": x,
            "y": y,
            "size": size,
            "label_offset_x": offset_x,
            "label_offset_y": offset_y,
            "z": z,
            "foreground": normalize_hex_color(self.qr_foreground_var.get(), "#000000"),
            "background": normalize_hex_color(self.qr_background_var.get(), "#ffffff"),
        })
        self._syncing_qr_vars = True
        try:
            self.qr_x_var.set(x)
            self.qr_y_var.set(y)
            self.qr_size_var.set(size)
            self.qr_label_offset_x_var.set(offset_x)
            self.qr_label_offset_y_var.set(offset_y)
            self.qr_z_var.set(z)
            self.qr_foreground_var.set(qr["foreground"])
            self.qr_background_var.set(qr["background"])
        finally:
            self._syncing_qr_vars = False
        self.sync_qr_label_absolute_storage()
        self.qr_cache_key = None
        self.store.mark_dirty("qr-group-updated")
        return True

    def apply_qr_group(self) -> None:
        if not self.apply_qr_group_without_reschedule():
            return
        self.load_selected_display_text_into_controls()
        self.redraw_output()
        self.status_var.set("QR group applied")
        self.schedule_autosave()

    def choose_qr_color(self, target: str) -> None:
        current = self.qr_foreground_var.get() if target == "foreground" else self.qr_background_var.get()
        _rgb, color = colorchooser.askcolor(color=current, title=f"Choose QR {target} color")
        if not color:
            return
        if target == "foreground":
            self.qr_foreground_var.set(color.lower())
        else:
            self.qr_background_var.set(color.lower())
        self.apply_qr_group()

    def nudge_qr_group(self, dx: int, dy: int) -> None:
        self.qr_x_var.set(int(self.qr_x_var.get()) + dx)
        self.qr_y_var.set(int(self.qr_y_var.get()) + dy)
        self.apply_qr_group()

    def nudge_qr_label(self, dx: int, dy: int) -> None:
        self.qr_label_offset_x_var.set(int(self.qr_label_offset_x_var.get()) + dx)
        self.qr_label_offset_y_var.set(int(self.qr_label_offset_y_var.get()) + dy)
        self.apply_qr_group()

    def nudge_qr_z(self, dz: int) -> None:
        self.qr_z_var.set(int(self.qr_z_var.get()) + dz)
        self.apply_qr_group()

    def bring_qr_to_front(self) -> None:
        max_layer_z = max([int(layer.get("z", 0)) for layer in self.store.active_card().get("layers", [])] or [0])
        self.qr_z_var.set(max_layer_z + 1)
        self.apply_qr_group()

    def pull_qr_to_back(self) -> None:
        self.qr_z_var.set(int(self.qr_group().get("default_z", QR_GROUP_DEFAULTS["default_z"])))
        self.apply_qr_group()

    def reset_qr_group_defaults(self) -> None:
        qr = self.qr_group()
        qr.clear()
        qr.update(copy.deepcopy(QR_GROUP_DEFAULTS))
        self.load_qr_group_into_controls()
        self.qr_cache_key = None
        self.store.mark_dirty("qr-group-reset-defaults")
        self.redraw_output()
        self.status_var.set("QR group reset to defaults")
        self.schedule_autosave()

    def top_rows(self) -> list[dict]:
        return ensure_top_row_storage(self.store.data)

    def top_row_by_id(self, row_id: str) -> dict | None:
        for row in self.top_rows():
            if row.get("id") == row_id:
                return row
        return None

    def top_row_by_field(self, field: str) -> dict | None:
        return self.top_row_by_id(TOP_ROW_FIELD_TO_ID.get(field, field))

    def top_row_by_label_id(self, label_id: str) -> dict | None:
        return self.top_row_by_id(TOP_ROW_LABEL_TO_ID.get(label_id, ""))

    def selected_top_row(self) -> dict | None:
        return self.top_row_by_id(self.selected_top_row_id_var.get())

    def selected_top_row_option(self) -> dict | None:
        row = self.selected_top_row()
        if not row:
            return None
        selected_id = self.selected_top_row_option_id_var.get()
        for option in row.get("options", []):
            if option.get("id") == selected_id:
                return option
        return None

    def top_row_option_by_text(self, row: dict | None, text: str) -> dict | None:
        if not row:
            return None
        wanted = str(text or "").strip().casefold()
        for option in row.get("options", []):
            if str(option.get("text", "")).strip().casefold() == wanted:
                return option
        return None

    def visible_top_row_values(self, row_id: str) -> list[str]:
        row = self.top_row_by_id(row_id)
        if not row:
            row = TOP_ROW_DEFAULTS_BY_ID.get(row_id)
            return list(row.get("options", [])) if row else []
        values = [str(opt.get("text", "")).strip() for opt in row.get("options", []) if opt.get("visible", True) and str(opt.get("text", "")).strip()]
        if not values:
            fallback = str(row.get("default_value", "Option")).strip() or "Option"
            values = [fallback]
        return values

    def refresh_top_dropdown_values(self) -> None:
        combos = [
            (getattr(self, "source_type_combo", None), "sourceType", self.source_type_var),
            (getattr(self, "confidence_combo", None), "confidence", self.confidence_var),
            (getattr(self, "verdict_combo", None), "verdict", self.verdict_var),
        ]
        for combo, row_id, var in combos:
            values = self.visible_top_row_values(row_id)
            if combo is not None:
                combo.configure(values=values)
            if not var.get().strip():
                var.set(values[0] if values else "")

    def ensure_current_card_values_are_options(self) -> None:
        fields = self.store.active_card().get("fields", {})
        changed = False
        for field, row_id in TOP_ROW_FIELD_TO_ID.items():
            value = str(fields.get(field, "")).strip()
            if not value:
                continue
            row = self.top_row_by_id(row_id)
            if row and self.top_row_option_by_text(row, value) is None:
                option = make_top_row_option(TOP_ROW_DEFAULTS_BY_ID[row_id], value, len(row.get("options", [])))
                option["created_from_card_value"] = True
                row.setdefault("options", []).append(option)
                changed = True
        if changed:
            self.store.mark_dirty("top-row-options-learned-card-values")

    def top_row_selector_label(self, row: dict) -> str:
        return str(row.get("label", row.get("id", "Top Row"))).strip() or "Top Row"

    def top_row_option_label(self, option: dict, index: int | None = None) -> str:
        prefix = f"{index + 1}. " if index is not None else ""
        text = str(option.get("text", "Option")).strip() or "Option"
        hidden = "  [hidden]" if option.get("visible", True) is False else ""
        return f"{prefix}{text}{hidden}"

    def refresh_top_row_editor(self) -> None:
        if self.top_row_selector is None or self.top_row_option_selector is None:
            return
        self.top_row_label_to_id = {}
        row_labels = []
        for row in self.top_rows():
            label = self.top_row_selector_label(row)
            self.top_row_label_to_id[label] = row.get("id", "")
            row_labels.append(label)
        self.top_row_selector.configure(values=row_labels)
        if not self.selected_top_row_id_var.get() and self.top_rows():
            self.selected_top_row_id_var.set(self.top_rows()[0].get("id", ""))
        current_row = self.selected_top_row()
        if current_row is None and self.top_rows():
            current_row = self.top_rows()[0]
            self.selected_top_row_id_var.set(current_row.get("id", ""))
        if current_row:
            self.selected_top_row_label_var.set(self.top_row_selector_label(current_row))
        self.refresh_top_row_option_selector()

    def refresh_top_row_option_selector(self) -> None:
        if self.top_row_option_selector is None:
            return
        row = self.selected_top_row()
        self.top_row_option_label_to_id = {}
        values = []
        if row:
            for idx, option in enumerate(row.get("options", [])):
                label = self.top_row_option_label(option, idx)
                base = label
                counter = 2
                while label in self.top_row_option_label_to_id:
                    label = f"{base} ({counter})"
                    counter += 1
                self.top_row_option_label_to_id[label] = option.get("id", "")
                values.append(label)
        self.top_row_option_selector.configure(values=values)
        current_id = self.selected_top_row_option_id_var.get()
        if row and not any(opt.get("id") == current_id for opt in row.get("options", [])):
            current_id = row.get("options", [{}])[0].get("id", "") if row.get("options") else ""
            self.selected_top_row_option_id_var.set(current_id)
        selected_label = ""
        for label, opt_id in self.top_row_option_label_to_id.items():
            if opt_id == self.selected_top_row_option_id_var.get():
                selected_label = label
                break
        if not selected_label and values:
            selected_label = values[0]
            self.selected_top_row_option_id_var.set(self.top_row_option_label_to_id[selected_label])
        self.selected_top_row_option_label_var.set(selected_label)
        self.load_selected_top_row_option_into_controls()

    def on_top_row_selected(self, _event=None) -> None:
        label = self.selected_top_row_label_var.get()
        row_id = self.top_row_label_to_id.get(label, "")
        if row_id:
            self.selected_top_row_id_var.set(row_id)
            row = self.selected_top_row()
            if row and row.get("options"):
                self.selected_top_row_option_id_var.set(row["options"][0].get("id", ""))
            self.refresh_top_row_option_selector()

    def on_top_row_option_selected(self, _event=None) -> None:
        label = self.selected_top_row_option_label_var.get()
        option_id = self.top_row_option_label_to_id.get(label, "")
        if option_id:
            self.selected_top_row_option_id_var.set(option_id)
        self.load_selected_top_row_option_into_controls()

    def load_selected_top_row_option_into_controls(self) -> None:
        option = self.selected_top_row_option()
        if not option:
            return
        self.top_row_option_text_var.set(str(option.get("text", "")))
        self.top_row_font_size_var.set(max(6, min(96, int(option.get("font_size", 15)))))
        self.top_row_text_color_var.set(normalize_hex_color(option.get("color", "#f0fff8"), "#f0fff8"))
        self.top_row_bar_color_var.set(normalize_hex_color(option.get("bar_color", "#00ff99"), "#00ff99"))
        self.top_row_x_var.set(max(0, min(OUTPUT_WIDTH, int(option.get("x", 200)))))
        self.top_row_y_var.set(max(0, min(OUTPUT_HEIGHT, int(option.get("y", 96)))))
        self.top_row_visible_var.set(bool(option.get("visible", True)))

    def schedule_top_row_stage_only(self) -> None:
        if self.selected_top_row_id_var.get() and self.selected_top_row_option_id_var.get():
            self.store.data["stage"]["save_body_pending"] = True
            self.store.mark_dirty("top-row-stage-updated")
            self.schedule_autosave()

    def apply_top_row_option_without_reschedule(self) -> bool:
        option = self.selected_top_row_option()
        if not option:
            return False
        try:
            option["font_size"] = max(6, min(96, int(self.top_row_font_size_var.get())))
            option["x"] = max(0, min(OUTPUT_WIDTH, int(self.top_row_x_var.get())))
            option["y"] = max(0, min(OUTPUT_HEIGHT, int(self.top_row_y_var.get())))
        except (tk.TclError, ValueError):
            return False
        old_text = str(option.get("text", "")).strip()
        option["text"] = (self.top_row_option_text_var.get().strip() or old_text or "Option")[:64]
        option["color"] = normalize_hex_color(self.top_row_text_color_var.get(), option.get("default_color", "#f0fff8"))
        option["bar_color"] = normalize_hex_color(self.top_row_bar_color_var.get(), option.get("default_bar_color", "#00ff99"))
        option["visible"] = bool(self.top_row_visible_var.get())
        # If a selected card currently uses the old option text, keep it synced to the renamed option.
        row = self.selected_top_row()
        if row and old_text and old_text != option["text"]:
            field = row.get("field", "")
            fields = self.store.active_card().setdefault("fields", {})
            if fields.get(field) == old_text:
                fields[field] = option["text"]
                if field == "sourceType":
                    self.source_type_var.set(option["text"])
                elif field == "confidence":
                    self.confidence_var.set(option["text"])
                elif field == "verdict":
                    self.verdict_var.set(option["text"])
        self.store.mark_dirty("top-row-option-applied")
        return True

    def apply_top_row_option(self) -> None:
        if not self.apply_top_row_option_without_reschedule():
            return
        self.refresh_top_dropdown_values()
        self.refresh_top_row_option_selector()
        self.redraw_output()
        self.schedule_autosave()
        self.status_var.set("Top row option applied")

    def add_top_row_option(self) -> None:
        row = self.selected_top_row()
        if not row:
            return
        text = self.top_row_option_text_var.get().strip() or "New Option"
        option = make_top_row_option(TOP_ROW_DEFAULTS_BY_ID.get(row.get("id", ""), row), text, len(row.get("options", [])))
        existing_ids = {opt.get("id") for opt in row.get("options", [])}
        base_id = option["id"]
        counter = 2
        while option["id"] in existing_ids:
            option["id"] = f"{base_id}-{counter}"
            counter += 1
        row.setdefault("options", []).append(option)
        self.selected_top_row_option_id_var.set(option["id"])
        self.store.mark_dirty("top-row-option-added")
        self.refresh_top_dropdown_values()
        self.refresh_top_row_option_selector()
        self.redraw_output()
        self.schedule_autosave()

    def duplicate_top_row_option(self) -> None:
        row = self.selected_top_row()
        option = self.selected_top_row_option()
        if not row or not option:
            return
        new_option = copy.deepcopy(option)
        new_option["id"] = f"{option.get('id', 'option')}-copy-{uuid.uuid4().hex[:6]}"
        new_option["text"] = self.unique_top_row_option_text(row, f"{option.get('text', 'Option')} Copy")
        row.setdefault("options", []).append(new_option)
        self.selected_top_row_option_id_var.set(new_option["id"])
        self.store.mark_dirty("top-row-option-duplicated")
        self.refresh_top_dropdown_values()
        self.refresh_top_row_option_selector()
        self.redraw_output()
        self.schedule_autosave()

    def unique_top_row_option_text(self, row: dict, desired: str) -> str:
        existing = {str(opt.get("text", "")).strip().casefold() for opt in row.get("options", [])}
        text = desired.strip() or "Option"
        if text.casefold() not in existing:
            return text[:64]
        counter = 2
        while True:
            candidate = f"{text} {counter}"
            if candidate.casefold() not in existing:
                return candidate[:64]
            counter += 1

    def move_top_row_option(self, direction: int) -> None:
        row = self.selected_top_row()
        option = self.selected_top_row_option()
        if not row or not option:
            return
        options = row.get("options", [])
        try:
            idx = options.index(option)
        except ValueError:
            return
        new_idx = max(0, min(len(options) - 1, idx + direction))
        if new_idx == idx:
            return
        options[idx], options[new_idx] = options[new_idx], options[idx]
        self.store.mark_dirty("top-row-option-moved")
        self.refresh_top_dropdown_values()
        self.refresh_top_row_option_selector()
        self.schedule_autosave()

    def delete_top_row_option(self) -> None:
        row = self.selected_top_row()
        option = self.selected_top_row_option()
        if not row or not option:
            return
        options = row.get("options", [])
        if len(options) <= 1:
            messagebox.showwarning("Cannot delete last option", "Each top row must keep at least one option.")
            return
        text = str(option.get("text", "Option"))
        if not messagebox.askyesno("Delete top row option", f"Delete this option?\n\n{text}"):
            return
        options.remove(option)
        if options:
            self.selected_top_row_option_id_var.set(options[min(0, len(options) - 1)].get("id", ""))
        self.store.mark_dirty("top-row-option-deleted")
        self.refresh_top_dropdown_values()
        self.refresh_top_row_option_selector()
        self.redraw_output()
        self.schedule_autosave()

    def show_top_row_option(self) -> None:
        option = self.selected_top_row_option()
        if not option:
            return
        option["visible"] = True
        self.top_row_visible_var.set(True)
        self.store.mark_dirty("top-row-option-shown")
        self.refresh_top_dropdown_values()
        self.refresh_top_row_option_selector()
        self.redraw_output()
        self.schedule_autosave()

    def hide_top_row_option(self) -> None:
        option = self.selected_top_row_option()
        if not option:
            return
        option["visible"] = False
        self.top_row_visible_var.set(False)
        self.store.mark_dirty("top-row-option-hidden")
        self.refresh_top_dropdown_values()
        self.refresh_top_row_option_selector()
        self.redraw_output()
        self.schedule_autosave()

    def use_selected_top_row_option_on_card(self) -> None:
        row = self.selected_top_row()
        option = self.selected_top_row_option()
        if not row or not option:
            return
        value = str(option.get("text", "")).strip()
        if not value:
            return
        field = row.get("field", "")
        if field == "sourceType":
            self.source_type_var.set(value)
        elif field == "confidence":
            self.confidence_var.set(value)
        elif field == "verdict":
            self.verdict_var.set(value)
        self.apply_editor_to_card()
        self.status_var.set("Option used on active card")

    def default_top_row_option(self) -> None:
        option = self.selected_top_row_option()
        if not option:
            return
        option["text"] = str(option.get("default_text", option.get("text", "Option")))
        option["color"] = normalize_hex_color(option.get("default_color", "#f0fff8"), "#f0fff8")
        option["bar_color"] = normalize_hex_color(option.get("default_bar_color", "#00ff99"), "#00ff99")
        option["font_size"] = int(option.get("default_font_size", 15))
        option["visible"] = True
        self.store.mark_dirty("top-row-option-defaulted")
        self.refresh_top_dropdown_values()
        self.refresh_top_row_option_selector()
        self.redraw_output()
        self.schedule_autosave()

    def reset_selected_top_row_defaults(self) -> None:
        row = self.selected_top_row()
        if not row:
            return
        row_id = row.get("id", "")
        default = TOP_ROW_DEFAULTS_BY_ID.get(row_id)
        if not default:
            return
        if not messagebox.askyesno("Reset row defaults", "Reset this top row option list back to the default options?"):
            return
        fresh = default_top_rows()
        fresh_row = next((item for item in fresh if item.get("id") == row_id), None)
        if not fresh_row:
            return
        row.clear()
        row.update(fresh_row)
        self.selected_top_row_option_id_var.set(row.get("options", [{}])[0].get("id", ""))
        self.store.mark_dirty("top-row-defaults-reset")
        self.refresh_top_dropdown_values()
        self.refresh_top_row_editor()
        self.redraw_output()
        self.schedule_autosave()

    def choose_top_row_color(self, target: str = "text") -> None:
        from tkinter import colorchooser
        current = self.top_row_bar_color_var.get() if target == "bar" else self.top_row_text_color_var.get()
        _rgb, hex_color = colorchooser.askcolor(color=current, title="Choose top row color")
        if not hex_color:
            return
        if target == "bar":
            self.top_row_bar_color_var.set(hex_color.lower())
        else:
            self.top_row_text_color_var.set(hex_color.lower())
        self.apply_top_row_option()

    def nudge_top_row_option(self, dx: int, dy: int) -> None:
        option = self.selected_top_row_option()
        if not option:
            return
        option["x"] = max(0, min(OUTPUT_WIDTH, int(option.get("x", 200)) + dx))
        option["y"] = max(0, min(OUTPUT_HEIGHT, int(option.get("y", 96)) + dy))
        self.top_row_x_var.set(int(option["x"]))
        self.top_row_y_var.set(int(option["y"]))
        self.store.mark_dirty("top-row-option-nudged")
        self.redraw_output()
        self.schedule_autosave()

    def display_text_objects(self) -> list[dict]:
        return ensure_display_text_storage(self.store.data)

    def selected_display_text_object(self) -> dict | None:
        selected_id = self.selected_display_text_id_var.get()
        for obj in self.display_text_objects():
            if obj.get("id") == selected_id:
                return obj
        return None

    def display_text_object_by_id(self, object_id: str) -> dict | None:
        for obj in self.display_text_objects():
            if obj.get("id") == object_id:
                return obj
        return None

    def display_text_storage_label(self, obj: dict) -> str:
        label = str(obj.get("label", obj.get("id", "Display Text"))).strip() or "Display Text"
        hidden = "  [hidden]" if obj.get("visible", True) is False else ""
        border = "  [border]" if obj.get("border_enabled", False) else ""
        return f"{label}{hidden}{border}"

    def refresh_display_text_storage(self) -> None:
        if self.display_text_storage_listbox is None:
            return
        self.display_text_storage_listbox.delete(0, "end")
        self.display_text_label_to_id = {}
        values = []
        for obj in self.display_text_objects():
            label = self.display_text_storage_label(obj)
            base = label
            counter = 2
            while label in self.display_text_label_to_id:
                label = f"{base} ({counter})"
                counter += 1
            self.display_text_label_to_id[label] = obj.get("id", "")
            values.append(label)
            self.display_text_storage_listbox.insert("end", label)
        current_id = self.selected_display_text_id_var.get()
        current_idx = None
        if current_id:
            for idx, obj in enumerate(self.display_text_objects()):
                if obj.get("id") == current_id:
                    current_idx = idx
                    break
        if current_idx is None and values:
            current_idx = 0
            self.selected_display_text_id_var.set(self.display_text_objects()[0].get("id", ""))
        if current_idx is not None:
            try:
                self.display_text_storage_listbox.selection_clear(0, "end")
                self.display_text_storage_listbox.selection_set(current_idx)
                self.display_text_storage_listbox.see(current_idx)
                self.selected_display_text_label_var.set(values[current_idx])
            except tk.TclError:
                pass
        self.load_selected_display_text_into_controls()

    def on_display_text_selected(self, _event=None) -> None:
        if self.display_text_storage_listbox is None:
            return
        selection = self.display_text_storage_listbox.curselection()
        if not selection:
            return
        label = self.display_text_storage_listbox.get(selection[0])
        selected_id = self.display_text_label_to_id.get(label, "")
        self.selected_display_text_id_var.set(selected_id)
        self.selected_display_text_label_var.set(label)
        self.load_selected_display_text_into_controls()

    def display_text_content_value(self) -> str:
        if self.display_text_value_text is None:
            return ""
        return self.display_text_value_text.get("1.0", "end").rstrip()

    def load_selected_display_text_into_controls(self) -> None:
        obj = self.selected_display_text_object()
        if not obj:
            return
        if obj.get("id") == "qr_label":
            linked_x, linked_y = self.qr_label_position()
            obj["x"], obj["y"] = linked_x, linked_y
        self.display_text_x_var.set(int(obj.get("x", 0)))
        self.display_text_y_var.set(int(obj.get("y", 0)))
        self.display_text_color_var.set(normalize_hex_color(obj.get("color", obj.get("default_color", "#e8fff5"))))
        self.display_text_border_enabled_var.set(bool(obj.get("border_enabled", False)))
        self.display_text_border_color_var.set(normalize_hex_color(obj.get("border_color", obj.get("default_border_color", "#26333a")), "#26333a"))
        self.display_text_font_family_var.set(str(obj.get("font_family", obj.get("default_font_family", "TkDefaultFont"))) or "TkDefaultFont")
        self.display_text_font_size_var.set(max(6, min(96, int(obj.get("font_size", obj.get("default_font_size", 12))))))
        self.display_text_font_weight_var.set(str(obj.get("font_weight", obj.get("default_font_weight", "normal"))) or "normal")
        self.display_text_font_slant_var.set(str(obj.get("font_slant", obj.get("default_font_slant", "roman"))) or "roman")
        self.display_text_visible_var.set(bool(obj.get("visible", True)))
        if self.display_text_value_text is not None:
            self.display_text_value_text.delete("1.0", "end")
            self.display_text_value_text.insert("1.0", str(obj.get("text", obj.get("default_text", ""))))
            self.display_text_value_text.edit_modified(False)

    def schedule_display_text_stage_only(self) -> None:
        if self.selected_display_text_id_var.get():
            self.store.data["stage"]["save_body_pending"] = True
            self.store.mark_dirty("display-text-stage-updated")
            self.schedule_autosave()

    def on_display_text_focus_out(self, _event=None) -> None:
        self.apply_display_text_editor()

    def on_display_text_modified(self, _event=None) -> None:
        if self.display_text_value_text is None:
            return
        if self.display_text_value_text.edit_modified():
            self.schedule_display_text_stage_only()
            self.display_text_value_text.edit_modified(False)

    def apply_display_text_editor_without_reschedule(self) -> bool:
        obj = self.selected_display_text_object()
        if not obj:
            return False
        try:
            obj["x"] = max(0, min(OUTPUT_WIDTH, int(self.display_text_x_var.get())))
            obj["y"] = max(0, min(OUTPUT_HEIGHT, int(self.display_text_y_var.get())))
            obj["font_size"] = max(6, min(96, int(self.display_text_font_size_var.get())))
        except (tk.TclError, ValueError):
            return False
        obj["text"] = self.display_text_content_value()
        obj["color"] = normalize_hex_color(self.display_text_color_var.get(), obj.get("default_color", "#e8fff5"))
        obj["border_enabled"] = bool(self.display_text_border_enabled_var.get())
        obj["border_color"] = normalize_hex_color(self.display_text_border_color_var.get(), obj.get("default_border_color", "#26333a"))
        obj["font_family"] = self.display_text_font_family_var.get().strip() or obj.get("default_font_family", "TkDefaultFont")
        obj["font_weight"] = self.display_text_font_weight_var.get() if self.display_text_font_weight_var.get() in {"normal", "bold"} else "normal"
        obj["font_slant"] = self.display_text_font_slant_var.get() if self.display_text_font_slant_var.get() in {"roman", "italic"} else "roman"
        obj["visible"] = bool(self.display_text_visible_var.get())
        if obj.get("id") == "qr_label":
            qr = self.qr_group()
            qr["label_offset_x"] = int(obj["x"]) - int(qr.get("x", QR_GROUP_DEFAULTS["x"]))
            qr["label_offset_y"] = int(obj["y"]) - int(qr.get("y", QR_GROUP_DEFAULTS["y"]))
            self._syncing_qr_vars = True
            try:
                self.qr_label_offset_x_var.set(int(qr["label_offset_x"]))
                self.qr_label_offset_y_var.set(int(qr["label_offset_y"]))
            finally:
                self._syncing_qr_vars = False
        self.store.mark_dirty("display-text-updated")
        return True

    def apply_display_text_editor(self) -> None:
        if not self.apply_display_text_editor_without_reschedule():
            return
        self.refresh_display_text_storage()
        self.redraw_output()
        self.status_var.set("Display text applied")
        self.schedule_autosave()

    def choose_display_color(self, target: str) -> None:
        current = self.display_text_border_color_var.get() if target == "border" else self.display_text_color_var.get()
        _rgb, hex_color = colorchooser.askcolor(color=current, title="Choose RGB color")
        if not hex_color:
            return
        if target == "border":
            self.display_text_border_color_var.set(hex_color.lower())
        else:
            self.display_text_color_var.set(hex_color.lower())
        self.apply_display_text_editor()

    def default_display_text(self) -> None:
        obj = self.selected_display_text_object()
        if not obj or self.display_text_value_text is None:
            return
        self.display_text_value_text.delete("1.0", "end")
        self.display_text_value_text.insert("1.0", str(obj.get("default_text", DISPLAY_TEXT_DEFAULTS_BY_ID.get(obj.get("id", ""), {}).get("text", ""))))
        self.apply_display_text_editor()

    def default_display_color(self) -> None:
        obj = self.selected_display_text_object()
        if not obj:
            return
        self.display_text_color_var.set(normalize_hex_color(obj.get("default_color", "#e8fff5")))
        self.display_text_border_color_var.set(normalize_hex_color(obj.get("default_border_color", obj.get("default_color", "#e8fff5"))))
        self.apply_display_text_editor()

    def default_display_font(self) -> None:
        obj = self.selected_display_text_object()
        if not obj:
            return
        self.display_text_font_family_var.set(str(obj.get("default_font_family", "TkDefaultFont")))
        self.display_text_font_size_var.set(int(obj.get("default_font_size", 12)))
        self.display_text_font_weight_var.set(str(obj.get("default_font_weight", "normal")))
        self.display_text_font_slant_var.set(str(obj.get("default_font_slant", "roman")))
        self.apply_display_text_editor()

    def choose_display_font(self) -> None:
        obj = self.selected_display_text_object()
        if not obj:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("Display Text Font")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        fam_var = tk.StringVar(value=self.display_text_font_family_var.get() or "TkDefaultFont")
        size_var = tk.IntVar(value=int(self.display_text_font_size_var.get()))
        bold_var = tk.BooleanVar(value=self.display_text_font_weight_var.get() == "bold")
        italic_var = tk.BooleanVar(value=self.display_text_font_slant_var.get() == "italic")
        families = sorted(set(tkfont.families(self.root)))
        if "TkDefaultFont" not in families:
            families.insert(0, "TkDefaultFont")
        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Family").grid(row=0, column=0, sticky="w", pady=2)
        family_combo = ttk.Combobox(frame, textvariable=fam_var, values=families, width=34)
        family_combo.grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(frame, text="Size").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(frame, from_=6, to=96, textvariable=size_var, width=8).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Checkbutton(frame, text="Bold", variable=bold_var).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(frame, text="Italic", variable=italic_var).grid(row=2, column=1, sticky="w", pady=2)

        def apply_and_close() -> None:
            self.display_text_font_family_var.set(fam_var.get().strip() or "TkDefaultFont")
            self.display_text_font_size_var.set(max(6, min(96, int(size_var.get()))))
            self.display_text_font_weight_var.set("bold" if bold_var.get() else "normal")
            self.display_text_font_slant_var.set("italic" if italic_var.get() else "roman")
            self.apply_display_text_editor()
            dlg.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(buttons, text="Apply Font", command=apply_and_close).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(side="left", padx=6)
        family_combo.focus_set()

    def show_display_text(self) -> None:
        obj = self.selected_display_text_object()
        if not obj:
            return
        self.display_text_visible_var.set(True)
        obj["visible"] = True
        self.store.mark_dirty("display-text-shown")
        self.refresh_display_text_storage()
        self.redraw_output()
        self.schedule_autosave()

    def hide_display_text(self) -> None:
        obj = self.selected_display_text_object()
        if not obj:
            return
        self.display_text_visible_var.set(False)
        obj["visible"] = False
        self.store.mark_dirty("display-text-hidden")
        self.refresh_display_text_storage()
        self.redraw_output()
        self.schedule_autosave()

    def display_text_font_tuple(self, obj: dict):
        family = str(obj.get("font_family", "TkDefaultFont")) or "TkDefaultFont"
        size = max(6, min(96, int(obj.get("font_size", 12))))
        styles = []
        if obj.get("font_weight") == "bold":
            styles.append("bold")
        if obj.get("font_slant") == "italic":
            styles.append("italic")
        return (family, size, *styles)

    def display_text_render_value(self, obj: dict, runtime_vars: dict | None = None, override_text: str | None = None) -> str:
        text = str(obj.get("text", obj.get("default_text", ""))) if override_text is None else str(override_text)
        if runtime_vars:
            try:
                text = text.format(**runtime_vars)
            except Exception:
                pass
        return text

    def draw_display_text(self, canvas: tk.Canvas, object_id: str, runtime_vars: dict | None = None, override_text: str | None = None, override_x: int | None = None, override_y: int | None = None):
        obj = self.display_text_object_by_id(object_id)
        if not obj or obj.get("visible", True) is False:
            return None
        text = self.display_text_render_value(obj, runtime_vars=runtime_vars, override_text=override_text)
        if not text.strip():
            return None
        x = int(obj.get("x", 0) if override_x is None else override_x)
        y = int(obj.get("y", 0) if override_y is None else override_y)
        anchor = str(obj.get("anchor", "center")) or "center"
        color = normalize_hex_color(obj.get("color", obj.get("default_color", "#e8fff5")))
        item = canvas.create_text(x, y, anchor=anchor, text=text, fill=color, font=self.display_text_font_tuple(obj))
        if obj.get("border_enabled", False):
            bbox = canvas.bbox(item)
            if bbox:
                pad = 4
                border = canvas.create_rectangle(
                    bbox[0] - pad,
                    bbox[1] - pad,
                    bbox[2] + pad,
                    bbox[3] + pad,
                    fill="",
                    outline=normalize_hex_color(obj.get("border_color", obj.get("default_border_color", color)), color),
                    width=1,
                )
                canvas.tag_lower(border, item)
        return item

    def display_text_size_for_alignment(self, obj: dict | None) -> tuple[int, int]:
        if not obj:
            return (0, 0)
        text = self.display_text_render_value(obj, runtime_vars={"host": "example.com"})
        font_spec = self.display_text_font_tuple(obj)
        try:
            font = tkfont.Font(root=self.root, font=font_spec)
            width = max(10, font.measure(text))
            height = max(10, font.metrics("linespace"))
            return (width, height)
        except Exception:
            return (160, 24)

    def set_display_text_position(self, obj: dict | None, x: int, y: int, reason: str) -> None:
        if not obj:
            return
        w, h = self.display_text_size_for_alignment(obj)
        x = max(0, min(OUTPUT_WIDTH - min(w, OUTPUT_WIDTH), int(x)))
        y = max(0, min(OUTPUT_HEIGHT - min(h, OUTPUT_HEIGHT), int(y)))
        obj["x"] = x
        obj["y"] = y
        if obj.get("id") == "qr_label":
            qr = self.qr_group()
            qr["label_offset_x"] = x - int(qr.get("x", QR_GROUP_DEFAULTS["x"]))
            qr["label_offset_y"] = y - int(qr.get("y", QR_GROUP_DEFAULTS["y"]))
            self._syncing_qr_vars = True
            try:
                self.qr_label_offset_x_var.set(int(qr["label_offset_x"]))
                self.qr_label_offset_y_var.set(int(qr["label_offset_y"]))
            finally:
                self._syncing_qr_vars = False
        self.display_text_x_var.set(x)
        self.display_text_y_var.set(y)
        self.store.mark_dirty(reason)
        self.refresh_display_text_storage()
        self.redraw_output()
        self.schedule_autosave()

    def nudge_display_text(self, dx: int, dy: int) -> None:
        obj = self.selected_display_text_object()
        if not obj:
            return
        self.set_display_text_position(obj, int(obj.get("x", 0)) + dx, int(obj.get("y", 0)) + dy, "display-text-nudged")

    def snap_display_text(self, target: str) -> None:
        obj = self.selected_display_text_object()
        if not obj:
            return
        safe_x1, safe_y1 = 24, 24
        safe_x2, safe_y2 = OUTPUT_WIDTH - 24, OUTPUT_HEIGHT - 24
        w, h = self.display_text_size_for_alignment(obj)
        x = int(obj.get("x", 0))
        y = int(obj.get("y", 0))
        if target == "left":
            x = safe_x1
        elif target == "center_x":
            x = safe_x1 + ((safe_x2 - safe_x1 - w) // 2)
        elif target == "right":
            x = safe_x2 - w
        elif target == "top":
            y = safe_y1
        elif target == "center_y":
            y = safe_y1 + ((safe_y2 - safe_y1 - h) // 2)
        elif target == "bottom":
            y = safe_y2 - h
        self.set_display_text_position(obj, x, y, "display-text-snapped")

    def active_deck_border_type(self) -> str:
        card = self.store.active_card()
        return normalize_deck_border_type(card.get("deck_border_type", ""))

    def sync_deck_border_checkboxes(self) -> None:
        selected = self.active_deck_border_type()
        self._syncing_deck_border_vars = True
        try:
            for key, var in self.deck_border_vars.items():
                var.set(key == selected)
        finally:
            self._syncing_deck_border_vars = False

    def on_deck_border_checkbox(self, selected: str) -> None:
        if self._syncing_deck_border_vars:
            return
        selected = normalize_deck_border_type(selected)
        card = self.store.active_card()
        turn_on = bool(self.deck_border_vars.get(selected) and self.deck_border_vars[selected].get())
        card["deck_border_type"] = selected if turn_on else ""
        self.sync_deck_border_checkboxes()
        self.store.mark_dirty("deck-button-border-updated")
        self.refresh_deck_buttons()
        self.schedule_autosave()

    def clear_deck_border(self) -> None:
        self.store.active_card()["deck_border_type"] = ""
        self.sync_deck_border_checkboxes()
        self.store.mark_dirty("deck-button-border-cleared")
        self.refresh_deck_buttons()
        self.schedule_autosave()

    def refresh_deck_buttons(self) -> None:
        if self.deck_button_frame is None:
            return
        for child in self.deck_button_frame.winfo_children():
            child.destroy()
        self.card_buttons = {}
        self.card_button_frames = {}
        active_id = self.store.data["header"].get("active_card_id", "")
        for card in self.store.cards()[:self.max_deck_buttons]:
            cid = card.get("id", "")
            label = card.get("label", cid or "Card")
            text = ("▶ " if cid == active_id else "  ") + label
            border_type = normalize_deck_border_type(card.get("deck_border_type", ""))
            border_color = DECK_BORDER_STYLES.get(border_type, {}).get("color", "#4b4f56")
            outer = tk.Frame(self.deck_button_frame, bg=border_color, bd=0, highlightthickness=0)
            outer.pack(fill="x", pady=3)
            btn = ttk.Button(outer, text=text, command=lambda selected=cid: self.on_deck_button_clicked(selected), width=24)
            if border_type:
                btn.pack(fill="x", padx=DECK_BORDER_WIDTH, pady=DECK_BORDER_WIDTH)
            else:
                btn.pack(fill="x")
            self.card_buttons[cid] = btn
            self.card_button_frames[cid] = outer
        self.refresh_deck_storage()

    def refresh_deck_storage(self) -> None:
        if self.deck_storage_listbox is None:
            return
        self.deck_storage_listbox.delete(0, "end")
        self.deck_storage_ids = []
        for idx, card in enumerate(self.store.cards()[self.max_deck_buttons:], start=self.max_deck_buttons):
            cid = card.get("id", "")
            label = card.get("label", cid or "Card")
            active_mark = "▶ " if cid == self.store.data["header"].get("active_card_id", "") else "  "
            self.deck_storage_ids.append(cid)
            self.deck_storage_listbox.insert("end", f"{active_mark}{idx + 1}. {label}")

    def selected_storage_card_id(self) -> str | None:
        if self.deck_storage_listbox is None:
            return None
        selection = self.deck_storage_listbox.curselection()
        if not selection:
            return None
        idx = selection[0]
        if idx < 0 or idx >= len(self.deck_storage_ids):
            return None
        return self.deck_storage_ids[idx]

    def card_index_by_id(self, card_id: str) -> int | None:
        for idx, card in enumerate(self.store.cards()):
            if card.get("id") == card_id:
                return idx
        return None

    def swap_card_positions(self, first_id: str, second_id: str) -> bool:
        first_idx = self.card_index_by_id(first_id)
        second_idx = self.card_index_by_id(second_id)
        if first_idx is None or second_idx is None or first_idx == second_idx:
            return False
        cards = self.store.cards()
        cards[first_idx], cards[second_idx] = cards[second_idx], cards[first_idx]
        return True

    def swap_storage_with_active(self) -> None:
        storage_id = self.selected_storage_card_id()
        if not storage_id:
            self.status_var.set("Select a storage card first")
            return
        active_id = self.store.data["header"].get("active_card_id", "")
        if self.swap_card_positions(storage_id, active_id):
            self.store.set_active_card(storage_id)
            self.refresh_after_deck_change("deck-storage-swapped-with-active")
            self.status_var.set("Swapped storage card with active card")

    def arm_storage_swap(self, activate_after_swap: bool) -> None:
        storage_id = self.selected_storage_card_id()
        if not storage_id:
            self.status_var.set("Select a storage card first")
            return
        self.pending_deck_swap = {"storage_id": storage_id, "activate": bool(activate_after_swap)}
        mode = "Swap Click" if activate_after_swap else "Silent Swap Click"
        self.status_var.set(f"{mode}: click a sidebar deck button")

    def on_deck_button_clicked(self, card_id: str) -> None:
        if self.pending_deck_swap:
            storage_id = self.pending_deck_swap.get("storage_id", "")
            activate = bool(self.pending_deck_swap.get("activate", True))
            previous_active = self.store.data["header"].get("active_card_id", "")
            self.pending_deck_swap = None
            if storage_id and self.swap_card_positions(storage_id, card_id):
                if activate:
                    self.store.set_active_card(storage_id)
                    self.load_active_card_into_editor()
                    self.redraw_output()
                else:
                    self.store.set_active_card(previous_active)
                self.refresh_deck_buttons()
                self.store.mark_dirty("deck-storage-swap-click")
                self.schedule_autosave()
                self.status_var.set("Deck storage swap complete")
                return
        self.select_card(card_id)

    def unique_card_id(self, prefix: str) -> str:
        existing = {card.get("id") for card in self.store.cards()}
        candidate = prefix
        if candidate not in existing:
            return candidate
        n = 2
        while True:
            candidate = f"{prefix}-{n}"
            if candidate not in existing:
                return candidate
            n += 1

    def unique_card_label(self, base: str) -> str:
        existing = {str(card.get("label", "")) for card in self.store.cards()}
        if base not in existing:
            return base
        n = 2
        while True:
            candidate = f"{base} {n}"
            if candidate not in existing:
                return candidate
            n += 1

    def refresh_after_deck_change(self, event: str) -> None:
        self.store.mark_dirty(event)
        self.refresh_deck_buttons()
        self.load_active_card_into_editor()
        self.redraw_output()
        self.schedule_autosave()

    def rename_active_card(self) -> None:
        card = self.store.active_card()
        label = (self.card_label_var.get() or "Card").strip()[:32] or "Card"
        card["label"] = label
        self.refresh_after_deck_change("card-renamed")
        self.status_var.set(f"Renamed card: {label}")

    def card_to_deckbutt_payload(self, card: dict) -> dict:
        return {
            "deckbutt_format": "3DCP-DECKBUTT",
            "version": APP_VERSION,
            "created_at": utc_now(),
            "source_app": APP_NAME,
            "card": copy.deepcopy(card),
        }

    def normalize_loaded_deckbutt_card(self, card: dict) -> dict:
        card = copy.deepcopy(card)
        base_label = str(card.get("label", "Loaded Card"))[:32] or "Loaded Card"
        card["label"] = self.unique_card_label(base_label)
        base_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(card.get("id", "loaded-card")).lower()).strip("-") or "loaded-card"
        card["id"] = self.unique_card_id(base_id)
        card.setdefault("fields", {})
        card.setdefault("layers", [])
        card["deck_border_type"] = normalize_deck_border_type(card.get("deck_border_type", ""))
        self.reassign_layer_ids_for_card_copy(card)
        return card

    def save_card_deckbutt(self) -> None:
        DECKBUTT_DIR.mkdir(parents=True, exist_ok=True)
        card = self.store.active_card()
        safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(card.get("label", "card"))).strip("_") or "card"
        path = filedialog.asksaveasfilename(
            title="Save deck card as .deckbutt",
            defaultextension=".deckbutt",
            filetypes=[("3DCP Deck Button", "*.deckbutt"), ("JSON", "*.json"), ("All files", "*.*")],
            initialdir=str(DECKBUTT_DIR),
            initialfile=f"{safe_label}.deckbutt",
        )
        if not path:
            return
        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        payload = self.card_to_deckbutt_payload(self.store.active_card())
        safe_write_json(Path(path), payload)
        self.status_var.set(f"Saved deck card: {Path(path).name}")

    def load_card_deckbutt(self) -> None:
        DECKBUTT_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Load .deckbutt card",
            filetypes=[("3DCP Deck Button", "*.deckbutt"), ("JSON", "*.json"), ("All files", "*.*")],
            initialdir=str(DECKBUTT_DIR),
        )
        if not path:
            return
        try:
            payload = safe_read_json(Path(path))
            if payload.get("deckbutt_format") != "3DCP-DECKBUTT":
                raise ValueError("This is not a 3DCP .deckbutt file.")
            card = payload.get("card")
            if not isinstance(card, dict):
                raise ValueError("The .deckbutt file does not contain a valid card.")
            card = self.normalize_loaded_deckbutt_card(card)
        except Exception as exc:
            messagebox.showerror("Could not load .deckbutt", str(exc))
            return

        self.store.cards().append(card)
        if self.card_index_by_id(card["id"]) is not None and self.card_index_by_id(card["id"]) < self.max_deck_buttons:
            self.store.set_active_card(card["id"])
        self.refresh_after_deck_change("deckbutt-card-loaded")
        self.status_var.set(f"Loaded deck card: {card.get('label', 'Card')}")

    def add_source_card(self) -> None:
        card = new_card("source_analyzer", self.unique_card_label("Source Analyzer"))
        card["id"] = self.unique_card_id("source-analyzer")
        # Keep built-in layer ids unique enough for future selection history.
        for layer in card.get("layers", []):
            if layer.get("type") == "emoji":
                layer["id"] = f"emoji-{uuid.uuid4().hex[:8]}"
        self.store.cards().append(card)
        if self.card_index_by_id(card["id"]) is not None and self.card_index_by_id(card["id"]) < self.max_deck_buttons:
            self.store.set_active_card(card["id"])
            self.status_var.set("Added Source Analyzer card")
        else:
            self.status_var.set("Added Source Analyzer card to storage")
        self.refresh_after_deck_change("source-card-added")

    def add_blank_card(self) -> None:
        card = new_card("blank", self.unique_card_label("Blank / Hide"))
        card["id"] = self.unique_card_id("blank-hide")
        self.store.cards().append(card)
        if self.card_index_by_id(card["id"]) is not None and self.card_index_by_id(card["id"]) < self.max_deck_buttons:
            self.store.set_active_card(card["id"])
            self.status_var.set("Added Blank / Hide card")
        else:
            self.status_var.set("Added Blank / Hide card to storage")
        self.refresh_after_deck_change("blank-card-added")

    def reassign_layer_ids_for_card_copy(self, card: dict) -> None:
        for layer in card.get("layers", []):
            layer_type = layer.get("type", "layer")
            if layer_type == "emoji":
                layer["id"] = f"emoji-{uuid.uuid4().hex[:8]}"
            elif layer_type == "image":
                layer["id"] = f"image-{uuid.uuid4().hex[:8]}"
            elif layer_type == "text":
                layer["id"] = f"text-{uuid.uuid4().hex[:8]}"
            else:
                layer["id"] = f"layer-{uuid.uuid4().hex[:8]}"

    def duplicate_active_card(self) -> None:
        source = self.store.active_card()
        duplicate = copy.deepcopy(source)
        base_label = str(source.get("label", "Card"))
        duplicate["id"] = self.unique_card_id(str(source.get("id", "card")) + "-copy")
        duplicate["label"] = self.unique_card_label(("Copy of " + base_label)[:32])
        self.reassign_layer_ids_for_card_copy(duplicate)
        self.store.cards().append(duplicate)
        if self.card_index_by_id(duplicate["id"]) is not None and self.card_index_by_id(duplicate["id"]) < self.max_deck_buttons:
            self.store.set_active_card(duplicate["id"])
            self.status_var.set(f"Duplicated card: {duplicate['label']}")
        else:
            self.status_var.set(f"Duplicated card to storage: {duplicate['label']}")
        self.refresh_after_deck_change("card-duplicated")

    def delete_active_card(self) -> None:
        cards = self.store.cards()
        if len(cards) <= 1:
            self.status_var.set("Cannot delete the only card")
            return
        active_id = self.store.data["header"].get("active_card_id")
        remaining = [card for card in cards if card.get("id") != active_id]
        if len(remaining) == len(cards):
            self.status_var.set("No active card deleted")
            return
        self.store.data["body"]["cards"] = remaining
        self.store.data["header"]["active_card_id"] = remaining[0].get("id")
        self.refresh_after_deck_change("card-deleted")
        self.status_var.set("Deleted active card")

    def select_card(self, card_id: str) -> None:
        self.apply_editor_to_card()
        self.store.set_active_card(card_id)
        self.load_active_card_into_editor()
        self.redraw_output()
        self.schedule_autosave()

    def load_active_card_into_editor(self) -> None:
        card = self.store.active_card()
        self.card_label_var.set(card.get("label", card.get("id", "Card")))
        fields = card.get("fields", {})
        self.ensure_current_card_values_are_options()
        self.refresh_top_dropdown_values()
        self.source_type_var.set(fields.get("sourceType", "Unknown"))
        self.confidence_var.set(fields.get("confidence", "Still Checking"))
        self.verdict_var.set(fields.get("verdict", "Still Checking"))
        self.source_link_var.set(fields.get("sourceLink", ""))
        wraps = ensure_box_wrap_storage(card)
        self.claim_wrap_var.set(int(wraps["claim"]))
        self.evidence_wrap_var.set(int(wraps["evidence"]))
        self.question_wrap_var.set(int(wraps["openQuestion"]))
        for text_widget, value in [
            (self.claim_text, fields.get("claim", "")),
            (self.evidence_text, fields.get("evidence", "")),
            (self.open_question_text, fields.get("openQuestion", "")),
        ]:
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", value)
            text_widget.edit_modified(False)
        active_id = card.get("id")
        for cid, btn in self.card_buttons.items():
            label = self.store.get_card(cid).get("label", cid)
            btn.configure(text=("▶ " if cid == active_id else "  ") + label)

        self.refresh_sticker_selector()
        self.refresh_image_selector()
        self.refresh_imported_image_library()
        self.refresh_text_layer_selector()
        self.refresh_top_row_editor()
        self.sync_deck_border_checkboxes()
        self.load_qr_group_into_controls()

    def emoji_layers(self) -> list[dict]:
        card = self.store.active_card()
        return [layer for layer in card.get("layers", []) if layer.get("type") == "emoji"]

    def clean_sticker_name(self, value: str, fallback: str = "Emoji") -> str:
        cleaned = (value or "").strip()[:19]
        return cleaned or fallback[:19]

    def next_sticker_auto_name(self) -> str:
        existing = {self.clean_sticker_name(layer.get("name", ""), "") for layer in self.emoji_layers()}
        n = 1
        while True:
            candidate = f"Emoji {n}"
            if candidate not in existing:
                return candidate
            n += 1

    def selected_sticker(self) -> dict | None:
        selected_id = self.selected_sticker_id_var.get()
        for layer in self.emoji_layers():
            if layer.get("id") == selected_id:
                return layer
        return None

    def sticker_display_label(self, layer: dict) -> str:
        name = self.clean_sticker_name(layer.get("name", ""), layer.get("id", "Emoji"))
        emoji = layer.get("text", "🔍")
        hidden = "" if layer.get("visible", True) else "  [hidden]"
        return f"{name}  {emoji}{hidden}"

    def refresh_sticker_selector(self) -> None:
        if self.sticker_selector is None:
            return

        layers = self.emoji_layers()
        label_to_id = {}
        values = []
        for layer in layers:
            label = self.sticker_display_label(layer)
            base = label
            counter = 2
            while label in label_to_id:
                label = f"{base} ({counter})"
                counter += 1
            label_to_id[label] = layer.get("id", "")
            values.append(label)
        self.sticker_label_to_id = label_to_id
        self.sticker_selector.configure(values=values)

        current_id = self.selected_sticker_id_var.get()
        current_label = ""
        for label, layer_id in label_to_id.items():
            if layer_id == current_id:
                current_label = label
                break
        if not current_label and values:
            current_label = values[0]
            self.selected_sticker_id_var.set(label_to_id[current_label])
        self.selected_sticker_label_var.set(current_label)
        self.load_selected_sticker_into_controls()

    def load_selected_sticker_into_controls(self) -> None:
        layer = self.selected_sticker()
        if not layer:
            self.sticker_name_var.set(self.next_sticker_auto_name())
            return
        self.sticker_text_var.set(layer.get("text", "🔍"))
        self.sticker_name_var.set(self.clean_sticker_name(layer.get("name", ""), "Emoji"))
        self.sticker_x_var.set(int(layer.get("x", 820)))
        self.sticker_y_var.set(int(layer.get("y", 340)))
        self.sticker_size_var.set(int(layer.get("size", 28)))
        self.sticker_opacity_var.set(float(layer.get("opacity", 1.0)))

    def on_sticker_selected(self, _event=None) -> None:
        selected_label = self.selected_sticker_label_var.get()
        selected_id = self.sticker_label_to_id.get(selected_label, "")
        self.selected_sticker_id_var.set(selected_id)
        self.load_selected_sticker_into_controls()

    def schedule_sticker_stage_only(self) -> None:
        if self.selected_sticker_id_var.get():
            self.store.data["stage"]["save_body_pending"] = True
            self.store.mark_dirty("sticker-stage-updated")
            self.schedule_autosave()

    def load_emoji_presets(self, path: Path | None = None) -> None:
        if path is None:
            user_current = USER_DATA_DIR / "current.emoji"
            path = user_current if user_current.exists() else DEFAULT_EMOJI_PRESET_PATH
        items = []
        try:
            if path.exists():
                items = load_emoji_presets_from_file(path)
        except Exception:
            items = []
        if not items:
            items = list(FALLBACK_EMOJI_PRESETS)
        self.emoji_preset_items = items
        self.refresh_emoji_preset_listbox()

    def refresh_emoji_preset_listbox(self) -> None:
        if self.emoji_preset_listbox is None:
            return
        self.emoji_preset_listbox.delete(0, "end")
        for item in self.emoji_preset_items:
            label = f"{item.get('emoji', '')}  {item.get('name', 'Emoji')}  [{item.get('category', 'General')}]"
            self.emoji_preset_listbox.insert("end", label)

    def on_emoji_preset_selected(self, _event=None) -> None:
        selection = self.emoji_preset_listbox.curselection() if self.emoji_preset_listbox else ()
        if not selection:
            return
        item = self.emoji_preset_items[selection[0]]
        self.status_var.set(f"Preset selected: {item.get('name', 'Emoji')}")

    def selected_emoji_preset(self) -> dict | None:
        if self.emoji_preset_listbox is None:
            return None
        selection = self.emoji_preset_listbox.curselection()
        if not selection:
            return None
        idx = selection[0]
        if idx < 0 or idx >= len(self.emoji_preset_items):
            return None
        return self.emoji_preset_items[idx]

    def use_selected_emoji_preset(self) -> None:
        item = self.selected_emoji_preset()
        if not item:
            return
        self.sticker_text_var.set(item.get("emoji", "🧪"))
        if not self.selected_sticker_id_var.get():
            suggested_name = self.clean_sticker_name(item.get("name", "Emoji"), self.next_sticker_auto_name())
            self.sticker_name_var.set(suggested_name)
        self.status_var.set(f"Preset loaded: {item.get('name', 'Emoji')}")
        if self.selected_sticker_id_var.get():
            self.apply_sticker_editor()

    def copy_selected_emoji_preset(self) -> None:
        item = self.selected_emoji_preset()
        if not item:
            return
        emoji = item.get("emoji", "")
        self.root.clipboard_clear()
        self.root.clipboard_append(emoji)
        self.status_var.set(f"Copied emoji: {item.get('name', 'Emoji')}")

    def load_custom_emoji_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Load .emoji preset file",
            filetypes=[("Emoji preset", "*.emoji"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=str(EMOJI_PRESET_DIR),
        )
        if not path:
            return
        try:
            self.load_emoji_presets(Path(path))
            self.status_var.set(f"Loaded emoji preset file: {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("Could not load .emoji file", str(exc))

    def add_emoji_sticker(self) -> None:
        card = self.store.active_card()
        if card.get("type") == "blank":
            return

        layers = card.setdefault("layers", [])
        existing_z = [int(layer.get("z", 0)) for layer in layers]
        z = (max(existing_z) + 1) if existing_z else 1
        layer_id = f"emoji-{uuid.uuid4().hex[:8]}"

        try:
            x = int(self.sticker_x_var.get())
            y = int(self.sticker_y_var.get())
            size = int(self.sticker_size_var.get())
            opacity = float(self.sticker_opacity_var.get())
        except (tk.TclError, ValueError):
            x, y, size, opacity = 820, 340, 28, 1.0

        fallback_name = self.next_sticker_auto_name()
        layer = {
            "id": layer_id,
            "type": "emoji",
            "name": self.clean_sticker_name(self.sticker_name_var.get(), fallback_name),
            "text": self.sticker_text_var.get().strip() or "🧪",
            "x": max(0, min(OUTPUT_WIDTH, x)),
            "y": max(0, min(OUTPUT_HEIGHT, y)),
            "size": max(8, min(96, size)),
            "opacity": max(0.1, min(1.0, opacity)),
            "z": z,
            "visible": True,
        }
        layers.append(layer)
        self.selected_sticker_id_var.set(layer_id)
        self.store.mark_dirty("emoji-sticker-added")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def apply_sticker_editor(self) -> None:
        layer = self.selected_sticker()
        if not layer:
            return

        try:
            x = max(0, min(OUTPUT_WIDTH, int(self.sticker_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT, int(self.sticker_y_var.get())))
            size = max(8, min(96, int(self.sticker_size_var.get())))
            opacity = max(0.1, min(1.0, float(self.sticker_opacity_var.get())))
        except (tk.TclError, ValueError):
            return

        layer["name"] = self.clean_sticker_name(self.sticker_name_var.get(), self.next_sticker_auto_name())
        layer["text"] = self.sticker_text_var.get().strip() or "🧪"
        layer["x"] = x
        layer["y"] = y
        layer["size"] = size
        layer["opacity"] = opacity
        self.store.mark_dirty("emoji-sticker-updated")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_sticker_up(self) -> None:
        layer = self.selected_sticker()
        if not layer:
            return
        max_z = max([int(item.get("z", 0)) for item in self.store.active_card().get("layers", [])] or [0])
        layer["z"] = min(max_z + 1, int(layer.get("z", 0)) + 1)
        self.store.mark_dirty("emoji-sticker-layer-up")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_sticker_down(self) -> None:
        layer = self.selected_sticker()
        if not layer:
            return
        layer["z"] = max(0, int(layer.get("z", 0)) - 1)
        self.store.mark_dirty("emoji-sticker-layer-down")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def delete_sticker(self) -> None:
        card = self.store.active_card()
        selected_id = self.selected_sticker_id_var.get()
        if not selected_id:
            return

        layers = card.get("layers", [])
        card["layers"] = [layer for layer in layers if layer.get("id") != selected_id]
        self.selected_sticker_id_var.set("")
        self.selected_sticker_label_var.set("")
        self.store.mark_dirty("emoji-sticker-deleted")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def image_layers(self) -> list[dict]:
        card = self.store.active_card()
        return [layer for layer in card.get("layers", []) if layer.get("type") == "image"]

    def clean_image_name(self, value: str, fallback: str = "Image") -> str:
        cleaned = (value or "").strip()[:19]
        return cleaned or fallback[:19]

    def next_image_auto_name(self) -> str:
        existing = {self.clean_image_name(layer.get("name", ""), "") for layer in self.image_layers()}
        n = 1
        while True:
            candidate = f"Image {n}"
            if candidate not in existing:
                return candidate
            n += 1

    def selected_image_layer(self) -> dict | None:
        selected_id = self.selected_image_id_var.get()
        for layer in self.image_layers():
            if layer.get("id") == selected_id:
                return layer
        return None

    def image_display_label(self, layer: dict) -> str:
        name = self.clean_image_name(layer.get("name", ""), layer.get("id", "Image"))
        hidden = "" if layer.get("visible", True) else "  [hidden]"
        return f"{name}  🖼️{hidden}"

    def refresh_image_selector(self) -> None:
        if self.image_selector is None:
            return
        layers = self.image_layers()
        label_to_id = {}
        values = []
        for layer in layers:
            label = self.image_display_label(layer)
            base = label
            counter = 2
            while label in label_to_id:
                label = f"{base} ({counter})"
                counter += 1
            label_to_id[label] = layer.get("id", "")
            values.append(label)
        self.image_label_to_id = label_to_id
        self.image_selector.configure(values=values)

        current_id = self.selected_image_id_var.get()
        current_label = ""
        for label, layer_id in label_to_id.items():
            if layer_id == current_id:
                current_label = label
                break
        if not current_label and values:
            current_label = values[0]
            self.selected_image_id_var.set(label_to_id[current_label])
        self.selected_image_label_var.set(current_label)
        self.load_selected_image_into_controls()

    def load_selected_image_into_controls(self) -> None:
        layer = self.selected_image_layer()
        if not layer:
            self.image_name_var.set(self.next_image_auto_name())
            self.image_path_var.set("")
            self.image_rotation_var.set(0)
            self.image_flip_x_var.set(False)
            self.image_flip_y_var.set(False)
            self.image_z_var.set(0)
            return
        self.image_name_var.set(self.clean_image_name(layer.get("name", ""), "Image"))
        self.image_x_var.set(int(layer.get("x", 760)))
        self.image_y_var.set(int(layer.get("y", 245)))
        self.image_scale_var.set(int(layer.get("scale", 100)))
        self.image_opacity_var.set(float(layer.get("opacity", 1.0)))
        self.image_rotation_var.set(int(layer.get("rotation", 0)))
        self.image_flip_x_var.set(bool(layer.get("flip_x", False)))
        self.image_flip_y_var.set(bool(layer.get("flip_y", False)))
        self.image_z_var.set(int(layer.get("z", 0)))
        path = layer.get("source_path", "")
        self.image_path_var.set(Path(path).name if path else "")

    def on_image_layer_selected(self, _event=None) -> None:
        selected_label = self.selected_image_label_var.get()
        selected_id = self.image_label_to_id.get(selected_label, "")
        self.selected_image_id_var.set(selected_id)
        self.load_selected_image_into_controls()

    def schedule_image_stage_only(self) -> None:
        if self.selected_image_id_var.get():
            self.store.data["stage"]["save_body_pending"] = True
            self.store.mark_dirty("image-stage-updated")
            self.schedule_autosave()

    def imported_image_paths(self) -> list[Path]:
        IMPORTED_PNG_DIR.mkdir(parents=True, exist_ok=True)
        allowed = {".png", ".jpg", ".jpeg", ".webp"}
        return sorted([path for path in IMPORTED_PNG_DIR.iterdir() if path.is_file() and path.suffix.lower() in allowed], key=lambda path: path.name.casefold())

    def refresh_imported_image_library(self) -> None:
        paths = self.imported_image_paths()
        values = [path.name for path in paths]
        if self.imported_image_selector is not None:
            self.imported_image_selector.configure(values=values)
        if self.imported_image_library_var.get() not in values:
            self.imported_image_library_var.set(values[0] if values else "")

    def find_reusable_imported_image(self, src: Path) -> Path | None:
        try:
            src_resolved = src.resolve()
        except Exception:
            src_resolved = src
        for existing in self.imported_image_paths():
            try:
                if existing.resolve() == src_resolved:
                    return existing
            except Exception:
                pass
        try:
            src_hash = file_sha256(src)
        except Exception:
            return None
        for existing in self.imported_image_paths():
            try:
                if file_sha256(existing) == src_hash:
                    return existing
            except Exception:
                continue
        return None

    def store_or_reuse_imported_image(self, src: Path) -> Path:
        reusable = self.find_reusable_imported_image(src)
        if reusable is not None:
            return reusable
        dest = IMPORTED_PNG_DIR / src.name
        if dest.exists():
            stem, suffix, n = src.stem, src.suffix, 1
            while True:
                candidate = IMPORTED_PNG_DIR / f"{stem}_{n}{suffix}"
                if not candidate.exists():
                    dest = candidate
                    break
                n += 1
        shutil.copy2(src, dest)
        return dest

    def add_image_layer_from_path(self, image_path: Path, reason: str = "png-image-added") -> dict | None:
        card = self.store.active_card()
        if card.get("type") == "blank" or not image_path.exists():
            return None
        layers = card.setdefault("layers", [])
        existing_z = [int(layer.get("z", 0)) for layer in layers]
        z = (max(existing_z) + 1) if existing_z else 1
        try:
            x = max(0, min(OUTPUT_WIDTH, int(self.image_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT, int(self.image_y_var.get())))
            scale = max(10, min(400, int(self.image_scale_var.get())))
            opacity = max(0.1, min(1.0, float(self.image_opacity_var.get())))
            rotation = max(-359, min(359, int(self.image_rotation_var.get())))
        except (tk.TclError, ValueError):
            x, y, scale, opacity, rotation = 760, 245, 100, 1.0, 0
        layer_id = f"image-{uuid.uuid4().hex[:8]}"
        fallback_name = self.next_image_auto_name()
        name_guess = self.clean_image_name(image_path.stem.replace('_', ' '), fallback_name)
        layer = {
            "id": layer_id,
            "type": "image",
            "name": name_guess,
            "source_path": str(image_path),
            "x": x,
            "y": y,
            "scale": scale,
            "opacity": opacity,
            "rotation": rotation,
            "flip_x": bool(self.image_flip_x_var.get()),
            "flip_y": bool(self.image_flip_y_var.get()),
            "z": z,
            "visible": True,
        }
        layers.append(layer)
        self.selected_image_id_var.set(layer_id)
        self.image_path_var.set(image_path.name)
        self.image_z_var.set(z)
        self.store.mark_dirty(reason)
        self.refresh_imported_image_library()
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()
        return layer

    def import_png_layer(self) -> None:
        IMPORTED_PNG_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Import image layer",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.webp"), ("PNG image", "*.png"), ("All files", "*.*")],
            initialdir=str(IMPORTED_PNG_DIR if IMPORTED_PNG_DIR.exists() else USER_DATA_DIR),
        )
        if not path:
            return
        src = Path(path)
        reusable_before = self.find_reusable_imported_image(src)
        try:
            dest = reusable_before or self.store_or_reuse_imported_image(src)
        except Exception as exc:
            messagebox.showerror("Import image", f"Could not import image:\n{exc}")
            return
        reused = reusable_before is not None
        self.add_image_layer_from_path(dest, "png-image-reused" if reused else "png-image-imported")
        self.status_var.set(f"Using imported image: {dest.name}")

    def reuse_imported_png_layer(self) -> None:
        name = self.imported_image_library_var.get().strip()
        if not name:
            self.status_var.set("No imported image is available to reuse")
            return
        path = IMPORTED_PNG_DIR / name
        if not path.is_file():
            self.refresh_imported_image_library()
            self.status_var.set("Selected imported image is no longer available")
            return
        self.add_image_layer_from_path(path, "png-image-library-reused")
        self.status_var.set(f"Reused imported image without another copy: {name}")

    def apply_image_editor(self) -> None:
        layer = self.selected_image_layer()
        if not layer:
            return
        try:
            x = max(0, min(OUTPUT_WIDTH, int(self.image_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT, int(self.image_y_var.get())))
            scale = max(10, min(400, int(self.image_scale_var.get())))
            opacity = max(0.1, min(1.0, float(self.image_opacity_var.get())))
            rotation = max(-359, min(359, int(self.image_rotation_var.get())))
            z = max(-1000, min(1000, int(self.image_z_var.get())))
        except (tk.TclError, ValueError):
            return
        layer["name"] = self.clean_image_name(self.image_name_var.get(), self.next_image_auto_name())
        layer["x"] = x
        layer["y"] = y
        layer["scale"] = scale
        layer["opacity"] = opacity
        layer["rotation"] = rotation
        layer["flip_x"] = bool(self.image_flip_x_var.get())
        layer["flip_y"] = bool(self.image_flip_y_var.get())
        layer["z"] = z
        self.rendered_image_cache.clear()
        self.store.mark_dirty("png-image-updated")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_image_up(self) -> None:
        layer = self.selected_image_layer()
        if not layer:
            return
        max_z = max([int(item.get("z", 0)) for item in self.store.active_card().get("layers", [])] or [0])
        layer["z"] = min(1000, max_z + 1, int(layer.get("z", 0)) + 1)
        self.image_z_var.set(int(layer["z"]))
        self.store.mark_dirty("png-image-layer-up")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_image_down(self) -> None:
        layer = self.selected_image_layer()
        if not layer:
            return
        layer["z"] = max(-1000, int(layer.get("z", 0)) - 1)
        self.image_z_var.set(int(layer["z"]))
        self.store.mark_dirty("png-image-layer-down")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def delete_image_layer(self) -> None:
        card = self.store.active_card()
        selected_id = self.selected_image_id_var.get()
        if not selected_id:
            return
        layers = card.get("layers", [])
        card["layers"] = [layer for layer in layers if layer.get("id") != selected_id]
        self.selected_image_id_var.set("")
        self.selected_image_label_var.set("")
        self.store.mark_dirty("png-image-deleted")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def text_layers(self) -> list[dict]:
        card = self.store.active_card()
        return [layer for layer in card.get("layers", []) if layer.get("type") == "text"]

    def clean_text_layer_name(self, value: str, fallback: str = "Text") -> str:
        cleaned = (value or "").strip()[:19]
        return cleaned or fallback[:19]

    def next_text_layer_auto_name(self) -> str:
        existing = {self.clean_text_layer_name(layer.get("name", ""), "") for layer in self.text_layers()}
        n = 1
        while True:
            candidate = f"Text {n}"
            if candidate not in existing:
                return candidate
            n += 1

    def selected_text_layer(self) -> dict | None:
        selected_id = self.selected_text_layer_id_var.get()
        for layer in self.text_layers():
            if layer.get("id") == selected_id:
                return layer
        return None

    def text_layer_display_label(self, layer: dict) -> str:
        name = self.clean_text_layer_name(layer.get("name", ""), layer.get("id", "Text"))
        hidden = "" if layer.get("visible", True) else "  [hidden]"
        return f"{name}  T{hidden}"

    def refresh_text_layer_selector(self) -> None:
        if self.text_layer_selector is None:
            return
        layers = self.text_layers()
        label_to_id = {}
        values = []
        for layer in layers:
            label = self.text_layer_display_label(layer)
            base = label
            counter = 2
            while label in label_to_id:
                label = f"{base} ({counter})"
                counter += 1
            label_to_id[label] = layer.get("id", "")
            values.append(label)
        self.text_layer_label_to_id = label_to_id
        self.text_layer_selector.configure(values=values)

        current_id = self.selected_text_layer_id_var.get()
        current_label = ""
        for label, layer_id in label_to_id.items():
            if layer_id == current_id:
                current_label = label
                break
        if not current_label and values:
            current_label = values[0]
            self.selected_text_layer_id_var.set(label_to_id[current_label])
        self.selected_text_layer_label_var.set(current_label)
        self.load_selected_text_layer_into_controls()

    def load_selected_text_layer_into_controls(self) -> None:
        layer = self.selected_text_layer()
        if not layer:
            self.text_layer_name_var.set(self.next_text_layer_auto_name())
            self.text_layer_color_var.set("#e8fff5")
            self.text_layer_wrap_var.set(260)
            self.text_layer_rotation_var.set(0)
            self.text_layer_flip_x_var.set(False)
            self.text_layer_flip_y_var.set(False)
            self.text_layer_z_var.set(0)
            if self.text_layer_text is not None:
                self.text_layer_text.delete("1.0", "end")
                self.text_layer_text.insert("1.0", "New text layer")
                self.text_layer_text.edit_modified(False)
            return
        self.text_layer_name_var.set(self.clean_text_layer_name(layer.get("name", ""), "Text"))
        self.text_layer_x_var.set(int(layer.get("x", 740)))
        self.text_layer_y_var.set(int(layer.get("y", 185)))
        self.text_layer_size_var.set(int(layer.get("size", 22)))
        self.text_layer_opacity_var.set(float(layer.get("opacity", 1.0)))
        self.text_layer_color_var.set(normalize_hex_color(layer.get("color", "#e8fff5")))
        self.text_layer_wrap_var.set(int(layer.get("wrap_width", 260)))
        self.text_layer_rotation_var.set(int(layer.get("rotation", 0)))
        self.text_layer_flip_x_var.set(bool(layer.get("flip_x", False)))
        self.text_layer_flip_y_var.set(bool(layer.get("flip_y", False)))
        self.text_layer_z_var.set(int(layer.get("z", 0)))
        if self.text_layer_text is not None:
            self.text_layer_text.delete("1.0", "end")
            self.text_layer_text.insert("1.0", layer.get("text", ""))
            self.text_layer_text.edit_modified(False)

    def on_text_layer_selected(self, _event=None) -> None:
        selected_label = self.selected_text_layer_label_var.get()
        selected_id = self.text_layer_label_to_id.get(selected_label, "")
        self.selected_text_layer_id_var.set(selected_id)
        self.load_selected_text_layer_into_controls()

    def text_layer_content_value(self) -> str:
        if self.text_layer_text is None:
            return ""
        return self.text_layer_text.get("1.0", "end").rstrip()

    def schedule_text_layer_stage_only(self) -> None:
        if self.selected_text_layer_id_var.get():
            self.store.data["stage"]["save_body_pending"] = True
            self.store.mark_dirty("text-layer-stage-updated")
            self.schedule_autosave()

    def on_text_layer_focus_out(self, _event=None) -> None:
        self.apply_text_layer_editor()

    def on_text_layer_modified(self, _event=None) -> None:
        if self.text_layer_text is None:
            return
        if self.text_layer_text.edit_modified():
            self.schedule_text_layer_stage_only()
            self.text_layer_text.edit_modified(False)

    def add_text_layer(self) -> None:
        card = self.store.active_card()
        if card.get("type") == "blank":
            return
        layers = card.setdefault("layers", [])
        existing_z = [int(layer.get("z", 0)) for layer in layers]
        z = (max(existing_z) + 1) if existing_z else 1
        layer_id = f"text-{uuid.uuid4().hex[:8]}"
        fallback_name = self.next_text_layer_auto_name()
        try:
            x = max(0, min(OUTPUT_WIDTH, int(self.text_layer_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT, int(self.text_layer_y_var.get())))
            size = max(8, min(72, int(self.text_layer_size_var.get())))
            opacity = max(0.1, min(1.0, float(self.text_layer_opacity_var.get())))
            wrap_width = max(80, min(900, int(self.text_layer_wrap_var.get())))
            rotation = max(-359, min(359, int(self.text_layer_rotation_var.get())))
        except (tk.TclError, ValueError):
            x, y, size, opacity, wrap_width, rotation = 740, 185, 22, 1.0, 260, 0
        layer = {
            "id": layer_id,
            "type": "text",
            "name": self.clean_text_layer_name(self.text_layer_name_var.get(), fallback_name),
            "text": self.text_layer_content_value() or "New text layer",
            "x": x,
            "y": y,
            "size": size,
            "opacity": opacity,
            "color": normalize_hex_color(self.text_layer_color_var.get()),
            "wrap_width": wrap_width,
            "rotation": rotation,
            "flip_x": bool(self.text_layer_flip_x_var.get()),
            "flip_y": bool(self.text_layer_flip_y_var.get()),
            "z": z,
            "visible": True,
        }
        layers.append(layer)
        self.selected_text_layer_id_var.set(layer_id)
        self.store.mark_dirty("text-layer-added")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def apply_text_layer_editor(self) -> None:
        layer = self.selected_text_layer()
        if not layer:
            return
        try:
            x = max(0, min(OUTPUT_WIDTH, int(self.text_layer_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT, int(self.text_layer_y_var.get())))
            size = max(8, min(72, int(self.text_layer_size_var.get())))
            opacity = max(0.1, min(1.0, float(self.text_layer_opacity_var.get())))
            wrap_width = max(80, min(900, int(self.text_layer_wrap_var.get())))
            rotation = max(-359, min(359, int(self.text_layer_rotation_var.get())))
            z = max(-1000, min(1000, int(self.text_layer_z_var.get())))
        except (tk.TclError, ValueError):
            return
        layer["name"] = self.clean_text_layer_name(self.text_layer_name_var.get(), self.next_text_layer_auto_name())
        layer["text"] = self.text_layer_content_value() or "New text layer"
        layer["x"] = x
        layer["y"] = y
        layer["size"] = size
        layer["opacity"] = opacity
        layer["color"] = normalize_hex_color(self.text_layer_color_var.get())
        layer["wrap_width"] = wrap_width
        layer["rotation"] = rotation
        layer["flip_x"] = bool(self.text_layer_flip_x_var.get())
        layer["flip_y"] = bool(self.text_layer_flip_y_var.get())
        layer["z"] = z
        self.rendered_text_cache.clear()
        self.store.mark_dirty("text-layer-updated")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_text_up(self) -> None:
        layer = self.selected_text_layer()
        if not layer:
            return
        max_z = max([int(item.get("z", 0)) for item in self.store.active_card().get("layers", [])] or [0])
        layer["z"] = min(1000, max_z + 1, int(layer.get("z", 0)) + 1)
        self.text_layer_z_var.set(int(layer["z"]))
        self.store.mark_dirty("text-layer-up")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_text_down(self) -> None:
        layer = self.selected_text_layer()
        if not layer:
            return
        layer["z"] = max(-1000, int(layer.get("z", 0)) - 1)
        self.text_layer_z_var.set(int(layer["z"]))
        self.store.mark_dirty("text-layer-down")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def delete_text_layer(self) -> None:
        card = self.store.active_card()
        selected_id = self.selected_text_layer_id_var.get()
        if not selected_id:
            return
        layers = card.get("layers", [])
        card["layers"] = [layer for layer in layers if layer.get("id") != selected_id]
        self.selected_text_layer_id_var.set("")
        self.selected_text_layer_label_var.set("")
        self.store.mark_dirty("text-layer-deleted")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def max_layer_z(self) -> int:
        return max([int(layer.get("z", 0)) for layer in self.store.active_card().get("layers", [])] or [0])

    def duplicate_layer_common(self, layer: dict | None, layer_type: str) -> dict | None:
        if not layer:
            return None
        duplicate = copy.deepcopy(layer)
        duplicate["x"] = max(0, min(OUTPUT_WIDTH, int(duplicate.get("x", 0)) + 20))
        duplicate["y"] = max(0, min(OUTPUT_HEIGHT, int(duplicate.get("y", 0)) + 20))
        duplicate["z"] = self.max_layer_z() + 1
        duplicate["visible"] = True
        if layer_type == "emoji":
            duplicate["id"] = f"emoji-{uuid.uuid4().hex[:8]}"
            duplicate["name"] = self.clean_sticker_name("Copy " + str(layer.get("name", "Emoji")), self.next_sticker_auto_name())
        elif layer_type == "image":
            duplicate["id"] = f"image-{uuid.uuid4().hex[:8]}"
            duplicate["name"] = self.clean_image_name("Copy " + str(layer.get("name", "Image")), self.next_image_auto_name())
        elif layer_type == "text":
            duplicate["id"] = f"text-{uuid.uuid4().hex[:8]}"
            duplicate["name"] = self.clean_text_layer_name("Copy " + str(layer.get("name", "Text")), self.next_text_layer_auto_name())
        self.store.active_card().setdefault("layers", []).append(duplicate)
        return duplicate

    def duplicate_sticker(self) -> None:
        duplicate = self.duplicate_layer_common(self.selected_sticker(), "emoji")
        if not duplicate:
            return
        self.selected_sticker_id_var.set(duplicate["id"])
        self.store.mark_dirty("emoji-sticker-duplicated")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def duplicate_image_layer(self) -> None:
        duplicate = self.duplicate_layer_common(self.selected_image_layer(), "image")
        if not duplicate:
            return
        self.selected_image_id_var.set(duplicate["id"])
        self.store.mark_dirty("png-image-duplicated")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def duplicate_text_layer(self) -> None:
        duplicate = self.duplicate_layer_common(self.selected_text_layer(), "text")
        if not duplicate:
            return
        self.selected_text_layer_id_var.set(duplicate["id"])
        self.store.mark_dirty("text-layer-duplicated")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def set_layer_visibility(self, layer: dict | None, visible: bool, reason: str) -> None:
        if not layer:
            return
        layer["visible"] = bool(visible)
        self.store.mark_dirty(reason)
        self.refresh_sticker_selector()
        self.refresh_image_selector()
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def show_sticker(self) -> None:
        self.set_layer_visibility(self.selected_sticker(), True, "emoji-sticker-shown")

    def hide_sticker(self) -> None:
        self.set_layer_visibility(self.selected_sticker(), False, "emoji-sticker-hidden")

    def show_image_layer(self) -> None:
        self.set_layer_visibility(self.selected_image_layer(), True, "png-image-shown")

    def hide_image_layer(self) -> None:
        self.set_layer_visibility(self.selected_image_layer(), False, "png-image-hidden")

    def show_text_layer(self) -> None:
        self.set_layer_visibility(self.selected_text_layer(), True, "text-layer-shown")

    def hide_text_layer(self) -> None:
        self.set_layer_visibility(self.selected_text_layer(), False, "text-layer-hidden")

    def layer_size_for_alignment(self, layer: dict | None) -> tuple[int, int]:
        if not layer:
            return (0, 0)
        layer_type = layer.get("type")
        if layer_type == "emoji":
            size = max(8, min(96, int(layer.get("size", 26))))
            return (size, size)
        if layer_type == "image":
            try:
                rendered = self.transformed_image_pil(layer)
                if rendered is not None:
                    return rendered.size
            except Exception:
                pass
            return (100, 100)
        if layer_type == "text":
            if int(layer.get("rotation", 0)) or bool(layer.get("flip_x", False)) or bool(layer.get("flip_y", False)):
                try:
                    rendered = self.render_text_layer_pil(layer)
                    if rendered is not None:
                        return rendered.size
                except Exception:
                    pass
            width = max(80, min(900, int(layer.get("wrap_width", 260))))
            txt = str(layer.get("text", ""))
            size = max(8, min(72, int(layer.get("size", 22))))
            approx_lines = max(1, min(10, (len(txt) // max(12, width // max(size, 1))) + 1))
            return (width, max(size + 4, approx_lines * (size + 4)))
        return (0, 0)

    def set_layer_position(self, layer: dict | None, x: int, y: int, reason: str) -> None:
        if not layer:
            return
        w, h = self.layer_size_for_alignment(layer)
        x = max(0, min(OUTPUT_WIDTH - min(w, OUTPUT_WIDTH), int(x)))
        y = max(0, min(OUTPUT_HEIGHT - min(h, OUTPUT_HEIGHT), int(y)))
        layer["x"] = x
        layer["y"] = y
        if layer.get("type") == "emoji":
            self.sticker_x_var.set(x)
            self.sticker_y_var.set(y)
            self.refresh_sticker_selector()
        elif layer.get("type") == "image":
            self.image_x_var.set(x)
            self.image_y_var.set(y)
            self.refresh_image_selector()
        elif layer.get("type") == "text":
            self.text_layer_x_var.set(x)
            self.text_layer_y_var.set(y)
            self.refresh_text_layer_selector()
        self.store.mark_dirty(reason)
        self.redraw_output()
        self.schedule_autosave()

    def nudge_layer(self, layer: dict | None, dx: int, dy: int, reason: str) -> None:
        if not layer:
            return
        self.set_layer_position(layer, int(layer.get("x", 0)) + dx, int(layer.get("y", 0)) + dy, reason)

    def snap_layer(self, layer: dict | None, target: str, reason: str) -> None:
        if not layer:
            return
        safe_x1, safe_y1 = 52, 72
        safe_x2, safe_y2 = OUTPUT_WIDTH - 52, OUTPUT_HEIGHT - 40
        w, h = self.layer_size_for_alignment(layer)
        x = int(layer.get("x", 0))
        y = int(layer.get("y", 0))
        if target == "left":
            x = safe_x1
        elif target == "center_x":
            x = safe_x1 + ((safe_x2 - safe_x1 - w) // 2)
        elif target == "right":
            x = safe_x2 - w
        elif target == "top":
            y = safe_y1
        elif target == "center_y":
            y = safe_y1 + ((safe_y2 - safe_y1 - h) // 2)
        elif target == "bottom":
            y = safe_y2 - h
        self.set_layer_position(layer, x, y, reason)

    def nudge_sticker(self, dx: int, dy: int) -> None:
        self.nudge_layer(self.selected_sticker(), dx, dy, "emoji-sticker-nudged")

    def snap_sticker(self, target: str) -> None:
        self.snap_layer(self.selected_sticker(), target, "emoji-sticker-snapped")

    def nudge_image_layer(self, dx: int, dy: int) -> None:
        self.nudge_layer(self.selected_image_layer(), dx, dy, "png-image-nudged")

    def snap_image_layer(self, target: str) -> None:
        self.snap_layer(self.selected_image_layer(), target, "png-image-snapped")

    def nudge_text_layer(self, dx: int, dy: int) -> None:
        self.nudge_layer(self.selected_text_layer(), dx, dy, "text-layer-nudged")

    def snap_text_layer(self, target: str) -> None:
        self.snap_layer(self.selected_text_layer(), target, "text-layer-snapped")

    def render_z_values(self, exclude_layer_id: str = "") -> list[int]:
        values = [int(self.qr_group().get("z", 0))]
        for layer in self.store.active_card().get("layers", []):
            if exclude_layer_id and layer.get("id") == exclude_layer_id:
                continue
            values.append(int(layer.get("z", 0)))
        return values or [0]

    def set_layer_z_value(self, layer: dict | None, z: int, var: tk.IntVar, reason: str) -> None:
        if not layer:
            return
        z = max(-1000, min(1000, int(z)))
        layer["z"] = z
        var.set(z)
        self.store.mark_dirty(reason)
        self.refresh_image_selector()
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def nudge_image_z(self, dz: int) -> None:
        layer = self.selected_image_layer()
        if layer:
            self.set_layer_z_value(layer, int(layer.get("z", 0)) + dz, self.image_z_var, "png-image-z-nudged")

    def bring_image_to_front(self) -> None:
        layer = self.selected_image_layer()
        if layer:
            self.set_layer_z_value(layer, max(self.render_z_values(layer.get("id", ""))) + 1, self.image_z_var, "png-image-brought-front")

    def pull_image_to_back(self) -> None:
        layer = self.selected_image_layer()
        if layer:
            self.set_layer_z_value(layer, min(self.render_z_values(layer.get("id", ""))) - 1, self.image_z_var, "png-image-pulled-back")

    def nudge_text_z(self, dz: int) -> None:
        layer = self.selected_text_layer()
        if layer:
            self.set_layer_z_value(layer, int(layer.get("z", 0)) + dz, self.text_layer_z_var, "text-layer-z-nudged")

    def bring_text_to_front(self) -> None:
        layer = self.selected_text_layer()
        if layer:
            self.set_layer_z_value(layer, max(self.render_z_values(layer.get("id", ""))) + 1, self.text_layer_z_var, "text-layer-brought-front")

    def pull_text_to_back(self) -> None:
        layer = self.selected_text_layer()
        if layer:
            self.set_layer_z_value(layer, min(self.render_z_values(layer.get("id", ""))) - 1, self.text_layer_z_var, "text-layer-pulled-back")

    def set_box_wrap_to_max(self, key: str, variable: tk.IntVar) -> None:
        maximum = boxed_content_wrap_limit(key)
        variable.set(maximum)
        self.apply_editor_to_card()
        labels = {"claim": "Boxed Content #1", "evidence": "Boxed Content #2", "openQuestion": "Boxed Content #3"}
        self.status_var.set(f"{labels.get(key, key)} wrap set to available max: {maximum}px")

    def normalized_editor_box_wraps(self) -> dict:
        values = {
            "claim": normalize_box_wrap_width("claim", self.claim_wrap_var.get()),
            "evidence": normalize_box_wrap_width("evidence", self.evidence_wrap_var.get()),
            "openQuestion": normalize_box_wrap_width("openQuestion", self.question_wrap_var.get()),
        }
        # Keep the visible controls honest when a typed value exceeds the safe
        # output-region limit; do not silently show an unsaved oversized number.
        if self.claim_wrap_var.get() != values["claim"]:
            self.claim_wrap_var.set(values["claim"])
        if self.evidence_wrap_var.get() != values["evidence"]:
            self.evidence_wrap_var.set(values["evidence"])
        if self.question_wrap_var.get() != values["openQuestion"]:
            self.question_wrap_var.set(values["openQuestion"])
        return values

    def editor_values(self) -> dict:
        return {
            "sourceType": self.source_type_var.get().strip() or "Unknown",
            "confidence": self.confidence_var.get().strip() or "Still Checking",
            "sourceLink": self.source_link_var.get().strip(),
            "claim": self.claim_text.get("1.0", "end-1c").strip(),
            "evidence": self.evidence_text.get("1.0", "end-1c").strip(),
            "openQuestion": self.open_question_text.get("1.0", "end-1c").strip(),
            "verdict": self.verdict_var.get().strip() or "Still Checking",
        }

    def apply_editor_to_card(self) -> None:
        card = self.store.active_card()
        card["label"] = (self.card_label_var.get() or card.get("label", "Card")).strip()[:32] or "Card"
        if card.get("type") == "source_analyzer":
            card["fields"] = self.editor_values()
            card["box_wrap_widths"] = self.normalized_editor_box_wraps()
            card["box_wrap_model"] = BOX_WRAP_MODEL
        self.store.data["under_header"]["scan_loop"] = bool(self.scan_loop_var.get())
        self.store.data["under_header"]["scan_speed_ms"] = int(self.scan_speed_var.get())
        self.store.data["under_header"]["scanner_color"] = self.scanner_color_var.get().strip() or "#00ff99"
        self.store.data["under_header"]["output_visible"] = bool(self.output_visible_var.get())
        self.store.data["header"]["resource_profile"] = self.resource_profile_var.get()
        self.store.mark_dirty("editor-applied")
        self.apply_display_text_editor_without_reschedule()
        self.apply_top_row_option_without_reschedule()
        self.apply_qr_group_without_reschedule()
        self.refresh_top_dropdown_values()
        self.refresh_deck_buttons()
        self.redraw_output()
        self.status_var.set("Applied")
        self.schedule_autosave()

    def on_text_modified(self, event: tk.Event) -> None:
        widget = event.widget
        if widget.edit_modified():
            widget.edit_modified(False)
            self.schedule_autosave_stage_only()

    def on_editor_focus_out(self, _event: tk.Event) -> None:
        self.apply_editor_to_card()

    def schedule_autosave_stage_only(self) -> None:
        self.store.data["stage"]["draft_cards"][self.store.active_card().get("id")] = self.editor_values()
        self.store.data["stage"]["save_body_pending"] = True
        self.store.mark_dirty("stage-draft-updated")
        self.schedule_autosave()

    def schedule_autosave(self) -> None:
        if self.autosave_after_id:
            try:
                self.root.after_cancel(self.autosave_after_id)
            except tk.TclError:
                pass
        profile = self.resource_profile_var.get()
        delay = RESOURCE_PROFILES.get(profile, RESOURCE_PROFILES["low"])["autosave_delay_ms"]
        self.autosave_after_id = self.root.after(delay, self.autosave_tick)

    def autosave_tick(self) -> None:
        self.autosave_after_id = None
        self.apply_editor_to_card_without_reschedule()
        display_changed = self.apply_display_text_editor_without_reschedule()
        top_row_changed = self.apply_top_row_option_without_reschedule()
        qr_changed = self.apply_qr_group_without_reschedule()
        if display_changed or top_row_changed or qr_changed:
            self.refresh_top_dropdown_values()
            self.redraw_output()
        self.store.save("autosave")
        self.status_var.set("Autosaved")

    def apply_editor_to_card_without_reschedule(self) -> None:
        card = self.store.active_card()
        card["label"] = (self.card_label_var.get() or card.get("label", "Card")).strip()[:32] or "Card"
        if card.get("type") == "source_analyzer":
            card["fields"] = self.editor_values()
            card["box_wrap_widths"] = self.normalized_editor_box_wraps()
            card["box_wrap_model"] = BOX_WRAP_MODEL
        self.store.data["under_header"]["scan_loop"] = bool(self.scan_loop_var.get())
        self.store.data["under_header"]["scan_speed_ms"] = int(self.scan_speed_var.get())
        self.store.data["under_header"]["scanner_color"] = self.scanner_color_var.get().strip() or "#00ff99"
        self.store.data["under_header"]["output_visible"] = bool(self.output_visible_var.get())
        self.store.data["header"]["resource_profile"] = self.resource_profile_var.get()
        self.apply_top_row_option_without_reschedule()
        self.apply_qr_group_without_reschedule()
        self.store.mark_dirty("editor-applied")

    def redraw_output(self) -> None:
        self.output_canvas.delete("all")
        self.render_image_refs = []
        card = self.store.active_card()
        if card.get("type") == "blank":
            self.draw_blank_panel()
            return
        self.draw_source_analyzer(card)

    def draw_blank_panel(self) -> None:
        c = self.output_canvas
        blank_bg = self.theme_color("blank_background")
        c.configure(bg=blank_bg)
        c.create_rectangle(0, 0, OUTPUT_WIDTH, OUTPUT_HEIGHT, fill=blank_bg, outline="")
        c.create_text(OUTPUT_WIDTH // 2, OUTPUT_HEIGHT // 2, text="", fill=blank_bg, font=("TkDefaultFont", 1))

    def draw_source_analyzer(self, card: dict) -> None:
        c = self.output_canvas
        bg = self.theme_color("output_background")
        self.store.data["header"]["output"]["background"] = bg
        accent = normalize_hex_color(self.scanner_color_var.get().strip() or self.theme_color("accent"), self.theme_color("accent"))
        c.configure(bg=bg)
        c.create_rectangle(0, 0, OUTPUT_WIDTH, OUTPUT_HEIGHT, fill=bg, outline="")
        c.create_rectangle(14, 14, OUTPUT_WIDTH - 14, OUTPUT_HEIGHT - 14, fill=self.theme_color("main_panel_background"), outline=self.theme_color("main_border"), width=2)
        c.create_line(24, 54, OUTPUT_WIDTH - 24, 54, fill=self.theme_color("main_border"))

        bracket = 28
        for x1, y1, sx, sy in [(20, 20, 1, 1), (OUTPUT_WIDTH - 20, 20, -1, 1), (20, OUTPUT_HEIGHT - 20, 1, -1), (OUTPUT_WIDTH - 20, OUTPUT_HEIGHT - 20, -1, -1)]:
            c.create_line(x1, y1, x1 + bracket * sx, y1, fill=accent, width=2)
            c.create_line(x1, y1, x1, y1 + bracket * sy, fill=accent, width=2)

        self.draw_display_text(c, "title_main")
        self.draw_display_text(c, "status_live")

        block_x1, block_y1, block_x2, block_y2 = 40, 72, OUTPUT_WIDTH - 40, 188
        c.create_rectangle(block_x1, block_y1, block_x2, block_y2, fill=self.theme_color("info_panel_background"), outline=self.theme_color("standard_line"))

        fields = card.get("fields", {})
        link_text = fields.get("sourceLink", "").strip()
        has_link = bool(link_text)

        # Far-right aligned third column; QR column only when link exists.
        right_col_x2 = block_x2 - 18
        right_col_width = 250
        right_col_x1 = right_col_x2 - right_col_width

        if has_link:
            # Keep the original column reservation stable even when the QR Group is
            # moved elsewhere. This prevents manual QR positioning from reshaping rows.
            reserved_qr_size = QR_GROUP_DEFAULTS["size"]
            qr_gap = 18
            reserved_qr_x2 = right_col_x1 - qr_gap
            reserved_qr_x1 = reserved_qr_x2 - reserved_qr_size
            left_x2 = reserved_qr_x1 - qr_gap
        else:
            left_x2 = right_col_x1 - 18

        left_x1 = 52

        # Column separators
        c.create_line(left_x2, block_y1 + 12, left_x2, block_y2 - 12, fill=self.theme_color("standard_line"))
        if has_link:
            c.create_line(right_col_x1 - 9, block_y1 + 12, right_col_x1 - 9, block_y2 - 12, fill=self.theme_color("standard_line"))

        self.draw_row(c, "row_source_type", fields.get("sourceType", "Unknown"), accent, value_x=200, line_end=left_x2 - 10)
        self.draw_row(c, "row_confidence", fields.get("confidence", "Still Checking"), accent, value_x=200, line_end=left_x2 - 10)
        self.draw_row(c, "row_verdict", fields.get("verdict", "Still Checking"), accent, value_x=200, line_end=left_x2 - 10)

        # QR Group is rendered with user layers below, so its z value can move it
        # in front of or behind emoji/PNG/text layers as one linked section.

        # Display Edit positions are authoritative for every stored text object.
        self.draw_display_text(c, "right_brand")
        self.draw_display_text(c, "right_subtitle")
        if has_link:
            parse_target = link_text if "://" in link_text else "//" + link_text
            parsed = urlparse(parse_target)
            host = (parsed.netloc or parsed.path.split("/")[0] or "link").strip().lower()
            self.draw_display_text(c, "activity_label")
            self.draw_display_text(c, "host_label", runtime_vars={"host": host})

        wraps = ensure_box_wrap_storage(card)
        for wrap_key in ("claim", "evidence", "openQuestion"):
            geometry = boxed_content_geometry(wrap_key)
            self.draw_boxed_text(
                c,
                geometry["x"],
                geometry["y"],
                geometry["label_id"],
                fields.get(geometry["field"], ""),
                width=geometry["width"],
                height=geometry["height"],
                accent=accent,
                max_lines=2,
                wrap_width=wraps[wrap_key],
            )

        render_items = []
        if has_link:
            render_items.append((int(self.qr_group().get("z", 0)), 0, "qr", None))
        for layer in card.get("layers", []):
            render_items.append((int(layer.get("z", 0)), 1, "layer", layer))

        for _z, _tie, item_type, layer in sorted(render_items, key=lambda item: (item[0], item[1])):
            if item_type == "qr":
                self.draw_qr_group(c, link_text)
                continue
            if not layer or layer.get("visible", True) is False:
                continue
            if layer.get("type") == "image":
                self.draw_image_layer(c, layer)
            elif layer.get("type") == "text":
                self.draw_text_layer(c, layer)
            elif layer.get("type") == "emoji":
                lx = int(layer.get("x", 900))
                ly = int(layer.get("y", 210))
                # Legacy v0.1-v0.2.3 default magnifier sat over STATUS at y≈28.
                # Move only that built-in sticker down; future user-edited stickers keep their saved coordinates.
                if layer.get("id") == "emoji-default-scan" and ly <= 45:
                    ly = 210
                opacity = max(0.1, min(1.0, float(layer.get("opacity", 1.0))))
                fill = blend_hex_colors(self.theme_color("standard_text"), bg, opacity)
                c.create_text(lx, ly, text=layer.get("text", "🔍"), fill=fill, font=("TkDefaultFont", int(layer.get("size", 26))))

    def pil_font_for_size(self, size: int):
        size = max(8, min(144, int(size)))
        for candidate in ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"]:
            try:
                return ImageFont.truetype(candidate, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    def wrap_text_for_pil(self, text: str, font, max_width: int) -> str:
        draw = ImageDraw.Draw(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))
        output = []
        for paragraph in str(text).splitlines() or [""]:
            words = paragraph.split()
            if not words:
                output.append("")
                continue
            line = ""
            for word in words:
                candidate = word if not line else line + " " + word
                try:
                    measured = draw.textlength(candidate, font=font)
                except Exception:
                    measured = len(candidate) * max(6, getattr(font, "size", 12) * 0.6)
                if measured <= max_width or not line:
                    line = candidate
                else:
                    output.append(line)
                    line = word
            if line:
                output.append(line)
        return "\n".join(output)

    def render_text_layer_pil(self, layer: dict):
        if Image is None or ImageDraw is None or ImageFont is None:
            return None
        txt = str(layer.get("text", ""))
        if not txt.strip():
            return None
        size = max(8, min(72, int(layer.get("size", 22))))
        wrap_width = max(80, min(900, int(layer.get("wrap_width", 260))))
        rotation = max(-359, min(359, int(layer.get("rotation", 0))))
        flip_x = bool(layer.get("flip_x", False))
        flip_y = bool(layer.get("flip_y", False))
        opacity = max(0.1, min(1.0, float(layer.get("opacity", 1.0))))
        color = normalize_hex_color(layer.get("color", self.theme_color("standard_text")), self.theme_color("standard_text"))
        cache_key = (txt, size, wrap_width, rotation, flip_x, flip_y, round(opacity, 2), color)
        cached = self.rendered_text_cache.get(cache_key)
        if cached is not None:
            return cached.copy()
        font = self.pil_font_for_size(size)
        wrapped = self.wrap_text_for_pil(txt, font, wrap_width)
        probe = ImageDraw.Draw(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))
        try:
            bbox = probe.multiline_textbbox((0, 0), wrapped, font=font, spacing=4)
            width = max(4, min(1000, bbox[2] - bbox[0] + 8))
            height = max(4, min(1000, bbox[3] - bbox[1] + 8))
        except Exception:
            width = wrap_width + 8
            height = max(size + 8, (wrapped.count("\n") + 1) * (size + 4))
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        draw.multiline_text((4, 4), wrapped, font=font, fill=(*rgb, int(255 * opacity)), spacing=4)
        if flip_x:
            image = ImageOps.mirror(image)
        if flip_y:
            image = ImageOps.flip(image)
        if rotation:
            resampling = getattr(getattr(Image, "Resampling", Image), "BICUBIC")
            image = image.rotate(-rotation, expand=True, resample=resampling)
        self.rendered_text_cache[cache_key] = image.copy()
        return image

    def draw_text_layer(self, canvas: tk.Canvas, layer: dict) -> None:
        txt = str(layer.get("text", ""))
        if not txt.strip():
            return
        x = int(layer.get("x", 740))
        y = int(layer.get("y", 185))
        size = max(8, min(72, int(layer.get("size", 22))))
        wrap_width = max(80, min(900, int(layer.get("wrap_width", 260))))
        opacity = max(0.1, min(1.0, float(layer.get("opacity", 1.0))))
        rotation = int(layer.get("rotation", 0))
        flip_x = bool(layer.get("flip_x", False))
        flip_y = bool(layer.get("flip_y", False))
        if not rotation and not flip_x and not flip_y:
            color = blend_hex_colors(layer.get("color", self.theme_color("standard_text")), self.theme_color("output_background"), opacity)
            canvas.create_text(x, y, anchor="nw", text=txt, fill=color, width=wrap_width, font=("TkDefaultFont", size))
            return
        image = self.render_text_layer_pil(layer)
        if image is None or ImageTk is None:
            return
        photo = ImageTk.PhotoImage(image)
        self.render_image_refs.append(photo)
        canvas.create_image(x, y, anchor="nw", image=photo)

    def transformed_image_pil(self, layer: dict):
        source_path = Path(layer.get("source_path", ""))
        if not source_path.exists() or Image is None:
            return None
        base = self.base_image_cache.get(str(source_path))
        if base is None:
            base = Image.open(source_path).convert("RGBA")
            self.base_image_cache[str(source_path)] = base
        scale = max(10, min(400, int(layer.get("scale", 100))))
        opacity = max(0.1, min(1.0, float(layer.get("opacity", 1.0))))
        rotation = max(-359, min(359, int(layer.get("rotation", 0))))
        flip_x = bool(layer.get("flip_x", False))
        flip_y = bool(layer.get("flip_y", False))
        width = max(4, int(base.width * scale / 100))
        height = max(4, int(base.height * scale / 100))
        cache_key = (str(source_path), width, height, round(opacity, 2), rotation, flip_x, flip_y)
        cached = self.rendered_image_cache.get(cache_key)
        if cached is not None:
            return cached.copy()
        resized = base.resize((width, height), Image.LANCZOS)
        if flip_x:
            resized = ImageOps.mirror(resized)
        if flip_y:
            resized = ImageOps.flip(resized)
        if rotation:
            resampling = getattr(getattr(Image, "Resampling", Image), "BICUBIC")
            resized = resized.rotate(-rotation, expand=True, resample=resampling)
        if opacity < 0.999:
            alpha = resized.getchannel("A")
            alpha = alpha.point(lambda a: int(a * opacity))
            resized.putalpha(alpha)
        self.rendered_image_cache[cache_key] = resized.copy()
        return resized

    def draw_image_layer(self, canvas: tk.Canvas, layer: dict) -> None:
        if ImageTk is None:
            return
        try:
            rendered = self.transformed_image_pil(layer)
            if rendered is None:
                return
            photo = ImageTk.PhotoImage(rendered)
            x = int(layer.get("x", 760))
            y = int(layer.get("y", 245))
            self.render_image_refs.append(photo)
            canvas.create_image(x, y, anchor="nw", image=photo)
        except Exception:
            return

    def draw_qr_group(self, canvas: tk.Canvas, link: str) -> None:
        qr = self.qr_group()
        x = int(qr.get("x", QR_GROUP_DEFAULTS["x"]))
        y = int(qr.get("y", QR_GROUP_DEFAULTS["y"]))
        size = int(qr.get("size", QR_GROUP_DEFAULTS["size"]))
        background = normalize_hex_color(qr.get("background", "#ffffff"), "#ffffff")
        outline = normalize_hex_color(qr.get("outline", self.theme_color("qr_outline")), self.theme_color("qr_outline"))
        label_x, label_y = self.qr_label_position()
        self.draw_display_text(canvas, "qr_label", override_x=label_x, override_y=label_y)
        canvas.create_rectangle(x, y, x + size, y + size, fill=background, outline=outline)
        self.draw_qr(canvas, x, y, size, link)

    def draw_qr(self, canvas: tk.Canvas, x: int, y: int, size: int, link: str) -> None:
        link = (link or "").strip()
        if not link or not QR_AVAILABLE:
            return
        qr_group = self.qr_group()
        foreground = normalize_hex_color(qr_group.get("foreground", "#000000"), "#000000")
        background = normalize_hex_color(qr_group.get("background", "#ffffff"), "#ffffff")
        inner_pad = max(4, min(12, size // 14))
        render_size = max(24, size - inner_pad * 2)
        cache_key = (link, render_size, foreground, background)
        if self.qr_cache_key != cache_key or self.qr_photo is None:
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
            qr.add_data(link)
            qr.make(fit=True)
            img = qr.make_image(fill_color=foreground, back_color=background).convert("RGB")
            resampling = getattr(getattr(Image, "Resampling", Image), "NEAREST")
            img = img.resize((render_size, render_size), resampling)
            self.qr_photo = ImageTk.PhotoImage(img)
            self.qr_cache_key = cache_key
        canvas.create_image(x + inner_pad, y + inner_pad, anchor="nw", image=self.qr_photo)

    def draw_row(self, canvas: tk.Canvas, label_id: str, value: str, accent: str, value_x: int, line_end: int) -> None:
        label_obj = self.display_text_object_by_id(label_id) or {}
        self.draw_display_text(canvas, label_id)
        row = self.top_row_by_label_id(label_id)
        option = self.top_row_option_by_text(row, value)
        if option and option.get("visible", True) is False:
            return
        y = int((option or {}).get("y", label_obj.get("y", 96)))
        x = int((option or {}).get("x", value_x))
        render_value = str((option or {}).get("text", value)).strip()
        if not render_value:
            return
        color = normalize_hex_color((option or {}).get("color", "#f0fff8"), "#f0fff8")
        bar_color = normalize_hex_color((option or {}).get("bar_color", accent), accent)
        family = str((option or {}).get("font_family", "TkDefaultFont")) or "TkDefaultFont"
        size = max(6, min(96, int((option or {}).get("font_size", 15))))
        weight = str((option or {}).get("font_weight", "bold")) or "bold"
        slant = str((option or {}).get("font_slant", "roman")) or "roman"
        styles = []
        if weight == "bold":
            styles.append("bold")
        if slant == "italic":
            styles.append("italic")
        canvas.create_text(x, y, anchor="w", text=render_value, fill=color, font=(family, size, *styles))
        canvas.create_line(x, y + 15, max(x + 10, line_end), y + 15, fill=normalize_hex_color(str((row or {}).get("line_color", self.theme_color("top_row_line"))), self.theme_color("top_row_line")))
        canvas.create_rectangle(x - 8, y - 14, x - 4, y + 17, fill=bar_color, outline="")

    def draw_boxed_text(self, canvas: tk.Canvas, x: int, y: int, label_id: str, value: str, width: int, height: int, accent: str, max_lines: int = 2, wrap_width: int | None = None) -> None:
        self.draw_display_text(canvas, label_id)
        canvas.create_rectangle(x, y, x + width, y + height, fill=self.theme_color("box_background"), outline=self.theme_color("box_border"))
        canvas.create_rectangle(x, y, x + 4, y + height, fill=accent, outline="")
        region_limit = max(BOX_WRAP_MIN, (x + width - BOXED_CONTENT_TEXT_RIGHT_PAD) - (x + BOXED_CONTENT_TEXT_LEFT_PAD))
        requested_wrap = region_limit if wrap_width is None else int(wrap_width)
        effective_wrap = max(BOX_WRAP_MIN, min(region_limit, requested_wrap))

        # Use the Canvas text engine for both measurement and final wrapping.
        # The prior implementation measured with tkfont.Font and then rendered a
        # separately-created Canvas font. On some Linux font/DPI combinations
        # those two paths disagree, causing an 858px setting to wrap near the old
        # visual limit. Canvas-native probing guarantees the visible line uses
        # the real boxed-region width on the current display.
        wrapped = self.wrap_text_for_canvas(
            canvas,
            value,
            ("TkDefaultFont", 12),
            max_width=effective_wrap,
            max_lines=max_lines,
        )
        canvas.create_text(
            x + BOXED_CONTENT_TEXT_LEFT_PAD,
            y + 11,
            anchor="nw",
            text=wrapped,
            fill=self.theme_color("box_text"),
            font=("TkDefaultFont", 12),
            width=effective_wrap,
            justify="left",
        )

    def wrap_text_for_canvas(self, canvas: tk.Canvas, text: str, font_spec, max_width: int, max_lines: int = 2) -> str:
        """Return text clipped to max_lines using the Canvas's actual font layout.

        Canvas and tkfont can resolve named/default fonts differently depending
        on DPI, desktop scaling, and Linux font substitution. Temporary offscreen
        Canvas items make the measurement path identical to final rendering.
        """
        normalized = " ".join((text or "").replace("\n", " ").split())
        if not normalized:
            return ""

        max_width = max(BOX_WRAP_MIN, int(max_width))
        max_lines = max(1, int(max_lines))
        cache = getattr(self, "_boxed_canvas_wrap_cache", None)
        if cache is None:
            cache = {}
            self._boxed_canvas_wrap_cache = cache
        try:
            scaling = round(float(self.root.tk.call("tk", "scaling")), 4)
        except Exception:
            scaling = 0.0
        cache_key = (normalized, tuple(font_spec), max_width, max_lines, scaling)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        probe_x = -10000
        probe_y = -10000

        def item_height(candidate: str) -> int:
            item = canvas.create_text(
                probe_x,
                probe_y,
                anchor="nw",
                text=candidate,
                font=font_spec,
                width=max_width,
                justify="left",
            )
            bbox = canvas.bbox(item)
            canvas.delete(item)
            return 0 if not bbox else int(bbox[3] - bbox[1])

        line_probe = "\n".join(["Ag"] * max_lines)
        allowed_height = item_height(line_probe)
        if item_height(normalized) <= allowed_height:
            cache[cache_key] = normalized
            return normalized

        words = normalized.split()
        lo, hi = 0, len(words)
        best = "..."
        while lo <= hi:
            mid = (lo + hi) // 2
            prefix = " ".join(words[:mid]).rstrip()
            candidate = (prefix + "...") if prefix else "..."
            if item_height(candidate) <= allowed_height:
                best = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        cache[cache_key] = best
        # Bound the cache because redraws may see many temporary editor values.
        if len(cache) > 256:
            for old_key in list(cache)[:64]:
                cache.pop(old_key, None)
        return best

    def wrap_text_pixels(self, text: str, font_spec, max_width: int, max_lines: int = 2) -> str:
        text = (text or "").replace("\n", " ").strip()
        if not text:
            return ""
        font = tkfont.Font(root=self.root, font=font_spec)
        words = text.split()
        lines = []
        current = ""

        def fit_with_ellipsis(s: str) -> str:
            if font.measure(s) <= max_width:
                return s
            ell = "..."
            while s and font.measure(s + ell) > max_width:
                s = s[:-1]
            return (s.rstrip() + ell) if s else ell

        i = 0
        while i < len(words):
            word = words[i]
            candidate = word if not current else current + " " + word
            if font.measure(candidate) <= max_width:
                current = candidate
                i += 1
                continue
            if not current:
                fragment = word
                while fragment and font.measure(fragment) > max_width:
                    fragment = fragment[:-1]
                if not fragment:
                    fragment = word[:1]
                current = fragment
                words[i] = word[len(fragment):] if len(fragment) < len(word) else ""
                if not words[i]:
                    i += 1
            lines.append(current)
            current = ""
            if len(lines) == max_lines:
                break
        if len(lines) < max_lines and current:
            lines.append(current)
        remaining_text = " ".join(words[i:]).strip()
        if len(lines) == max_lines and remaining_text:
            lines[-1] = fit_with_ellipsis(lines[-1] + " " + remaining_text if lines[-1] else remaining_text)
        return "\n".join(lines[:max_lines])

    def scan_once(self) -> None:
        if self.store.active_card().get("type") == "blank":
            return
        # Reset any in-flight scan immediately. Older scheduled frames exit when
        # their token no longer matches self.scan_token.
        self.scan_token += 1
        token = self.scan_token
        self.scan_active = True
        self.scan_y = 74
        self.redraw_output()
        self.run_scan_frame(loop=False, token=token)

    def toggle_scan_loop(self) -> None:
        self.scan_token += 1
        token = self.scan_token
        self.store.data["under_header"]["scan_loop"] = bool(self.scan_loop_var.get())
        self.store.mark_dirty("scan-loop-toggled")
        if self.scan_loop_var.get():
            self.scan_active = True
            self.scan_y = 74
            self.run_scan_frame(loop=True, token=token)
        else:
            self.scan_active = False
            self.redraw_output()
        self.schedule_autosave()

    def run_scan_frame(self, loop: bool, token: int | None = None) -> None:
        if token is None:
            token = self.scan_token
        if token != self.scan_token:
            return
        if not self.scan_active:
            return
        if self.store.active_card().get("type") == "blank":
            self.scan_active = False
            return
        self.redraw_output()
        c = self.output_canvas
        accent = self.scanner_color_var.get().strip() or "#00ff99"
        c.create_rectangle(42, self.scan_y, OUTPUT_WIDTH - 42, self.scan_y + 3, fill=accent, outline="")
        c.create_rectangle(42, self.scan_y + 4, OUTPUT_WIDTH - 42, self.scan_y + 15, fill=self.theme_color("scan_trail"), outline="", stipple="gray50")
        self.draw_display_text(c, "scan_label")
        self.scan_y += 8
        if self.scan_y > OUTPUT_HEIGHT - 34:
            if loop or self.scan_loop_var.get():
                self.scan_y = 74
            else:
                self.scan_active = False
                self.redraw_output()
                return
        delay = max(20, int(self.scan_speed_var.get()))
        self.root.after(delay, lambda: self.run_scan_frame(loop=loop, token=token))

    def on_scan_speed_drag(self, value: str) -> None:
        ms = int(float(value))
        self.scan_speed_var.set(ms)
        # Tk can fire the Scale callback during widget construction before speed_label exists.
        # Guarding here prevents a startup traceback and keeps launch stable.
        if hasattr(self, "speed_label"):
            self.speed_label.configure(text=f"{ms} ms")
        if hasattr(self, "store"):
            self.store.data["under_header"]["scan_speed_ms"] = ms
            self.store.mark_dirty("scan-speed-changed")

    def on_resource_profile_changed(self, _event=None) -> None:
        profile = self.resource_profile_var.get()
        profile_data = RESOURCE_PROFILES.get(profile, RESOURCE_PROFILES["low"])
        self.scan_speed_var.set(profile_data["scan_ms"])
        self.speed_scale.set(profile_data["scan_ms"])
        self.speed_label.configure(text=f"{profile_data['scan_ms']} ms")
        self.store.data["header"]["resource_profile"] = profile
        self.store.data["under_header"]["scan_speed_ms"] = profile_data["scan_ms"]
        self.store.mark_dirty("resource-profile-changed")
        self.schedule_autosave()

    def on_setting_changed(self) -> None:
        self.store.data["under_header"]["output_visible"] = bool(self.output_visible_var.get())
        self.store.mark_dirty("setting-changed")
        self.schedule_autosave()

    def recover_output_window_on_launch(self) -> None:
        """Map the OBS output window safely on KWin/X11/Wayland.

        Borderless windows can fail to visibly map if overrideredirect is applied
        too early. Startup always uses normal framed mode; the user can enable
        borderless later with Apply OBS Mode.
        """
        try:
            self.output.overrideredirect(False)
        except tk.TclError:
            pass
        try:
            self.output.attributes("-topmost", False)
        except tk.TclError:
            pass

        geo = self.store.data["under_header"].get("output_geometry") or DEFAULT_OUTPUT_GEOMETRY
        if not is_safe_geometry(geo, OUTPUT_WIDTH, OUTPUT_HEIGHT):
            geo = DEFAULT_OUTPUT_GEOMETRY
        try:
            self.output.geometry(geo)
        except tk.TclError:
            self.output.geometry(DEFAULT_OUTPUT_GEOMETRY)

        self.output.title(OUTPUT_TITLE)
        self.output.resizable(False, False)
        if self.output_visible_var.get():
            self.output.deiconify()
            self.output.lift()
            self.output.update_idletasks()
            # A second lift shortly after launch helps on KDE/KWin where a Toplevel
            # can exist but not paint until after the mainloop cycles once.
            self.root.after(250, self.bring_output_front)

        self.store.data["under_header"]["output_borderless"] = False
        self.store.data["under_header"]["output_topmost"] = False
        self.store.data["under_header"]["output_geometry"] = geo
        self.store.mark_dirty("output-launch-recovery")
        self.schedule_autosave()


    def rescue_output_window(self) -> None:
        """Emergency recovery button for OBS output visibility."""
        self.output_borderless_var.set(False)
        self.output_topmost_var.set(False)

        try:
            self.output.withdraw()
            self.output.update_idletasks()
            self._set_output_window_type_hint(False)
            self.output.overrideredirect(False)
            self.output.attributes("-topmost", False)
            self.output.geometry(DEFAULT_OUTPUT_GEOMETRY)
            self.output.resizable(False, False)
            self.output.deiconify()
            self.output.geometry(DEFAULT_OUTPUT_GEOMETRY)
            self.output.lift()
            self.output.update_idletasks()
            try:
                self.output.focus_force()
            except tk.TclError:
                pass
        except tk.TclError:
            pass

        self.output_visible_var.set(True)
        self.store.data["under_header"]["output_visible"] = True
        self.store.data["under_header"]["output_borderless"] = False
        self.store.data["under_header"]["output_topmost"] = False
        self.store.data["under_header"]["output_geometry"] = DEFAULT_OUTPUT_GEOMETRY
        self.store.mark_dirty("output-window-rescued")
        self.schedule_autosave()
        self.status_var.set("Output window rescued")


    def _set_output_window_type_hint(self, borderless: bool) -> None:
        """Best-effort X11/KWin hint for borderless OBS capture windows."""
        try:
            windowing = str(self.output.tk.call("tk", "windowingsystem"))
        except tk.TclError:
            return

        if windowing != "x11":
            return

        try:
            hint = "splash" if borderless else "normal"
            self.output.tk.call("wm", "attributes", self.output._w, "-type", hint)
        except tk.TclError:
            pass

    def apply_output_window_style(self, save: bool = True) -> None:
        """Apply OBS output window behavior using a safe withdraw/remap cycle.

        Tk only guarantees overrideredirect changes when the window is first
        mapped, or when it is remapped from withdrawn back to normal.
        """
        borderless = bool(self.output_borderless_var.get())
        topmost = bool(self.output_topmost_var.get())

        try:
            current_geo = self.output.geometry()
        except tk.TclError:
            current_geo = DEFAULT_OUTPUT_GEOMETRY

        if not is_safe_geometry(current_geo, OUTPUT_WIDTH, OUTPUT_HEIGHT):
            current_geo = DEFAULT_OUTPUT_GEOMETRY

        try:
            self.output.withdraw()
            self.output.update_idletasks()

            self._set_output_window_type_hint(borderless)
            self.output.overrideredirect(borderless)
            self.output.geometry(current_geo)
            self.output.resizable(False, False)

            try:
                self.output.attributes("-topmost", topmost)
            except tk.TclError:
                pass

            self.output.deiconify()
            self.output.geometry(current_geo)
            self.output.update_idletasks()
            self.output.lift()

            def finish_remap() -> None:
                try:
                    self.output.geometry(current_geo)
                    self.output.resizable(False, False)
                    if topmost:
                        self.output.attributes("-topmost", True)
                    self.output.lift()
                except tk.TclError:
                    pass

            self.root.after(80, finish_remap)
        except tk.TclError:
            pass

        if save:
            self.store.data["under_header"]["output_topmost"] = topmost
            self.store.data["under_header"]["output_borderless"] = borderless
            self.store.data["under_header"]["output_geometry"] = current_geo
            self.store.mark_dirty("output-style-changed")
            self.schedule_autosave()

    def enable_obs_output_mode(self) -> None:
        self.show_output()
        self.output.update_idletasks()
        self.output_topmost_var.set(True)
        self.output_borderless_var.set(True)
        self.apply_output_window_style(save=True)
        self.bring_output_front()
        self.status_var.set("OBS output mode enabled")

    def disable_obs_output_mode(self) -> None:
        self.output_borderless_var.set(False)
        self.output_topmost_var.set(False)
        self.apply_output_window_style(save=True)
        self.bring_output_front()
        self.status_var.set("Normal output mode enabled")

    def bring_output_front(self) -> None:
        self.output.deiconify()
        self.output.lift()
        try:
            self.output.focus_force()
        except tk.TclError:
            pass
        self.output_visible_var.set(True)
        self.on_setting_changed()
        self.status_var.set("Output brought to front")


    def reset_output_window_position(self) -> None:
        """Reset the OBS output window to safe normal framed mode."""
        self.output_borderless_var.set(False)
        self.output_topmost_var.set(False)

        try:
            self.output.geometry(DEFAULT_OUTPUT_GEOMETRY)
        except tk.TclError:
            pass

        self.apply_output_window_style(save=False)

        self.store.data["under_header"]["output_geometry"] = DEFAULT_OUTPUT_GEOMETRY
        self.store.data["under_header"]["output_borderless"] = False
        self.store.data["under_header"]["output_topmost"] = False
        self.store.mark_dirty("output-window-reset")
        self.schedule_autosave()
        self.status_var.set("Output window reset")

    def save_output_settings(self) -> None:
        self.store.data["under_header"]["output_visible"] = bool(self.output_visible_var.get())
        self.store.data["under_header"]["output_topmost"] = bool(self.output_topmost_var.get())
        self.store.data["under_header"]["output_borderless"] = bool(self.output_borderless_var.get())
        try:
            self.store.data["under_header"]["output_geometry"] = self.output.geometry()
        except tk.TclError:
            self.store.data["under_header"]["output_geometry"] = DEFAULT_OUTPUT_GEOMETRY
        self.store.save("output-settings-save")
        self.status_var.set("Output settings saved")

    def show_output(self) -> None:
        self.output.deiconify()
        self.output.title(OUTPUT_TITLE)
        self.output.geometry(self.store.data["under_header"].get("output_geometry", DEFAULT_OUTPUT_GEOMETRY))
        self.output.update_idletasks()
        self.output.lift()
        self.output_visible_var.set(True)
        self.on_setting_changed()

    def hide_output(self) -> None:
        self.output.withdraw()
        self.output_visible_var.set(False)
        self.on_setting_changed()

    def save_now(self) -> None:
        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        self.apply_display_text_editor_without_reschedule()
        self.apply_top_row_option_without_reschedule()
        self.apply_qr_group_without_reschedule()
        self.refresh_top_dropdown_values()
        self.remember_window_geometry()
        self.store.save("manual-save")
        self.redraw_output()
        self.status_var.set(f"Saved: {self.store.path.name}")

    def save_as(self) -> None:
        path = filedialog.asksaveasfilename(title="Save .buttstore episode", defaultextension=".buttstore", filetypes=[("3DCP ButtStore", "*.buttstore"), ("JSON", "*.json"), ("All files", "*.*")], initialdir=str(BUTTSTORE_DIR))
        if not path:
            return
        self.apply_editor_to_card_without_reschedule()
        self.apply_display_text_editor_without_reschedule()
        self.apply_top_row_option_without_reschedule()
        self.apply_qr_group_without_reschedule()
        self.refresh_top_dropdown_values()
        self.remember_window_geometry()
        self.store.save_as(Path(path))
        self.status_var.set(f"Saved As: {Path(path).name}")

    def load_buttstore(self) -> None:
        path = filedialog.askopenfilename(title="Load .buttstore episode", filetypes=[("3DCP ButtStore", "*.buttstore"), ("JSON", "*.json"), ("All files", "*.*")], initialdir=str(BUTTSTORE_DIR))
        if not path:
            return
        try:
            self.store = ButtStore.load_or_create(Path(path))
        except Exception as exc:
            messagebox.showerror("Could not load .buttstore", str(exc))
            return
        self.scan_loop_var.set(bool(self.store.data["under_header"].get("scan_loop", False)))
        self.output_visible_var.set(bool(self.store.data["under_header"].get("output_visible", True)))
        self.resource_profile_var.set(self.store.data["header"].get("resource_profile", "low"))
        self.scan_speed_var.set(int(self.store.data["under_header"].get("scan_speed_ms", 67)))
        self.scanner_color_var.set(self.store.data["under_header"].get("scanner_color", "#00ff99"))
        self.speed_scale.set(self.scan_speed_var.get())
        self.speed_label.configure(text=f"{self.scan_speed_var.get()} ms")
        self.qr_cache_key = None
        self.qr_photo = None
        self.base_image_cache = {}
        self.rendered_image_cache = {}
        self.refresh_deck_buttons()
        self.load_active_card_into_editor()
        self.redraw_output()
        self.status_var.set(f"Loaded: {Path(path).name}")

    def to_default_wipe(self) -> None:
        approved = messagebox.askyesno("To-default wipe", "Reset editable card content to public-clean defaults?\n\nFooter serial values will move forward, not backward.")
        if not approved:
            return
        self.store.wipe_to_default()
        self.scan_loop_var.set(False)
        self.output_visible_var.set(True)
        self.resource_profile_var.set("low")
        self.scan_speed_var.set(RESOURCE_PROFILES["low"]["scan_ms"])
        self.scanner_color_var.set("#00ff99")
        self.qr_cache_key = None
        self.qr_photo = None
        self.base_image_cache = {}
        self.rendered_image_cache = {}
        self.speed_scale.set(self.scan_speed_var.get())
        self.speed_label.configure(text=f"{self.scan_speed_var.get()} ms")
        self.refresh_deck_buttons()
        self.load_active_card_into_editor()
        self.redraw_output()
        self.status_var.set("To-default wipe complete")

    def remember_window_geometry(self) -> None:
        try:
            self.store.data["under_header"]["controller_geometry"] = self.root.geometry()
            self.store.data["under_header"]["output_geometry"] = self.output.geometry()
        except tk.TclError:
            pass

    def duplicate_buttstore_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        if not BUTTSTORE_DIR.exists():
            return candidates
        patterns = [
            "*_migrated_*.buttstore",
            "*_legacy_*.buttstore",
            "default_episode_template.buttstore",
        ]
        seen = set()
        for pattern in patterns:
            for path in BUTTSTORE_DIR.glob(pattern):
                if path.is_file() and path not in seen:
                    candidates.append(path)
                    seen.add(path)
        return candidates

    def archive_duplicate_buttstores_after_load(self) -> None:
        """Move duplicate-looking buttstores aside after the UI is fully available.

        The archive is intentionally temporary: it stays available for review during
        the session and is removed on clean shutdown.
        """
        try:
            candidates = self.duplicate_buttstore_candidates()
            if not candidates:
                return
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_dir = DUPLICATE_ARCHIVE_ROOT / stamp
            archive_dir.mkdir(parents=True, exist_ok=True)

            moved = 0
            for src in candidates:
                dest = archive_dir / src.name
                if dest.exists():
                    n = 1
                    while True:
                        candidate = archive_dir / f"{src.stem}_{n}{src.suffix}"
                        if not candidate.exists():
                            dest = candidate
                            break
                        n += 1
                shutil.move(str(src), str(dest))
                moved += 1

            if moved:
                self.store.data["under_header"]["last_duplicate_archive"] = str(archive_dir)
                self.store.mark_dirty("duplicate-buttstores-archived")
                self.store.save("duplicate-archive-after-load")
                self.status_var.set(f"Archived duplicate buttstores: {moved}")
        except Exception as exc:
            self.status_var.set(f"Duplicate archive skipped: {exc}")

    def cleanup_archived_duplicate_buttstores_on_shutdown(self) -> None:
        """Remove the temporary duplicate archive folder at clean shutdown."""
        try:
            if DUPLICATE_ARCHIVE_ROOT.exists():
                shutil.rmtree(DUPLICATE_ARCHIVE_ROOT)
                self.store.data["under_header"]["last_duplicate_archive_removed_at"] = utc_now()
                self.store.mark_dirty("duplicate-archive-cleaned-on-shutdown")
        except Exception as exc:
            try:
                self.store.data["under_header"]["duplicate_archive_cleanup_error"] = str(exc)
                self.store.mark_dirty("duplicate-archive-cleanup-error")
            except Exception:
                pass

    def export_current_card_png(self) -> None:
        if Image is None:
            messagebox.showerror("Export PNG unavailable", "Pillow is required for PNG export.")
            return

        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        self.apply_display_text_editor_without_reschedule()
        self.apply_top_row_option_without_reschedule()
        self.apply_qr_group_without_reschedule()
        self.refresh_top_dropdown_values()
        self.remember_window_geometry()
        self.store.save("export-current-card")

        export_day = datetime.now().strftime("%Y%m%d")
        export_dir = EXPORT_ROOT_DIR / export_day
        export_dir.mkdir(parents=True, exist_ok=True)
        card = self.store.active_card()
        safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(card.get("label", card.get("id", "card")))).strip("_") or "card"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = export_dir / f"{safe_label}_{timestamp}.png"
        self.output_canvas.update_idletasks()

        try:
            # Tk Canvas can export PostScript without needing a redraw loop.
            ps = self.output_canvas.postscript(colormode="color")
            from io import BytesIO
            img = Image.open(BytesIO(ps.encode("utf-8")))
            img.save(path, "PNG")
            self.status_var.set(f"Exported PNG: {path.name}")
            messagebox.showinfo("Export complete", f"Saved PNG:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not export current card as PNG:\n{exc}")

    def export_all_cards_png(self) -> None:
        if Image is None:
            messagebox.showerror("Export PNG unavailable", "Pillow is required for PNG export.")
            return

        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        self.apply_display_text_editor_without_reschedule()
        self.apply_top_row_option_without_reschedule()
        self.apply_qr_group_without_reschedule()
        self.refresh_top_dropdown_values()
        self.remember_window_geometry()
        self.store.save("export-all-cards")

        export_day = datetime.now().strftime("%Y%m%d")
        export_dir = EXPORT_ROOT_DIR / f"{export_day}_backup"
        export_dir.mkdir(parents=True, exist_ok=True)
        original_id = self.store.data["header"].get("active_card_id")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exported = 0
        errors = []

        try:
            from io import BytesIO
            for index, card in enumerate(self.store.cards(), start=1):
                self.store.data["header"]["active_card_id"] = card.get("id")
                self.load_active_card_into_editor()
                self.redraw_output()
                self.output_canvas.update_idletasks()

                safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(card.get("label", card.get("id", "card")))).strip("_") or "card"
                path = export_dir / f"{index:02d}_{safe_label}_{timestamp}.png"
                try:
                    ps = self.output_canvas.postscript(colormode="color")
                    img = Image.open(BytesIO(ps.encode("utf-8")))
                    img.save(path, "PNG")
                    exported += 1
                except Exception as exc:
                    errors.append(f"{card.get('label', card.get('id'))}: {exc}")

            if original_id:
                self.store.data["header"]["active_card_id"] = original_id
                self.load_active_card_into_editor()
                self.redraw_output()

            if errors:
                messagebox.showwarning("Export completed with warnings", f"Exported {exported} cards.\n\nWarnings:\n" + "\n".join(errors[:5]))
            else:
                messagebox.showinfo("Export complete", f"Exported {exported} cards to:\n{export_dir}")
            self.status_var.set(f"Exported {exported} PNG card(s)")
        except Exception as exc:
            if original_id:
                self.store.data["header"]["active_card_id"] = original_id
                self.load_active_card_into_editor()
                self.redraw_output()
            messagebox.showerror("Export failed", f"Could not export all cards:\n{exc}")

    def on_close(self) -> None:
        self.scan_active = False
        self.scan_token += 1
        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        self.apply_display_text_editor_without_reschedule()
        self.apply_top_row_option_without_reschedule()
        self.apply_qr_group_without_reschedule()
        self.refresh_top_dropdown_values()
        self.remember_window_geometry()
        # Clear temporary duplicate archive before the windows close.
        # The archive exists during the session for review, then gets removed on clean shutdown.
        self.cleanup_archived_duplicate_buttstores_on_shutdown()
        self.store.save("clean-shutdown")
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()

def main() -> int:
    try:
        app = PerspectiveConsoleApp()
        app.run()
        return 0
    except Exception as exc:
        print(f"{APP_NAME} failed: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
