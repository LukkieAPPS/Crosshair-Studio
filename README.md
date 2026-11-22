# Crosshair Studio

A Windows desktop crosshair customizer with an always-on-top overlay, presets, profiles, and optional keyboard/mouse profile switching.

## Run from source

1. Install Python 3.12 (64-bit).
2. Double-click `start.bat`.

## Build the Windows app

1. Install Python 3.12 (64-bit) and Inno Setup 6.
2. Double-click `build_windows.bat`.
3. Open `installer.iss` in Inno Setup Compiler and compile it.
4. The installer is created at `installer_output/CrosshairStudio_Setup.exe`.

## User data and profiles

Settings, presets, and profiles are stored in `%APPDATA%/Crosshair Studio`, not in the install folder. This allows normal updates to replace app files without removing saved profiles. Older JSON files beside a portable copy are migrated only when the corresponding AppData file does not already exist. Personal settings and profile JSON files are intentionally excluded from this public repository.

## Notes

- The app checks GitHub Releases for newer versions after launch. Updates are offered in-app, downloaded in the background, and SHA-256 verified before installation.
- For updates to be detected, publish a GitHub Release with tag `v1.0.2` (or higher) and attach `CrosshairStudio_Setup.exe` plus a text file named `CrosshairStudio_Setup.exe.sha256` containing the installer's 64-character SHA-256 hash.
- The updater is included in source; the first packaged installer and release assets still need to be built and uploaded from Windows.
- The app does not read or modify game memory and does not provide aiming assistance.
- Premium labels in this source are not a working payment or licence system. No payments are processed.
- Global keyboard/mouse hooks may be restricted by some games or security software; compatibility is not guaranteed.
