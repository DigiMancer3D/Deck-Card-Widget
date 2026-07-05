# Linux Desktop Launcher Setup

This guide explains how to create Linux desktop launcher entries for the Deck Card Widget and 3DCP Perspective Console.

The launcher setup is designed for Linux desktop environments such as KDE Plasma / Kubuntu, but the same `.desktop` launcher format is also commonly supported by other Linux desktops.

This guide assumes the app already has working launch scripts, such as:

```text
launch_deck_card_widget_venv.sh
launch_3dcp_console_venv.sh
```

The launcher entries created here will let users start the apps from the desktop application menu and pin them to a toolbar, panel, task manager, or favorites menu.

---

## 1. Confirm the program folder

Replace `{PROGRAM_PATH}` with the real path to the app's program folder.

Example:

```text
/home/YOUR_USERNAME/Deck_Card_Widget/program
```

Additional Example (no-change if set in $HOME):

```text
/home/Deck_Card_Widget/
```

The folder should contain files similar to:

```text
3dcp_perspective_console.py
launch_3dcp_console_venv.sh
launch_deck_card_widget_venv.sh
requirements.txt
icon.png
```

The text `YOUR_USERNAME` is the part to replace with the path to the app's program folder. At this point, the path is normally your OS username you use to login.

---

## 2. Make the launcher scripts executable

Open a terminal and run:

```bash
cd "{PROGRAM_PATH}"

chmod +x launch_deck_card_widget_venv.sh
chmod +x launch_3dcp_console_venv.sh
```

The replacement text `{PROGRAM_PATH}` is being wrapped in " " so spaces and other little things will not mess up your path so make sure the `{PROGRAM_PATH}` contains the full path to the program folder and not just replacing one section of the path to meet the expected output after download.

Test the first launcher:

```bash
./launch_deck_card_widget_venv.sh
```

Then test the second launcher:

```bash
./launch_3dcp_console_venv.sh
```

If both launch correctly from the terminal, continue to the desktop launcher setup.

---

## 3. Create Linux desktop launcher entries

Create a file named:

```text
install_linux_desktop_launchers.sh
```

Paste the following script into it.

Before running it, replace `{PROGRAM_PATH}` with the real absolute path to the program folder.

```bash
#!/usr/bin/env bash

set -e

# Replace this with the full path to the app's program folder.
APP_DIR="{PROGRAM_PATH}"

# The icon image used for both desktop launchers.
APP_ICON="$APP_DIR/icon.png"

# User-local application launcher folder.
APP_DESKTOP_DIR="$HOME/.local/share/applications"

mkdir -p "$APP_DESKTOP_DIR"

# Basic validation.
if [ ! -d "$APP_DIR" ]; then
    echo "ERROR: Program folder not found:"
    echo "$APP_DIR"
    exit 1
fi

if [ ! -f "$APP_ICON" ]; then
    echo "ERROR: icon.png not found:"
    echo "$APP_ICON"
    exit 1
fi

if [ ! -f "$APP_DIR/launch_deck_card_widget_venv.sh" ]; then
    echo "ERROR: launch_deck_card_widget_venv.sh not found in:"
    echo "$APP_DIR"
    exit 1
fi

if [ ! -f "$APP_DIR/launch_3dcp_console_venv.sh" ]; then
    echo "ERROR: launch_3dcp_console_venv.sh not found in:"
    echo "$APP_DIR"
    exit 1
fi

chmod +x "$APP_DIR/launch_deck_card_widget_venv.sh"
chmod +x "$APP_DIR/launch_3dcp_console_venv.sh"

cat > "$APP_DESKTOP_DIR/deck-card-widget.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Deck Card Widget
Comment=Launch the Deck Card Widget for OBS overlays
Exec=$APP_DIR/launch_deck_card_widget_venv.sh
Path=$APP_DIR
Icon=$APP_ICON
Terminal=false
StartupNotify=true
Categories=Utility;Graphics;AudioVideo;
EOF

cat > "$APP_DESKTOP_DIR/3dcp-perspective-console.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=3DCP Perspective Console
Comment=Launch the 3DCP Perspective Console controller
Exec=$APP_DIR/launch_3dcp_console_venv.sh
Path=$APP_DIR
Icon=$APP_ICON
Terminal=false
StartupNotify=true
Categories=Utility;Graphics;AudioVideo;
EOF

chmod +x "$APP_DESKTOP_DIR/deck-card-widget.desktop"
chmod +x "$APP_DESKTOP_DIR/3dcp-perspective-console.desktop"

# Refresh KDE Plasma application cache when available.
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5
else
    echo "Desktop launchers created. Log out/in if they do not appear immediately."
fi

echo
echo "Desktop launchers installed:"
echo "$APP_DESKTOP_DIR/deck-card-widget.desktop"
echo "$APP_DESKTOP_DIR/3dcp-perspective-console.desktop"
echo
echo "Search your application launcher for:"
echo "  Deck Card Widget"
echo "  3DCP Perspective Console"
```

Make the installer script executable:

```bash
chmod +x install_linux_desktop_launchers.sh
```

Run it:

```bash
./install_linux_desktop_launchers.sh
```

---

## 4. Add the apps to the desktop toolbar or panel

After running the installer script, open your Linux application launcher and search for:

```text
Deck Card Widget
```

and:

```text
3DCP Perspective Console
```

On KDE Plasma / Kubuntu, right-click the app entry and choose one of the available options, such as:

```text
Add to Panel
Add to Favorites
Pin to Task Manager
```

The exact wording may vary depending on the desktop environment and panel configuration.

---

## 5. Manual desktop entry examples

These are the `.desktop` files created by the installer script.

They can also be created manually inside:

```text
~/.local/share/applications/
```

### Deck Card Widget

File name:

```text
deck-card-widget.desktop
```

```ini
[Desktop Entry]
Type=Application
Name=Deck Card Widget
Comment=Launch the Deck Card Widget for OBS overlays
Exec={PROGRAM_PATH}/launch_deck_card_widget_venv.sh
Path={PROGRAM_PATH}
Icon={PROGRAM_PATH}/icon.png
Terminal=false
StartupNotify=true
Categories=Utility;Graphics;AudioVideo;
```

### 3DCP Perspective Console

File name:

```text
3dcp-perspective-console.desktop
```

```ini
[Desktop Entry]
Type=Application
Name=3DCP Perspective Console
Comment=Launch the 3DCP Perspective Console controller
Exec={PROGRAM_PATH}/launch_3dcp_console_venv.sh
Path={PROGRAM_PATH}
Icon={PROGRAM_PATH}/icon.png
Terminal=false
StartupNotify=true
Categories=Utility;Graphics;AudioVideo;
```

---

## 6. Troubleshooting

### The app does not appear in the launcher menu

Run one of these commands:

```bash
kbuildsycoca6
```

or:

```bash
kbuildsycoca5
```

If the app still does not appear, log out and log back in.

---

### Clicking the launcher does nothing

First test the launch script directly from the terminal:

```bash
cd "{PROGRAM_PATH}"
./launch_deck_card_widget_venv.sh
```

or:

```bash
cd "{PROGRAM_PATH}"
./launch_3dcp_console_venv.sh
```

If the terminal version fails, fix the launch script first. The `.desktop` launcher depends on the script already working.

---

### The icon does not appear

Confirm that this file exists:

```text
{PROGRAM_PATH}/icon.png
```

Then refresh the desktop application cache:

```bash
kbuildsycoca6
```

or:

```bash
kbuildsycoca5
```

---

### The launcher opens a terminal window

Make sure the `.desktop` file uses:

```ini
Terminal=false
```

---

## 7. Notes for repo maintainers

For public repositories, avoid committing user-specific absolute paths.

Recommended files to include:

```text
icon.png
launch_deck_card_widget_venv.sh
launch_3dcp_console_venv.sh
docs/LINUX-Desktop_Launcher.md
```

Recommended example files, if desired:

```text
docs/examples/deck-card-widget.desktop.example
docs/examples/3dcp-perspective-console.desktop.example
```

Do not commit local runtime folders or private user data unless intentionally publishing example data.

Common local-only folders include:

```text
__pycache__/
user_data/runtime/
user_data/exports/
user_data/imported_pngs/
```

A `.desktop` file can be included as an example, but users usually need to edit the path before using it.
