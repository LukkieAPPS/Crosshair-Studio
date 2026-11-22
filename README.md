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

- This repository currently contains source and build scripts. A downloadable installer and automatic update delivery are not published yet.
- The app does not read or modify game memory and does not provide aiming assistance.
- Premium labels in this source are not a working payment or licence system. No payments are processed.
- Global keyboard/mouse hooks may be restricted by some games or security software; compatibility is not guaranteed.
