"""UIに表示する日本語メッセージ・ラベルの一元管理。"""

APP_NAME = "PyAutoRecorder"

# メインウィンドウ
WINDOW_TITLE = APP_NAME
UNTITLED_FILE = "無題"
MODIFIED_MARK = "*"

TAB_INITIAL = "1.最初の処理"
TAB_LOOP = "2.繰り返し処理"
TAB_FINAL = "3.最後の処理"
LABEL_REPEAT_COUNT = "繰り返し回数"

COLUMN_INTERVAL = "間隔(秒)"
COLUMN_X = "横位置"
COLUMN_Y = "縦位置"
COLUMN_ACTION = "クリック方法"
COLUMN_KEYS = "キーボード操作"
COLUMN_CONDITION = "条件判断"

# ツールバー
TOOLBAR_NEW = "新規"
TOOLBAR_OPEN = "開く"
TOOLBAR_SAVE = "保存"
TOOLBAR_RECORD = "記録"
TOOLBAR_PLAY = "再生"
TOOLBAR_STOP = "停止"
TOOLBAR_PAUSE = "一時停止"

# 記録メニュー
MENU_RECORD_AUTO = "自動記録"
MENU_RECORD_MANUAL_MOUSE = "手動 - マウス操作の記録（子機）"
MENU_RECORD_MANUAL_KEY = "手動 - キーボード操作の記録"

# 項目操作
MENU_EDIT_ITEM = "編集"
MENU_DELETE_ITEM = "削除"
MENU_MOVE_UP = "上へ移動"
MENU_MOVE_DOWN = "下へ移動"

# アクション種別の表示名
ACTION_LABELS = {
    "none": "移動のみ",
    "left": "左クリック",
    "right": "右クリック",
    "double": "Wクリック",
    "middle": "中クリック",
    "drag": "ドラッグ",
    "key_only": "キーOnly",
    "launch_app": "アプリ起動",
    "set_text": "テキスト書込(UIA)",
    "get_text": "テキスト読取(UIA)",
}

# ファイルダイアログ
FILE_DIALOG_FILTER = "PyAutoRecorderファイル (*.par);;すべてのファイル (*)"
FILE_DIALOG_OPEN_TITLE = "ファイルを開く"
FILE_DIALOG_SAVE_TITLE = "名前を付けて保存"

# 確認・通知メッセージ
MSG_CONFIRM_DISCARD = "変更が保存されていません。破棄しますか？"
MSG_PLAYBACK_FINISHED = "再生が完了しました。"
MSG_PLAYBACK_STOPPED = "再生を停止しました。"
MSG_PLAYBACK_ERROR = "再生中にエラーが発生しました: {error}"
MSG_RECORDING = "記録中... 画面右下のボタンで終了します。"
MSG_FILE_LOAD_ERROR = "ファイルを読み込めませんでした: {error}"
MSG_FILE_SAVE_ERROR = "ファイルを保存できませんでした: {error}"

# 記録停止ボタン
STOP_BUTTON_TOOLTIP = "記録を終了"

# 項目編集ダイアログ
DIALOG_EDIT_TITLE = "項目の編集"
LABEL_INTERVAL = "間隔(秒):"
LABEL_POSITION_X = "横位置:"
LABEL_POSITION_Y = "縦位置:"
LABEL_ACTION = "クリック方法:"
LABEL_KEYS = "キーボード操作:"
LABEL_DRAG_TO = "ドラッグ先(X,Y):"
LABEL_REPEAT_OFFSET = "繰り返すたびに移動する量(X,Y):"
LABEL_KEY_REPEAT_INCREASE = "繰り返すたびにキーボード操作の実行回数を増加"
LABEL_APP_PATH = "起動するアプリ:"
BUTTON_BROWSE_APP = "参照..."
FILE_DIALOG_APP_TITLE = "起動するアプリを選択"
FILE_DIALOG_APP_FILTER = "実行ファイル (*.exe);;すべてのファイル (*)"
MSG_INVALID_KEYS = "キーボード操作の記述が不正です: {error}"
MSG_APP_PATH_REQUIRED = "起動するアプリのパスを指定してください。"

# 条件判断
GROUP_CONDITION = "条件判断使用"
LABEL_CONDITION_TYPE = "条件:"
LABEL_CONDITION_VALUE = "値:"
LABEL_CONDITION_MAX_WAIT = "最大待機(秒):"
CONDITION_LABELS = {
    "window_shown_wait": "次のウィンドウが表示されるまで待機",
    "window_closed_wait": "次のウィンドウが終了されるまで待機",
    "window_shown_skip": "次のウィンドウが表示されていればスキップ",
    "window_not_shown_skip": "次のウィンドウが表示されていなければスキップ",
    "clip_contains_run": "次の文字列がクリップボードにあれば実行",
    "clip_not_contains_run": "次の文字列がクリップボードになければ実行",
    "color_match_wait": "色が指定座標の色と一致するまで待機",
    "color_not_match_wait": "色が指定座標の色と異なるまで待機",
    "color_match_run": "色が指定座標の色と一致すれば実行",
    "color_not_match_run": "色が指定座標の色と異なれば実行",
    "file_exists_run": "次の指定ファイルが存在していれば実行",
    "file_not_exists_run": "次の指定ファイルが存在していなければ実行",
    "file_created_wait": "次の指定ファイルが生成されるまで待機",
    "file_larger_run": "次のファイルが指定サイズより大きければ実行",
    "file_smaller_run": "次のファイルが指定サイズより小さければ実行",
    "datetime_wait": "次の日時になるまで待機",
    "datetime_match_run": "次の日時であれば実行",
    "repeat_index_run": "繰り返し数が次の回目であれば実行",
    "button_shown_wait": "次のボタンが表示されるまで待機",
    "button_hidden_wait": "次のボタンが消えるまで待機",
    "button_shown_skip": "次のボタンが表示されていればスキップ",
    "button_not_shown_skip": "次のボタンが表示されていなければスキップ",
    "button_enabled_wait": "次のボタンが有効になるまで待機",
    "image_shown_wait": "次の画像が表示されるまで待機",
}
_BUTTON_SPEC_HINT = "ボタン名 or id:AutomationId[,親タイトル or id:… or class:…]"
CONDITION_VALUE_HINTS = {
    "window_shown_wait": 'タイトル名（"..."で完全一致）',
    "window_closed_wait": 'タイトル名（"..."で完全一致）',
    "window_shown_skip": 'タイトル名（"..."で完全一致）',
    "window_not_shown_skip": 'タイトル名（"..."で完全一致）',
    "clip_contains_run": "正規表現（例: 123|abc）",
    "clip_not_contains_run": "正規表現（例: 123|abc）",
    "color_match_wait": "色,x,y（例: 008080,10,18 座標省略可）",
    "color_not_match_wait": "色,x,y（例: 008080,10,18 座標省略可）",
    "color_match_run": "色,x,y（例: 008080,10,18 座標省略可）",
    "color_not_match_run": "色,x,y（例: 008080,10,18 座標省略可）",
    "file_exists_run": "フルパス",
    "file_not_exists_run": "フルパス",
    "file_created_wait": "フルパス",
    "file_larger_run": "フルパス,バイト数（例: C:\\readme.txt,500）",
    "file_smaller_run": "フルパス,バイト数（例: C:\\readme.txt,500）",
    "datetime_wait": "YYYY-MM-DD HH:MM または HH:MM",
    "datetime_match_run": "HH:MM",
    "repeat_index_run": "例: 2|5|17、奇数、偶数、7n",
    "button_shown_wait": _BUTTON_SPEC_HINT,
    "button_hidden_wait": _BUTTON_SPEC_HINT,
    "button_shown_skip": _BUTTON_SPEC_HINT,
    "button_not_shown_skip": _BUTTON_SPEC_HINT,
    "button_enabled_wait": _BUTTON_SPEC_HINT,
    "image_shown_wait": "「画像を取得」で認識する画像を設定",
}

# 対象コントロール（UIA要素指定）
GROUP_SELECTOR = "対象コントロール（UIA・クリック時は座標より優先）"
LABEL_SELECTOR_AUTOMATION_ID = "AutomationId:"
LABEL_SELECTOR_NAME = "Name:"
LABEL_SELECTOR_CONTROL_TYPE = "コントロール種別:"
LABEL_SELECTOR_WINDOW_ID = "ウィンドウAutomationId:"
LABEL_SELECTOR_WINDOW_NAME = "ウィンドウ名(部分一致):"
LABEL_SELECTOR_INDEX = "一致順(1始まり):"
BUTTON_PICK_ELEMENT = "画面から取得"
BUTTON_PICK_COUNTDOWN = "対象にカーソルを合わせてください({sec})"
MSG_PICK_FAILED = (
    "コントロール情報を取得できませんでした。"
    "AutomationIdもNameも持たないコントロールの可能性があります。"
)
MSG_SELECTOR_REQUIRED = "対象コントロールのAutomationIdまたはNameを指定してください。"
HINT_SET_TEXT_KEYS = "書き込むテキスト（そのまま書き込まれます）"

# 画像認識
BUTTON_CAPTURE_IMAGE = "画像を取得"
LABEL_CONDITION_IMAGE = "認識する画像:"
MSG_IMAGE_REQUIRED = "認識する画像を取得してください。"
DIALOG_CAPTURE_TITLE = "認識する画像の選択"
MSG_CAPTURE_INSTRUCTION = "認識する範囲をドラッグで選択してください（Escで中止）"
BUTTON_LOAD_IMAGE = "画像ファイルを選択"
DIALOG_LOAD_IMAGE_TITLE = "画像ファイルの選択"
FILTER_IMAGE_FILES = "画像ファイル (*.png *.jpg *.jpeg *.bmp);;すべてのファイル (*.*)"
MSG_IMAGE_LOAD_FAILED = "画像ファイルを読み込めませんでした。"

# 子機
CHILD_WINDOW_TITLE = "子機"
CHILD_MENU_LEFT = "左クリック"
CHILD_MENU_RIGHT = "右クリック"
CHILD_MENU_DOUBLE = "Wクリック"
CHILD_MENU_MIDDLE = "中クリック"
CHILD_MENU_MOVE_ONLY = "移動のみ"
CHILD_MENU_CLOSE = "子機を閉じる"

# トレイ
TRAY_MENU_SHOW = "メインウィンドウを表示"
TRAY_MENU_EXIT = "終了"

# タイマー
MSG_TIMER_PLAY_STARTED = "再生タイマーにより再生を開始しました。"
MSG_TIMER_STOPPED = "停止タイマーにより停止しました。"

TOOLBAR_TIMER = "タイマー"
DIALOG_TIMER_TITLE = "タイマーの設定"
LABEL_USE_PLAY_TIMER = "再生タイマーを使用"
LABEL_USE_STOP_TIMER = "停止タイマーを使用"
LABEL_STOP_TIMER_MODE = "停止タイマーの動作:"
STOP_MODE_LABELS = {
    "all": "すべて停止",
    "final": "最後の処理をする",
}

# オプション設定（parファイル別）
TOOLBAR_OPTIONS = "オプション"
DIALOG_OPTIONS_TITLE = "オプション設定"
LABEL_USE_PAUSE_HOTKEY = "一時停止の制御キーを使用"
LABEL_SPEED_PERCENT = "全体の速度率(%):"

# トレイランチャー
TRAY_MENU_ADD_CURRENT = "現在のファイルをランチャーに追加"
MSG_TRAY_NO_FILE = "先にファイルを保存してください。"
MSG_TRAY_ADDED = "トレイランチャーに追加しました: {name}"

# ワークフロー（共通）
TOOLBAR_WORKFLOW = "ワークフロー"
WORKFLOW_STEP_TYPE_LABELS = {
    "play_recording": "操作再生",
    "wait_image": "画面待ち",
    "human_confirm": "人間確認",
}
WORKFLOW_STEP_ICONS = {
    "play_recording": "■",
    "wait_image": "⌛",
    "human_confirm": "⚠️",
}
MSG_BUNDLE_LOAD_ERROR = "ワークフローを読み込めませんでした: {error}"

# ワークフロー実行画面
WORKFLOW_RUNNER_TITLE = "ワークフロー実行"
LABEL_WORKFLOW_LIST = "ワークフロー一覧"
BUTTON_WORKFLOW_REFRESH = "一覧を更新"
LABEL_CURRENT_FLOW = "現在の実行フロー：{name}"
BUTTON_WORKFLOW_PLAY = "◯ 再生"
BUTTON_WORKFLOW_PAUSE = "‖ 一時停止"
BUTTON_WORKFLOW_STOP = "■ 停止"
BUTTON_WORKFLOW_RESUME = "再開"
WORKFLOW_STATUS_DONE = "[完了]"
WORKFLOW_STATUS_RUNNING = "[実行]"
WORKFLOW_STATUS_WAITING = "[待機]"
MSG_WORKFLOW_FINISHED = "ワークフローが完了しました。"
MSG_WORKFLOW_STOPPED = "ワークフローを停止しました。"
MSG_WORKFLOW_PAUSED = "一時停止中"
MSG_CONFIRM_DEFAULT = "内容を目視確認し、「再開」を押してください。"
MSG_WAIT_TIMEOUT_CONFIRM = (
    "画面を確認できませんでした。目視確認して「再開」を押してください。"
)
MSG_BUNDLE_DIR_NOT_SET = (
    "共有フォルダが設定されていません。"
    "config.iniの[Workflow] bundle_dirを設定してください。"
)

# ワークフロー編集画面
WORKFLOW_EDITOR_TITLE = "ワークフロー編集"
LABEL_WORKFLOW_NAME = "ワークフロー名:"
COLUMN_STEP_TYPE = "種類"
COLUMN_STEP_LABEL = "ラベル"
COLUMN_STEP_DETAIL = "内容"
BUTTON_ADD_STEP = "ステップ追加"
MENU_ADD_STEP_PLAY = "操作再生（レコーディング呼び出し）"
MENU_ADD_STEP_WAIT_IMAGE = "画面待ち（画像認識）"
MENU_ADD_STEP_CONFIRM = "人間確認（一時停止）"
DIALOG_NEW_BUNDLE_TITLE = "新規ワークフロー"
LABEL_NEW_BUNDLE_NAME = "ワークフロー名を入力してください:"
DIALOG_BUNDLE_DIR_TITLE = "保存先フォルダの選択"
DIALOG_OPEN_BUNDLE_TITLE = "ワークフロー（.bundle）フォルダの選択"
MSG_INVALID_BUNDLE = "選択したフォルダはワークフローではありません。"
MSG_BUNDLE_EXISTS = "同名のワークフローが既に存在します: {name}"
MSG_BUNDLE_SAVE_ERROR = "ワークフローを保存できませんでした: {error}"

# ステップ編集ダイアログ
DIALOG_STEP_TITLE = "ステップの編集"
LABEL_STEP_LABEL = "ラベル:"
LABEL_STEP_RECORDING = "レコーディング:"
BUTTON_BROWSE_RECORDING = "参照..."
DIALOG_RECORDING_TITLE = "レコーディングファイルの選択"
LABEL_STEP_IMAGE = "認識する画像:"
LABEL_STEP_MAX_WAIT = "最大待機(秒、0は無限):"
LABEL_STEP_MESSAGE = "確認メッセージ:"
MSG_RECORDING_REQUIRED = "レコーディングファイルを選択してください。"
MSG_STEP_IMAGE_REQUIRED = "認識する画像を設定してください。"
