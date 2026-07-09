# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

PyAutoRecorder is a Windows GUI macro recorder/player (PySide6). It records mouse/keyboard input globally and plays it back, with support for timed scheduling, conditional execution, and hotkey control. The UI and in-code comments are in Japanese.

## Setup and running

- Package manager is `uv` (see `pyproject.toml` / `uv.lock`). Install deps with `uv sync`.
- Run the app: `python main.py` (creates the `QApplication` and shows `app.main_window.MainWindow`).
- Build a standalone executable: `python build.py` (PyInstaller, bundles `utils/config.ini` and `assets/app.png`).

## Architecture

- `app/` — PySide6 UI layer: main window, item editor dialog, recorder child window, stop-button overlay, timer dialog, tray launcher (for `.par` files), and `constants.py` for all user-facing Japanese strings.
- `service/` — business logic: `recorder.py` (global input hook), `player.py` (playback engine), `hotkey_manager.py` (global hotkeys via pynput), `conditions.py` (pre-execution condition checks), `timer_scheduler.py` (QTimer-based scheduling), `ime_control.py` (IME toggling via imm32), `key_notation.py` (keystroke notation parser), `models.py` (dataclasses + JSON persistence).
- `utils/` — `config_manager.py` / `config.ini` (hotkeys, tray launcher, logging settings), `env_loader.py` (loads `.env` via python-dotenv if present), `log_rotation.py`.
- `tests/` currently only covers `service/` (`test_conditions.py`, `test_key_notation.py`, `test_models.py`).

See `.claude/rules/` for coding conventions (`python-coding.md`), testing commands (`testing.md`), commit message format (`commit.md`), general coding-mistake guardrails (`coding-guidelines.md`), and response style (`response-style.md`).
