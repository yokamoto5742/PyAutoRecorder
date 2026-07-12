"""クリップボード変数: Excelでコピーした「項目(タブ)値」形式のテキストを辞書化し、
プレースホルダ {VAR:キー名} / {VAR:キー名:書式} を値へ解決する。

書式は「日付」（例: 2026/7/4 → 2026/07/04）と「時刻」（例: 930 → 09:30）に対応する。
"""

import re
from datetime import datetime

from service.models import MacroFile
from service.workflow import StepType, WorkflowBundle

FORMAT_DATE = "日付"
FORMAT_TIME = "時刻"

MSG_FIELD_NOT_FOUND = "クリップボードに「{name}」が見つかりません"
MSG_INVALID_DATE = "「{name}」を日付として解釈できません: {value}"
MSG_INVALID_TIME = "「{name}」を時刻として解釈できません: {value}"
MSG_UNKNOWN_FORMAT = "不明な書式です（日付・時刻のみ対応）: {fmt}"

_VAR_PATTERN = re.compile(r"\{VAR:([^}]+)\}", re.IGNORECASE)


def parse_fields(text: str) -> dict[str, str]:
    """タブ区切りの「項目(タブ)値」行を辞書化する（重複キーは後勝ち）。"""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if "\t" not in line:
            continue
        key, value = line.split("\t", 1)
        # 3列以上コピーされた場合は2列目のみを値として使う
        value = value.split("\t", 1)[0]
        if key.strip():
            fields[key.strip()] = value.strip()
    return fields


def format_value(name: str, value: str, fmt: str) -> str:
    """書式指定（日付・時刻）に従って値を整形する。解釈できなければValueError。"""
    if fmt == FORMAT_DATE:
        try:
            return datetime.strptime(value, "%Y/%m/%d").strftime("%Y/%m/%d")
        except ValueError:
            raise ValueError(MSG_INVALID_DATE.format(name=name, value=value)) from None
    if fmt == FORMAT_TIME:
        if value.isdigit() and len(value) in (3, 4):
            hour, minute = int(value[:-2]), int(value[-2:])
            if hour < 24 and minute < 60:
                return f"{hour:02d}:{minute:02d}"
        raise ValueError(MSG_INVALID_TIME.format(name=name, value=value))
    raise ValueError(MSG_UNKNOWN_FORMAT.format(fmt=fmt))


def var_name(spec: str) -> str:
    """変数指定（"キー名" または "キー名:書式"）からキー名を取り出す。"""
    return spec.partition(":")[0].strip()


def resolve(spec: str, fields: dict[str, str]) -> str:
    """変数指定を値へ解決する。キー欠損・書式不正はValueError。"""
    name, _, fmt = spec.partition(":")
    name = name.strip()
    if name not in fields:
        raise ValueError(MSG_FIELD_NOT_FOUND.format(name=name))
    value = fields[name]
    if fmt.strip():
        return format_value(name, value, fmt.strip())
    return value


def resolve_all(specs: list[str], fields: dict[str, str]) -> dict[str, str]:
    """各変数指定を解決して {指定: 値} を返す（実行前の一括検証用）。"""
    return {spec: resolve(spec, fields) for spec in specs}


def substitute_raw(text: str, fields: dict[str, str]) -> str:
    """平文テキスト（SET_TEXT用）内の {VAR:...} を値へ置換する。"""
    return _VAR_PATTERN.sub(lambda m: resolve(m.group(1), fields), text)


def collect_var_specs(macro: MacroFile) -> list[str]:
    """マクロ全体で使用している変数指定を出現順に重複なく列挙する。"""
    specs: list[str] = []
    for items in (macro.initial, macro.loop, macro.final):
        for item in items:
            for match in _VAR_PATTERN.finditer(item.keys):
                if match.group(1) not in specs:
                    specs.append(match.group(1))
    return specs


def collect_bundle_var_specs(bundle: WorkflowBundle) -> list[str]:
    """バンドル内の全レコーディングで使用している変数指定を列挙する。"""
    specs: list[str] = []
    for step in bundle.workflow.steps:
        if step.step_type != StepType.PLAY_RECORDING:
            continue
        macro = MacroFile.load(bundle.recording_path(step.recording))
        for spec in collect_var_specs(macro):
            if spec not in specs:
                specs.append(spec)
    return specs
