# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Versions use the Python spelling (`2.0.0b1`); release tags use `v2.0.0-beta.1`.

## [Unreleased]

### Changed

- Scrolling over a drop-down list no longer changes its value; the page scrolls instead.

## [2.0.0b2] - 2026-10-23

### Changed

- New icons for the app and the installer.

### Fixed

- Cancelling a download no longer leaves a temporary folder of about 23 MB in `%TEMP%`.

## [2.0.0b1] - 2026-10-22

First beta of Easy yt-dlp 2: a desktop app that replaces the 1.x console menu.

### Added

- Graphical interface in English and Spanish, with light and dark themes that follow Windows.
- Downloads of videos, audio, playlists and channels (choose which items), subtitles (languages, auto-generated, embedded or separate files) and clips (a time range only).
- Quality, container, audio format and bitrate choices; file-name templates with a live preview and subfolders per uploader or playlist.
- Download queue with parallel downloads, progress, speed, time left, cancel, retry and logs.
- History of downloads with search, "download again" and "open folder".
- Presets: six built-in ones, plus your own; choose a default.
- Advanced options: cookies from the browser, embedded metadata, thumbnails and chapters, SponsorBlock, rate limit, download archive and extra yt-dlp arguments.
- "Show command" displays the exact yt-dlp command; the Command page runs any yt-dlp arguments.
- One installer (no administrator rights) with an optional PATH entry for yt-dlp and FFmpeg, and an uninstaller that can keep or remove your data.
- First-run setup that downloads yt-dlp, FFmpeg and deno (the JavaScript runtime yt-dlp needs for YouTube), all verified with SHA-256.
- Automatic daily updates of the tools, and in-app updates of Easy yt-dlp itself (optional beta channel).

### Changed

- The 1.x console menu and the separate installer executable are replaced by the app. Easy yt-dlp 2 offers to remove the 1.x tools folder (`%USERPROFILE%\.ytdlp_env`) and its PATH entry.
- Tools now live in `%LOCALAPPDATA%\EasyYtDlp\bin`.

### Removed

- The 1.x scripts. Version 1.0.1 remains available from its release page.

[Unreleased]: https://github.com/asansil/easy-yt-dlp/compare/v2.0.0-beta.2...HEAD
[2.0.0b2]: https://github.com/asansil/easy-yt-dlp/compare/v2.0.0-beta.1...v2.0.0-beta.2
[2.0.0b1]: https://github.com/asansil/easy-yt-dlp/releases/tag/v2.0.0-beta.1
