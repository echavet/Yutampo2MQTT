"""Tests de la stratégie Commit-on-entry et de la protection window chasing."""

from tests.helpers import make_handler


def _tick(handler, current_hour, live_hottest):
    """Simule un cycle : heure courante + forecast, puis lecture de l'heure verrouillée."""
    handler._get_current_hour = lambda: current_hour
    handler.weather_client.get_hottest_hour.return_value = live_hottest
    return handler._get_locked_hottest_hour()


class TestGetLockedHottestHour:
    def test_follows_live_forecast_when_window_is_still_ahead(self):
        handler = make_handler(heating_duration=1.0, hottest_hour=14.0)
        assert _tick(handler, 12.0, 14.0) == 14.0
        assert handler._in_heating_window is False
        assert _tick(handler, 12.0, 15.0) == 15.0

    def test_locks_on_entry_and_ignores_later_forecast(self):
        handler = make_handler(heating_duration=1.0, hottest_hour=14.0)
        _tick(handler, 12.0, 14.0)
        assert _tick(handler, 14.0, 14.0) == 14.0
        assert handler._in_heating_window is True
        # Forecast qui bougerait la fenêtre dans le passé : ignoré tant qu'on est dedans
        assert _tick(handler, 14.2, 10.0) == 14.0
        assert handler._in_heating_window is True

    def test_sept18_chasing_past_forecast_keeps_reachable_window(self):
        """Scénario 18 sept (heating_duration=1h) :

        Le forecast reste en retard sur l'heure courante (fenêtre toujours
        entièrement passée). On conserve 14h, encore atteignable, jusqu'à
        y entrer — au lieu d'accepter 10h, 11h, 12h… et de rester à Min.
        """
        handler = make_handler(heating_duration=1.0, hottest_hour=14.0)
        assert _tick(handler, 11.0, 14.0) == 14.0

        # 12:25, forecast 10h → [9:30-10:30] passé, [13:30-14:30] encore OK
        current = 12 + 25 / 60.0
        assert _tick(handler, current, 10.0) == 14.0
        assert handler._in_heating_window is False

        # 13:25, forecast 11h → [10:30-11:30] passé, 14h toujours devant
        assert _tick(handler, 13 + 25 / 60.0, 11.0) == 14.0
        assert handler._in_heating_window is False

        # 13:36, forecast 12h → [11:30-12:30] passé ; 14h est en cours
        assert _tick(handler, 13.6, 12.0) == 14.0
        assert handler._in_heating_window is True

    def test_follows_live_forecast_when_its_window_is_happening_now(self):
        """Un forecast dont la fenêtre contient l'heure actuelle n'est pas
        'passé' : on le suit et on entre (commit-on-entry)."""
        handler = make_handler(heating_duration=1.0, hottest_hour=14.0)
        _tick(handler, 11.0, 14.0)
        current = 12 + 25 / 60.0  # 12:25, fenêtre 12h = [11:30-12:30]
        assert _tick(handler, current, 12.0) == 12.0
        assert handler._in_heating_window is True

    def test_accepts_new_forecast_when_both_windows_are_past(self):
        handler = make_handler(heating_duration=1.0, hottest_hour=10.0)
        _tick(handler, 12.0, 10.0)
        assert handler.locked_hottest_hour == 10.0
        # 10h et 11h sont toutes deux passées à 13h (duration=1h)
        assert _tick(handler, 13.0, 11.0) == 11.0
        assert handler._in_heating_window is False

    def test_accepts_past_forecast_when_no_previous_lock(self):
        handler = make_handler(heating_duration=1.0, hottest_hour=10.0)
        assert handler.locked_hottest_hour is None
        assert _tick(handler, 12.25, 10.0) == 10.0
        assert handler._in_heating_window is False

    def test_enters_window_when_live_forecast_is_reachable_now(self):
        handler = make_handler(heating_duration=6.0, hottest_hour=15.0)
        assert _tick(handler, 14.0, 15.0) == 15.0
        assert handler._in_heating_window is True

    def test_unlocks_after_leaving_window_then_follows_live(self):
        handler = make_handler(heating_duration=1.0, hottest_hour=14.0)
        _tick(handler, 14.0, 14.0)
        assert handler._in_heating_window is True

        handler._get_current_hour = lambda: 14.6
        handler.weather_client.get_hottest_hour.return_value = 14.0
        assert handler._is_in_weather_window() is False
        assert handler._in_heating_window is False

        # À 16h, forecast 16h : fenêtre [15.5–16.5] encore valide → on la suit
        assert _tick(handler, 16.0, 16.0) == 16.0
        assert handler._in_heating_window is True

    def test_keeps_previous_even_if_not_yet_inside_it(self):
        """Forecast passé, fenêtre précédente encore dans le futur → on attend."""
        handler = make_handler(heating_duration=1.0, hottest_hour=16.0)
        _tick(handler, 12.0, 16.0)
        assert _tick(handler, 12.0, 9.0) == 16.0
        assert handler._in_heating_window is False
        assert _tick(handler, 16.0, 9.0) == 16.0
        assert handler._in_heating_window is True

    def test_shorter_duration_still_keeps_reachable_previous_window(self):
        handler = make_handler(heating_duration=6.0, hottest_hour=14.0)
        _tick(handler, 12.0, 14.0)  # fenêtre [11–17], utilisable
        handler.set_heating_duration(1.0)
        # Ancienne 14h → [13.5–14.5] encore OK ; live 10h → [9.5–10.5] passé
        assert _tick(handler, 12.0, 10.0) == 14.0

        handler.set_heating_duration(0.5)
        # 14h → [13.75–14.25] encore futur ; on conserve
        assert _tick(handler, 12.0, 10.0) == 14.0

    def test_fallback_to_mqtt_default_without_weather_client(self):
        handler = make_handler(heating_duration=1.0)
        handler.weather_client = None
        handler.mqtt_handler.default_hottest_hour = 15.0
        handler._get_current_hour = lambda: 12.0
        assert handler._get_locked_hottest_hour() == 15.0
