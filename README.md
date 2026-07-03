# 🃏 Deck Card Widget

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![GUI](https://img.shields.io/badge/GUI-Tkinter-2ea44f)
![OBS](https://img.shields.io/badge/OBS-Window%20Capture-purple)
![No Electron](https://img.shields.io/badge/No-Electron-lightgrey)
![No Pygame](https://img.shields.io/badge/No-Pygame-lightgrey)
![Status](https://img.shields.io/badge/Status-Display%20Edit%20Build-brightgreen)

**Deck Card Widget** is a low-resource desktop overlay controller for streamers, educators, presenters, analysts, and creators who want reusable on-screen “deck cards” without needing a browser source, Electron app, or game engine.

It uses a private **controller window** and a separate OBS-friendly **output window**. The controller edits cards, emoji stickers, PNG layers, custom text layers, and built-in display labels. The output window is the clean visual surface meant to be captured by OBS.

> Built for simple desktop control, fast iteration, and personalized visual cards.

---

## ✨ Highlights

- 🖥️ **Separate controller + output windows**
- 🎥 **OBS Window Capture friendly** output
- 🃏 **Deck card buttons** with overflow card storage
- ✏️ **Display Edit tab** for changing built-in output labels
- 😀 **Personal emoji preset file** using a simple `.emoji` format
- 🖼️ **PNG image layers** for logos, icons, and custom graphics
- 🔤 **Custom text layers** for card-specific messages
- 💾 **`.buttstore` persistence** for app state, cards, display settings, and layout
- 📦 **`.deckbutt` card export/import** for reusable individual cards
- ⚡ **Low-resource design** using Python + Tkinter
- 🚫 No Electron, no browser overlay requirement, no pygame

---

## 🧠 What This Project Does

Deck Card Widget lets a creator prepare multiple “cards” and switch between them during a stream, recording, lesson, presentation, or live discussion.

Each card can contain:

- source or link information
- confidence/status fields
- claim/evidence/question text
- emoji stickers
- imported PNG images
- custom text layers
- editable built-in display labels

The output window can stay clean and stable while the controller window remains private.

---

## 🪟 Output Window

The output window has a stable title for OBS:

```text
Deck Card Widget - Output
```

Recommended OBS setup:

1. Launch Deck Card Widget.
2. Confirm the output window is visible.
3. In OBS, add **Window Capture**.
4. Select:

```text
Deck Card Widget - Output
```

5. Resize/crop in OBS as needed.

The default output canvas is designed around:

```text
960 x 500
```

---

## 📁 Project Layout

Typical standalone folder:

```text
Deck_Card_Widget/
  3dcp_perspective_console.py
  requirements.txt
  launch_deck_card_widget_venv.sh
  launch_3dcp_console_venv.sh
  setup_venv_3dcp_console.sh
  doctor_deck_card_widget.sh
  acceptance_deck_card_widget.sh
  data/
    emoji_presets/
      default_presets.emoji
    templates/
      default_episode_template.buttstore
  docs/
  user_data/                  # created at runtime
```

The app stores user/runtime files outside the main code path when possible:

```text
user_data/
  buttstores/
  deckbutts/
  exports/
  imported_pngs/
  runtime/
  current.emoji
  .venv/
```

Do not delete `user_data/` unless the goal is to reset local cards, presets, runtime state, and exports.

---

## ✅ Requirements

Minimum practical requirements:

- Python 3.10 or newer
- Tkinter / Tcl-Tk support
- pip
- a desktop session capable of showing GUI windows
- Pillow
- qrcode

Python package requirements are listed in:

```text
requirements.txt
```

Current pip requirements:

```text
qrcode[pil]>=7.4.2
Pillow>=10.0.0
```

---

## 🚀 Quick Start: Kubuntu / Ubuntu / Debian

This project was designed and tested around a Kubuntu 24 desktop workflow using X11/Wayland-aware window recovery.

Install system pieces:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk python3-full
```

From the project folder:

```bash
chmod +x *.sh
./setup_venv_3dcp_console.sh
./launch_deck_card_widget_venv.sh
```

Optional checks:

```bash
./doctor_deck_card_widget.sh
./acceptance_deck_card_widget.sh
```

Compatibility launcher:

```bash
./launch_3dcp_console_venv.sh
```

---

## 🐧 Arch Linux Setup

Install Python and Tk support:

```bash
sudo pacman -Syu python tk
```

Then run the included setup script:

```bash
chmod +x *.sh
./setup_venv_3dcp_console.sh
./launch_deck_card_widget_venv.sh
```

Manual fallback:

```bash
python -m venv user_data/.venv
source user_data/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python 3dcp_perspective_console.py
```

Tkinter test:

```bash
python -m tkinter
```

A small Tk test window should appear.

---

## 🍎 macOS Setup

Recommended: install Python from the official Python.org macOS installer, because it normally includes working Tkinter support.

Verify Tkinter:

```bash
python3 -m tkinter
```

Create a local virtual environment:

```bash
python3 -m venv user_data/.venv
source user_data/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python 3dcp_perspective_console.py
```

The included `.sh` launchers may also work from Terminal after permissions are set:

```bash
chmod +x *.sh
./setup_venv_3dcp_console.sh
./launch_deck_card_widget_venv.sh
```

If Tkinter fails on a Homebrew-based Python install, use the Python.org installer or install the matching Tk/Tcl support for that Python version.

---

## 🪟 Windows Setup

The included shell scripts are designed for Linux/macOS-style terminals. On Windows, use PowerShell or Windows Terminal with Python installed.

Verify Tkinter:

```powershell
py -m tkinter
```

Create and activate a local virtual environment:

```powershell
py -m venv user_data\.venv
.\user_data\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python .\3dcp_perspective_console.py
```

If PowerShell blocks activation for the current terminal session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\user_data\.venv\Scripts\Activate.ps1
```

Windows users can also run the app through Git Bash or WSL, but native PowerShell is usually simpler for a normal desktop launch.

---

## 🎛️ Basic Use

1. Launch the app.
2. Use the private controller window to edit the active card.
3. Use the sidebar deck buttons to switch between the first six cards.
4. Use **Deck Card Storage** for extra cards.
5. Capture the output window in OBS.
6. Save/export cards as needed.

Common card tools:

- **Add Source**: create a normal editable card
- **Add Blank**: create a blank/hide card
- **Duplicate Card**: copy the active card
- **Delete Card**: remove the active card
- **Save Card**: export one reusable `.deckbutt`
- **Load Card**: import a `.deckbutt`
- **Export Card PNG**: save the current visual card as PNG
- **Export All PNGs**: export every card

---

## ✏️ Display Edit Tab

The **Display Edit** tab controls built-in output labels that were previously hard-coded into the display renderer.

Use it to change public-facing text such as:

- top title
- status label
- card type label
- confidence label
- QR label
- brand/subtitle labels
- claim/evidence/question section labels
- scan animation label

Display Edit supports:

- text editing
- text color
- optional border
- border color
- font selection
- default text reset
- default color reset
- default font reset
- show/hide
- X/Y movement
- nudge buttons
- snap/move buttons
- **Apply Now** for immediate refresh

Display settings are stored in the active `.buttstore` under:

```json
header.display_text
```

Older `.buttstore` files are upgraded when loaded by adding the missing `header.display_text` section without deleting existing cards or layers.

---

## 😀 Personalized Emoji Presets

Deck Card Widget supports a simple `.emoji` text format so users can personalize the emoji picker.

Default packaged file:

```text
data/emoji_presets/default_presets.emoji
```

Optional user override file:

```text
user_data/current.emoji
```

When `user_data/current.emoji` exists, the app loads it first. If it does not exist, the packaged default preset file is used.

### Create a personal emoji file

From the project folder:

```bash
mkdir -p user_data
cp data/emoji_presets/default_presets.emoji user_data/current.emoji
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force user_data
Copy-Item data\emoji_presets\default_presets.emoji user_data\current.emoji
```

Then edit:

```text
user_data/current.emoji
```

### `.emoji` record format

Each emoji record uses:

```text
emoji|name|category /,
```

Examples:

```text
✅|Confirmed|Status /,
❌|Rejected|Status /,
🧪|Experiment|Lab /,
🎬|Scene|Streaming /,
📌|Pinned Point|Notes /,
```

Minimal emoji-only records also work:

```text
🔥 /,
👀 /,
💡 /,
```

Names and categories are filled with defaults when omitted.

### Emoji editing tips

- Save the file as UTF-8.
- Keep the record separator `/,` after each entry.
- Use short names for cleaner picker display.
- Group related emoji with the same category name.
- Restart the app after changing `current.emoji` so presets reload cleanly.

---

## 💾 Storage Formats

### `.buttstore`

A `.buttstore` stores the full app session state:

- deck cards
- active card
- output/controller geometry
- display text settings
- layer data
- runtime metadata

### `.deckbutt`

A `.deckbutt` stores one reusable deck card.

Useful for:

- reusable stream cards
- card templates
- sharing card layouts
- keeping a personal card library

### `.emoji`

A `.emoji` file stores emoji presets for the emoji sticker picker.

---

## 🔥 Hotkeys

Hotkeys work when the controller has focus and are ignored while typing in text fields.

```text
Ctrl+1 ... Ctrl+6    Select deck cards
Ctrl+B               Blank / Hide
Ctrl+O               Show output
Ctrl+Shift+O         Hide output
Ctrl+R               Scan Once
Ctrl+L               Toggle Scan Loop
Ctrl+S               Save + Apply
Ctrl+E               Export Card PNG
Ctrl+Alt+R           Rescue Output Window
Ctrl+Alt+O           Toggle OBS mode
```

---

## 🧪 Testing

Linux/macOS:

```bash
./acceptance_deck_card_widget.sh
```

Manual Python compile check:

```bash
python3 -m py_compile 3dcp_perspective_console.py
```

Windows PowerShell:

```powershell
python -m py_compile .\3dcp_perspective_console.py
```

Tkinter check:

```bash
python -m tkinter
```

A small test window should appear if Tkinter is working.

---

## 🔄 Updating

Recommended update flow:

1. Close Deck Card Widget.
2. Back up `user_data/`.
3. Replace the app folder with the new version.
4. Restore or keep `user_data/` beside the app folder.
5. Run setup again:

```bash
./setup_venv_3dcp_console.sh
```

6. Launch:

```bash
./launch_deck_card_widget_venv.sh
```

For Windows manual installs, re-run:

```powershell
.\user_data\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\3dcp_perspective_console.py
```

Existing `.buttstore` files should remain usable. New storage sections are added on load when needed.

---

## 🛟 Troubleshooting

### Output window is missing

Use the **Output Tools** tab:

1. Press **Rescue Output Window**.
2. Press **Reset Output Window** if needed.
3. Re-select the output window in OBS if OBS keeps an old target.

Hotkey:

```text
Ctrl+Alt+R
```

### OBS cannot see the output window

Confirm the output window title:

```text
Deck Card Widget - Output
```

Then refresh or recreate the OBS Window Capture source.

### Tkinter is missing

Run:

```bash
python -m tkinter
```

If no test window opens, install or repair Tkinter/Tcl-Tk for the active Python installation.

Linux users usually need a system package such as `python3-tk` or `tk`.

### QR/Pillow dependencies are missing

Run the setup script again:

```bash
./setup_venv_3dcp_console.sh
```

Manual fallback:

```bash
python -m pip install -r requirements.txt
```

### Wayland / KDE / KWin note

Some Linux desktop environments handle borderless or always-on-top windows differently. The app starts in normal framed mode for safer recovery. Enable OBS/borderless mode only after confirming the output window is visible.

---

## 🧭 History

Deck Card Widget is a standalone public project evolved from the original **3DCP Perspective Console** concept and implementation approach.

Original project history:

https://github.com/DigiMancer3D/3DChangesPerspectives/tree/main/PerspectiveConsole

This standalone version focuses on reusable deck-card overlays, public-facing display labels, emoji customization, OBS capture, and storage-backed editing.

---

## 🤝 Suggested Use Cases

- livestream discussion cards
- VTuber or PNGTuber overlay panels
- lesson/presentation cards
- claim/evidence/source review overlays
- podcast visual prompts
- stream segment cards
- reusable branded information cards
- OBS-friendly local overlays

---

## 🏷️ Suggested GitHub Repo Details

### Description

```text
Low-resource Python/Tkinter deck-card overlay controller for OBS, with editable display labels, emoji/PNG/text layers, deck storage, and standalone .buttstore persistence.
```

### Topics / Tags

```text
deck-card-widget
obs-overlay
tkinter
python
streamer-tools
vtuber-tools
png-overlay
emoji-presets
deck-cards
low-resource
no-electron
no-pygame
window-capture
tkinter-gui
content-creator-tools
overlay-controller
display-edit
buttstore
deckbutt
linux-desktop
kubuntu
arch-linux
windows
macos
```

---

## 📌 Notes

Deck Card Widget is meant to be easy to run, easy to customize, and easy to capture. It keeps the moving parts simple: one Python app, local files, a desktop GUI, and an OBS-visible output window.
