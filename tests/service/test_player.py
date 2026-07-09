from service.models import MacroFile, MacroSettings
from service.player import MacroPlayer


def build_player(speed_percent: int) -> MacroPlayer:
    macro = MacroFile(settings=MacroSettings(speed_percent=speed_percent))
    return MacroPlayer(macro)


class TestScaledInterval:
    def test_100_percent_keeps_interval(self):
        assert build_player(100)._scaled_interval(2.0) == 2.0

    def test_200_percent_halves_interval(self):
        assert build_player(200)._scaled_interval(2.0) == 1.0

    def test_300_percent(self):
        assert build_player(300)._scaled_interval(3.0) == 1.0

    def test_out_of_range_is_clamped(self):
        assert build_player(50)._scaled_interval(2.0) == 2.0
        assert build_player(500)._scaled_interval(3.0) == 1.0
