"""保存済みの.par / .bundleから操作手順書(Markdown)を一括生成するCLI。

使い方:
    python scripts/generate_manual.py foo.par bar.bundle
    python scripts/generate_manual.py --all   # config.iniの共有フォルダ内の全バンドル
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import constants  # noqa: E402
from service.manual_generator import (  # noqa: E402
    write_bundle_manual,
    write_macro_manual,
)
from service.workflow import WORKFLOW_FILENAME, list_bundles  # noqa: E402


def _is_bundle(path: Path) -> bool:
    return path.is_dir() and (path / WORKFLOW_FILENAME).exists()


def _generate(path: Path) -> Path:
    if _is_bundle(path):
        return write_bundle_manual(path)
    return write_macro_manual(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="操作手順書(Markdown)を生成する")
    parser.add_argument(
        "paths", nargs="*", type=Path, help=".parファイル または .bundleフォルダ"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="config.iniの[Workflow] bundle_dir内の全バンドルを出力",
    )
    args = parser.parse_args()

    targets: list[Path] = list(args.paths)
    if args.all:
        from utils.config_manager import ConfigManager

        bundle_dir = ConfigManager().config.get("Workflow", "bundle_dir", fallback="")
        if not bundle_dir:
            parser.error(constants.MSG_BUNDLE_DIR_NOT_SET)
        targets.extend(list_bundles(bundle_dir))
    if not targets:
        parser.error("paths または --all を指定してください。")

    failed = False
    for target in targets:
        try:
            print(_generate(target))
        except (OSError, ValueError, KeyError) as e:
            print(constants.MSG_MANUAL_ERROR.format(error=f"{target}: {e}"), file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
