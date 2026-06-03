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


def descargar_archivo(url: str, destino: Path):
    print(f"Descargando: {url}")

    try:
        with urllib.request.urlopen(url) as response:
            with open(destino, "wb") as f:
                shutil.copyfileobj(response, f)

    except Exception as e:
        raise RuntimeError(
            f"Error descargando {url}\n{e}"
        ) from e


def instalar_ytdlp():
    destino = ENV_DIR / "yt-dlp.exe"

    print("Instalando yt-dlp...")
    descargar_archivo(YTDLP_URL, destino)

    print("yt-dlp actualizado.")


def instalar_ffmpeg():
    print("Instalando FFmpeg...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        zip_path = tmpdir / "ffmpeg.zip"

        descargar_archivo(FFMPEG_URL, zip_path)

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
                        "No se encontraron ffmpeg.exe o ffprobe.exe dentro del ZIP."
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
                "El ZIP de FFmpeg está corrupto."
            ) from e

    print("FFmpeg actualizado.")


def actualizar_path_usuario():
    ruta = str(ENV_DIR)

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE
        )

        try:
            path_actual, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            path_actual = ""

        rutas = [p.strip() for p in path_actual.split(";") if p.strip()]

        if ruta.lower() not in [p.lower() for p in rutas]:
            rutas.append(ruta)

            nuevo_path = ";".join(rutas)

            winreg.SetValueEx(
                key,
                "Path",
                0,
                winreg.REG_EXPAND_SZ,
                nuevo_path
            )

            print("PATH actualizado.")

        else:
            print("La ruta ya existe en PATH.")

        winreg.CloseKey(key)

    except PermissionError:
        raise RuntimeError(
            "No se pudo modificar el PATH del usuario."
        )


def refrescar_entorno():
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

    print("Variables de entorno refrescadas.")


def main():
    try:
        ENV_DIR.mkdir(exist_ok=True)

        instalar_ytdlp()
        instalar_ffmpeg()

        actualizar_path_usuario()
        refrescar_entorno()

        print("\nInstalación completada.")

    except Exception as e:
        print(f"\nERROR:\n{e}")


if __name__ == "__main__":
    main()