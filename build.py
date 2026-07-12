import subprocess


def build_executable() -> None:
    subprocess.run(
        [
            "pyinstaller",
            "--name=PyAutoRecorder",
            "--windowed",
            "--icon=assets/PyAutoRecorder.ico",
            "--add-data=utils/config.ini;.",
            "--add-data=assets/PyAutoRecorder.png;.",
            "main.py",
        ],
        check=True,
    )

    print("Executable built successfully.")


if __name__ == "__main__":
    build_executable()