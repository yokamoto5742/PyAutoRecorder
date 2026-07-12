import pytest

from service.key_notation import KeyToken, escape_text, parse


class TestParse:
    def test_plain_text(self):
        assert parse("abc") == [KeyToken(kind="text", value="abc")]

    def test_japanese_text(self):
        assert parse("こんにちは") == [KeyToken(kind="text", value="こんにちは")]

    def test_special_key(self):
        assert parse("{ENTER}") == [KeyToken(kind="key", value="enter")]

    def test_special_key_sequence(self):
        tokens = parse("{ALT}{DOWN}{DOWN}{ENTER}")
        assert tokens == [
            KeyToken(kind="key", value="alt"),
            KeyToken(kind="key", value="down"),
            KeyToken(kind="key", value="down"),
            KeyToken(kind="key", value="enter"),
        ]

    def test_modifier_with_char(self):
        # 資料の例: Altを押しながらY → %y
        assert parse("%y") == [KeyToken(kind="key", value="y", modifiers=("alt",))]

    def test_modifier_with_special_key(self):
        assert parse("^{HOME}") == [
            KeyToken(kind="key", value="home", modifiers=("ctrl",))
        ]

    def test_multiple_modifiers(self):
        assert parse("+^a") == [
            KeyToken(kind="key", value="a", modifiers=("shift", "ctrl"))
        ]

    def test_text_and_key_mixed(self):
        tokens = parse("abc{ENTER}def")
        assert tokens == [
            KeyToken(kind="text", value="abc"),
            KeyToken(kind="key", value="enter"),
            KeyToken(kind="text", value="def"),
        ]

    def test_commands(self):
        tokens = parse("{WAIT}{CLIP}{CLEAR}{IME}{IMEON}{IMEOFF}")
        assert [t.kind for t in tokens] == [
            "wait",
            "clip",
            "clear",
            "ime_toggle",
            "ime_on",
            "ime_off",
        ]

    def test_escaped_chars_join_text(self):
        assert parse("a{+}b") == [KeyToken(kind="text", value="a+b")]

    def test_escaped_space(self):
        assert parse("{ }") == [KeyToken(kind="text", value=" ")]

    def test_escaped_close_brace(self):
        assert parse("{}}") == [KeyToken(kind="text", value="}")]

    def test_case_insensitive_special(self):
        assert parse("{enter}") == [KeyToken(kind="key", value="enter")]

    def test_function_keys(self):
        assert parse("{F12}") == [KeyToken(kind="key", value="f12")]

    def test_unknown_token_raises(self):
        with pytest.raises(ValueError):
            parse("{UNKNOWN}")

    def test_unclosed_brace_raises(self):
        with pytest.raises(ValueError):
            parse("{ENTER")

    def test_trailing_modifier_raises(self):
        with pytest.raises(ValueError):
            parse("abc^")

    def test_empty_string(self):
        assert parse("") == []


class TestVarToken:
    def test_var_plain(self):
        assert parse("{VAR:術者}") == [KeyToken(kind="var", value="術者")]

    def test_var_with_format(self):
        assert parse("{VAR:手術日:日付}") == [KeyToken(kind="var", value="手術日:日付")]

    def test_var_mixed_with_keys(self):
        tokens = parse("{VAR:病室}{TAB}")
        assert tokens == [
            KeyToken(kind="var", value="病室"),
            KeyToken(kind="key", value="tab"),
        ]

    def test_var_empty_name_raises(self):
        with pytest.raises(ValueError):
            parse("{VAR:}")

    def test_var_with_modifier_raises(self):
        with pytest.raises(ValueError):
            parse("^{VAR:術者}")


class TestEscape:
    def test_escape_plain(self):
        assert escape_text("abc") == "abc"

    def test_escape_specials(self):
        assert escape_text("a+b") == "a{+}b"
        assert escape_text("(x)") == "{(}x{)}"
        assert escape_text("a b") == "a{ }b"
        assert escape_text("}") == "{}}"

    def test_roundtrip(self):
        original = "a+b (c) {d} 100%"
        tokens = parse(escape_text(original))
        assert tokens == [KeyToken(kind="text", value=original)]
