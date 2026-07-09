import subprocess


def build_executable() -> None:
    subprocess.run(
        [
            "pyinstaller",
            "--name=PyAutoRecorder",
            "--windowed",
            "--icon=assets/PyAutoRecorder.ico",
            "utils/config.ini:.",
            "assets/PyAutoRecorder.png:.",
            "main.py",
        ],
        check=True,
    )

    print("Executable built successfully.")


if __name__ == "__main__":
    build_executable()
