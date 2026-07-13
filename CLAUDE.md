# CLAUDE.md

このファイルは、このリポジトリでコードを扱う際のClaude Code (claude.ai/code) 向けガイダンスです。

## プロジェクト概要

PyAutoRecorderは、Windows向けGUIマクロレコーダー/プレイヤー（PySide6製）です。マウス・キーボード入力をグローバルに記録・再生し、タイマーによるスケジュール実行、条件付き実行、ホットキー制御に対応しています。UIおよびコード内コメントは日本語です。

## セットアップと実行

- パッケージマネージャーは `uv`（`pyproject.toml` / `uv.lock` を参照）。依存関係のインストールは `uv sync`。
- アプリの実行: `python main.py`（`QApplication` を生成し `app.main_window.MainWindow` を表示）。
- 単体実行可能ファイルのビルド: `python build.py`（PyInstallerを使用し、`utils/config.ini` と `assets/app.png` を同梱）。

## アーキテクチャ

- `app/` — PySide6によるUI層。メインウィンドウ、項目編集ダイアログ、レコーダー子ウィンドウ、停止ボタンのオーバーレイ、タイマーダイアログ、トレイランチャー（`.par` ファイル用）、ユーザー向け日本語文字列をまとめた `constants.py`。
- `service/` — ビジネスロジック。`recorder.py`（グローバル入力フック）、`player.py`（再生エンジン）、`hotkey_manager.py`（pynputによるグローバルホットキー）、`conditions.py`（実行前条件チェック）、`timer_scheduler.py`（QTimerによるスケジューリング）、`ime_control.py`（imm32によるIME切り替え）、`key_notation.py`（キー入力表記のパーサー）、`models.py`（データクラス＋JSON永続化）。
- `utils/` — `config_manager.py` / `config.ini`（ホットキー、トレイランチャー、ログ設定）、`env_loader.py`（python-dotenvによる `.env` の読み込み）、`log_rotation.py`。
- `tests/` は現在 `service/` のみをカバー（`test_conditions.py`、`test_key_notation.py`、`test_models.py`）。

コーディング規約（`python-coding.md`）、テスト実行コマンド（`testing.md`）、コミットメッセージ形式（`commit.md`）、コーディングミスを防ぐための行動指針（`coding-guidelines.md`）、レスポンススタイル（`response-style.md`）については `.claude/rules/` を参照してください。
