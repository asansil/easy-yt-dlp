# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Versions use the Python spelling (`2.0.0b1`); release tags use `v2.0.0-beta.1`.

## [Unreleased]

## [2.1.0] - 2026-11-21

Easier clip times, and a copied command that pastes into PowerShell and cmd.

### Changed

- Clip times are typed into `HH:MM:SS` fields with the ":" already in place. The cursor moves on from hours to minutes to seconds as you type, and a first digit from 6 to 9 in the minutes or seconds counts as `06` to `09`. Up and Down change the part under the cursor, and pasted times such as `1:30` are converted. "To the end" replaces an empty end time. For an analyzed video, the times are limited to its length and the clip length is shown.
- Clip sections are passed to yt-dlp as `HH:MM:SS` (for example `--download-sections "*00:01:30-00:02:45"`), easier to read in the command.
- A clip from 00:00:00 to the end adds no `--download-sections` (nor `--force-keyframes-at-cuts`): the whole media is downloaded without cutting it.

### Fixed

- The copied command now works when pasted into PowerShell or cmd. Arguments such as `%(ext)s`, `res,ext:mp4:m4a`, `<=` or `|` are now quoted.
- "Show command" no longer shrinks to a single line when the window is not maximized: it grows with the command (up to 10 lines) and the page scrolls instead.

## [2.0.0] - 2026-10-23

Easy yt-dlp 2: a desktop app that replaces the 1.x console menu.

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

[Unreleased]: https://github.com/asansil/easy-yt-dlp/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/asansil/easy-yt-dlp/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/asansil/easy-yt-dlp/compare/v1.0.1...v2.0.0
