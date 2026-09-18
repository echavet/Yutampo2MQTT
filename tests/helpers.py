"""Helpers de construction d'objets isolés pour les tests."""

from unittest.mock import MagicMock

from automation_handler import AutomationHandler


def make_handler(
    heating_duration=1.0,
    hottest_hour=14.0,
    setpoint=50.0,
    amplitude=20.0,
    weather_client=None,
    mqtt_handler=None,
    off_peak_client=None,
    regulation_mode="step",
    regulation_priority="off_peak",
    eco_ratio=0.5,
):
    """Construit un AutomationHandler isolé, sans scheduler ni I/O."""
    if weather_client is None:
        weather_client = MagicMock()
        weather_client.weather_entity = "weather.forecast_home"
        weather_client.get_hottest_hour.return_value = hottest_hour

    if mqtt_handler is None:
        mqtt_handler = MagicMock()
        mqtt_handler.default_hottest_hour = 15.0

    return AutomationHandler(
        api_client=MagicMock(),
        mqtt_handler=mqtt_handler,
        physical_device=MagicMock(),
        weather_client=weather_client,
        setpoint=setpoint,
        amplitude=amplitude,
        heating_duration=heating_duration,
        regulation_mode=regulation_mode,
        off_peak_client=off_peak_client,
        regulation_priority=regulation_priority,
        eco_ratio=eco_ratio,
    )
