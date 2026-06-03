
# Easy yt-dlp Manager

**Release [v1.0.0](https://github.com/asansil/easy-yt-dlp/releases/tag/v1.0.0)**

Easy yt-dlp Manager is a simple tool that provides an automated setup and a lightweight interface for using [yt-dlp](https://github.com/yt-dlp/yt-dlp).  
It aims to make repetitive download tasks faster and more intuitive while still allowing full access to the original yt-dlp functionality.

---

# 📦 Project Structure

The project is composed of two main executables:

- **Updater / Installer**
- **CLI Interface**

---

# ⚙️ 1. Updater / Installer

The first executable is responsible for preparing the entire environment automatically.

## What it does:

- Downloads the latest version of `yt-dlp`
- Downloads and extracts `FFmpeg` and `FFprobe`
- Stores all tools inside a hidden folder located at:
'C:\Users<YourUser>.ytdlp_env'
- Automatically adds this folder to the **USER PATH** in Windows
- Refreshes environment variables so changes take effect immediately

---

## Result

After running the installer:

- `yt-dlp` can be used directly from **CMD / PowerShell**
- FFmpeg is globally available
- No manual installation is required

This follows the same usage model as the official yt-dlp project.

---

## Updating tools

To update yt-dlp or FFmpeg, simply re-run the installer executable.  
It will overwrite the existing files with the latest versions.

---

# 🖥️ 2. CLI Interface

The second executable is a simple command-line interface built on top of yt-dlp.

## Features (current release [v1.0.0](https://github.com/asansil/easy-yt-dlp/releases/tag/v1.0.0)):

- Download video in maximum available quality (best video + best audio merged)
- Download audio only in high quality (MP3 320kbps)
- Execute custom yt-dlp commands (expert mode)

Custom commands can be found in the official yt-dlp repository documentation.# Easy yt-dlp Manager
