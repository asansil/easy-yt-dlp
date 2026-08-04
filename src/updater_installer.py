import ctypes
import shutil
import tempfile
import urllib.request
import winreg
import zipfile
from pathlib import Path


ENV_DIR = Path.home() / ".ytdlp_env"

YTDLP_URL = (
    "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
)

FFMPEG_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)

DOWNLOAD_TIMEOUT = 30
CHUNK_SIZE = 64 * 1024


def download_file(url: str, destination: Path):
    print(f"Downloading: {url}")

    try:
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0

            with open(destination, "wb") as f:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    downloaded_mb = downloaded / 1_048_576

                    if total_size:
                        percent = downloaded * 100 // total_size
                        total_mb = total_size / 1_048_576
                        print(
                            f"\r  {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({percent}%)",
                            end="",
                            flush=True,
                        )
                    else:
                        print(
                            f"\r  {downloaded_mb:.1f} MB downloaded",
                            end="",
                            flush=True,
                        )

            print()

    except Exception as e:
        raise RuntimeError(
            f"Error downloading {url}\n{e}"
        ) from e


def install_ytdlp():
    destination = ENV_DIR / "yt-dlp.exe"

    print("Installing yt-dlp...")
    download_file(YTDLP_URL, destination)

    print("yt-dlp updated.")


def install_ffmpeg():
    print("Installing FFmpeg...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        zip_path = tmpdir / "ffmpeg.zip"

        download_file(FFMPEG_URL, zip_path)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:

                ffmpeg_member = None
                ffprobe_member = None

                for member in zf.namelist():

                    lower = member.lower()

                    if lower.endswith("/ffmpeg.exe"):
                        ffmpeg_member = member

                    elif lower.endswith("/ffprobe.exe"):
                        ffprobe_member = member

                if not ffmpeg_member or not ffprobe_member:
                    raise RuntimeError(
                        "ffmpeg.exe or ffprobe.exe were not found inside the ZIP."
                    )

                zf.extract(ffmpeg_member, tmpdir)
                zf.extract(ffprobe_member, tmpdir)

                shutil.copy2(
                    tmpdir / ffmpeg_member,
                    ENV_DIR / "ffmpeg.exe"
                )

                shutil.copy2(
                    tmpdir / ffprobe_member,
                    ENV_DIR / "ffprobe.exe"
                )

        except zipfile.BadZipFile as e:
            raise RuntimeError(
                "The FFmpeg ZIP file is corrupted."
            ) from e

    print("FFmpeg updated.")


def update_user_path():
    path = str(ENV_DIR)

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE
        )

        try:
            current_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""

        paths = [p.strip() for p in current_path.split(";") if p.strip()]

        if path.lower() not in [p.lower() for p in paths]:
            paths.append(path)

            new_path = ";".join(paths)

            winreg.SetValueEx(
                key,
                "Path",
                0,
                winreg.REG_EXPAND_SZ,
                new_path
            )

            print("PATH updated.")

        else:
            print("Path already exists in PATH.")

        winreg.CloseKey(key)

    except PermissionError:
        raise RuntimeError(
            "Could not modify user PATH."
        )


def refresh_environment():
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002

    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        "Environment",
        SMTO_ABORTIFHUNG,
        5000,
        None
    )

    print("Environment variables refreshed.")


def main():
    try:
        ENV_DIR.mkdir(exist_ok=True)

        install_ytdlp()
        install_ffmpeg()

        update_user_path()
        refresh_environment()

        print("\nInstallation completed.")

    except Exception as e:
        print(f"\nERROR:\n{e}")


if __name__ == "__main__":
    main()