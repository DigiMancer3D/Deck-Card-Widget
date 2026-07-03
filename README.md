# Deck Card Widget

Version: `1.1.0-de`

Deck Card Widget is a public, reusable mod of the 3DCP Perspective Console concept. It keeps the low-resource Tkinter controller + separate OBS output-window design, while adding a storage-backed **Display Edit** tab for changing the output labels that were previously hard-coded.

## Key features

- private controller window
- OBS-friendly output window
- deck card buttons and overflow storage
- emoji sticker layers
- PNG image layers
- custom text layers
- `.buttstore` session persistence
- `.deckbutt` reusable card export/import
- new Display Edit storage for built-in output labels

## Launch

```bash
chmod +x *.sh
./setup_venv_3dcp_console.sh
./launch_deck_card_widget_venv.sh
```

The original compatibility launcher is still present:

```bash
./launch_3dcp_console_venv.sh
```

## Display Edit

Open the **Display Edit** tab. Select a text object from **Display Text Storage**, then edit the text, color, border, font, visibility, and position. Press **Apply Now** for immediate output updates, or let the autosave/update cycle persist the change.

More detail is in:

- `DISPLAY_EDIT_UPDATE_NOTES.md`
- `HARD_CODED_DISPLAY_TEXT_MAP.md`
- `docs/USER_GUIDE.md`
- `docs/OBS_SETUP.md`

## OBS capture title

```text
Deck Card Widget - Output
```

## Compatibility

The main app file remains named `3dcp_perspective_console.py` so older scripts and workflows can still launch it. Older `.buttstore` files are upgraded in-place at load time by adding the new `header.display_text` storage section.
