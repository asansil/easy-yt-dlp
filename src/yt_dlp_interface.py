import shlex
import subprocess

from tkinter import Tk
from tkinter.filedialog import askdirectory


def select_folder():
    root = Tk()
    root.withdraw()

    folder = askdirectory(
        title="Select destination folder"
    )

    root.destroy()

    return folder


def run_ytdlp(url, arguments):
    command = ["yt-dlp"]

    command.extend(arguments)
    command.append(url)

    try:
        result = subprocess.run(command)

        if result.returncode != 0:
            print(
                f"\nThe download finished with error code "
                f"{result.returncode}"
            )

    except FileNotFoundError:
        print(
            "\nyt-dlp not found in PATH.\n"
            "Run the installer first (instalador_actualizador.py)."
        )

    except Exception as e:
        print(f"\nUnexpected error:\n{e}")


def download_best_video():
    url = input("\nURL: ").strip()

    folder = select_folder()

    if not folder:
        print("\nOperation cancelled.")
        return

    run_ytdlp(
        url,
        [
            "-P",
            folder,
            "-f",
            "bestvideo+bestaudio/best",
            "--merge-output-format",
            "mkv"
        ]
    )


def download_best_audio():
    url = input("\nURL: ").strip()

    folder = select_folder()

    if not folder:
        print("\nOperation cancelled.")
        return

    run_ytdlp(
        url,
        [
            "-P",
            folder,
            "-f",
            "bestaudio/best",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "320K"
        ]
    )


def expert_mode():
    url = input("\nURL: ").strip()

    folder = select_folder()

    if not folder:
        print("\nOperation cancelled.")
        return

    arguments = input(
        "yt-dlp arguments: "
    ).strip()

    try:
        args = shlex.split(arguments)

        args = ["-P", folder] + args

        run_ytdlp(url, args)

    except ValueError as e:
        print(f"\nError parsing arguments:\n{e}")


def show_menu():
    print("\n========================")
    print(" yt-dlp Downloader")
    print("========================")
    print("1. Best quality video")
    print("2. Best quality audio")
    print("3. Expert mode")
    print("4. Exit")


def main():
    while True:
        show_menu()

        option = input(
            "\nSelect an option: "
        ).strip()

        if option == "1":
            download_best_video()

        elif option == "2":
            download_best_audio()

        elif option == "3":
            expert_mode()

        elif option == "4":
            print("\nExiting...")
            break

        else:
            print("\nInvalid option.")


if __name__ == "__main__":
    main()