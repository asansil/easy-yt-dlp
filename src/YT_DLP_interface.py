import shlex
import subprocess

from tkinter import Tk
from tkinter.filedialog import askdirectory


def seleccionar_carpeta():
    root = Tk()
    root.withdraw()

    carpeta = askdirectory(
        title="Selecciona carpeta de destino"
    )

    root.destroy()

    return carpeta


def ejecutar_ytdlp(url, argumentos):
    comando = ["yt-dlp"]

    comando.extend(argumentos)
    comando.append(url)

    try:
        resultado = subprocess.run(comando)

        if resultado.returncode != 0:
            print(
                f"\nLa descarga terminó con código de error "
                f"{resultado.returncode}"
            )

    except FileNotFoundError:
        print(
            "\nNo se encontró yt-dlp en el PATH.\n"
            "Ejecute primero instalador_actualizador.py."
        )

    except Exception as e:
        print(f"\nError inesperado:\n{e}")


def video_maxima_calidad():
    url = input("\nURL: ").strip()

    carpeta = seleccionar_carpeta()

    if not carpeta:
        print("\nOperación cancelada.")
        return

    ejecutar_ytdlp(
        url,
        [
            "-P",
            carpeta,
            "-f",
            "bestvideo+bestaudio/best",
            "--merge-output-format",
            "mkv"
        ]
    )


def audio_maxima_calidad():
    url = input("\nURL: ").strip()

    carpeta = seleccionar_carpeta()

    if not carpeta:
        print("\nOperación cancelada.")
        return

    ejecutar_ytdlp(
        url,
        [
            "-P",
            carpeta,
            "-f",
            "bestaudio/best",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "320K"
        ]
    )


def modo_experto():
    url = input("\nURL: ").strip()

    carpeta = seleccionar_carpeta()

    if not carpeta:
        print("\nOperación cancelada.")
        return

    argumentos = input(
        "Argumentos de yt-dlp: "
    ).strip()

    try:
        args = shlex.split(argumentos)

        args = ["-P", carpeta] + args

        ejecutar_ytdlp(url, args)

    except ValueError as e:
        print(f"\nError interpretando argumentos:\n{e}")


def mostrar_menu():
    print("\n========================")
    print(" Descargador yt-dlp")
    print("========================")
    print("1. Vídeo máxima calidad")
    print("2. Audio máxima calidad")
    print("3. Modo experto")
    print("4. Salir")


def main():
    while True:
        mostrar_menu()

        opcion = input(
            "\nSeleccione una opción: "
        ).strip()

        if opcion == "1":
            video_maxima_calidad()

        elif opcion == "2":
            audio_maxima_calidad()

        elif opcion == "3":
            modo_experto()

        elif opcion == "4":
            print("\nSaliendo...")
            break

        else:
            print("\nOpción inválida.")


if __name__ == "__main__":
    main()