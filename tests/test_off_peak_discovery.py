"""Tests discovery MQTT OffPeak, ordre d'init, et is_off_peak() runtime."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import make_handler


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestInitOrder:
    def test_register_sensors_is_called_after_automation_handler(self):
        source = (REPO_ROOT / "yutampo_addon.py").read_text(encoding="utf-8")
        start_src = source.split("def start(self):", 1)[1]
        create_at = start_src.find("self.automation_handler = AutomationHandler")
        register_sensors_at = start_src.find("self.mqtt_handler.register_sensors()")
        register_numbers_at = start_src.find("self.mqtt_handler.register_numbers()")
        off_peak_start_at = start_src.find("self.off_peak_client.start()")

        assert create_at != -1
        assert register_sensors_at != -1
        assert register_numbers_at != -1
        assert off_peak_start_at != -1
        assert create_at < register_sensors_at
        assert create_at < register_numbers_at
        assert off_peak_start_at < register_sensors_at


class TestRegisterSensorsOffPeakDiscovery:
    def _mqtt(self):
        from mqtt_handler import MqttHandler

        handler = MqttHandler(
            {
                "mqtt_host": "localhost",
                "mqtt_port": 1883,
                "mqtt_user": "user",
                "mqtt_password": "pass",
                "discovery_prefix": "homeassistant",
                "default_hottest_hour": 15.0,
            }
        )
        handler.client = MagicMock()
        return handler

    def _published_topics(self, mqtt):
        return [call.args[0] for call in mqtt.client.publish.call_args_list]

    @patch("mqtt_handler.time.sleep")
    def test_skips_off_peak_discovery_without_automation_handler(self, _sleep):
        mqtt = self._mqtt()
        mqtt.automation_handler = None
        mqtt.register_sensors()
        topics = self._published_topics(mqtt)
        assert not any("yutampo_off_peak_state" in t for t in topics)
        assert any("yutampo_hottest_hour" in t for t in topics)

    @patch("mqtt_handler.time.sleep")
    def test_skips_off_peak_discovery_without_off_peak_client(self, _sleep):
        mqtt = self._mqtt()
        mqtt.automation_handler = make_handler(off_peak_client=None)
        mqtt.register_sensors()
        topics = self._published_topics(mqtt)
        assert not any("yutampo_off_peak_state" in t for t in topics)
        assert not any("yutampo_target_level" in t for t in topics)

    @patch("mqtt_handler.time.sleep")
    def test_publishes_off_peak_discovery_when_client_present(self, _sleep):
        mqtt = self._mqtt()
        off_peak = MagicMock()
        off_peak.is_off_peak.return_value = True
        mqtt.automation_handler = make_handler(off_peak_client=off_peak)
        mqtt.automation_handler.weather_client.get_hottest_hour.return_value = 14.0
        mqtt.automation_handler.weather_client.get_hottest_temperature.return_value = 22.0
        mqtt.register_sensors()
        topics = self._published_topics(mqtt)
        assert (
            "homeassistant/binary_sensor/yutampo_off_peak_state/config" in topics
        )
        assert "homeassistant/sensor/yutampo_target_level/config" in topics
        off_peak.is_off_peak.assert_called()


class TestOffPeakRuntimeIndependentOfDiscovery:
    """is_off_peak() est un état WebSocket interne, pas un état MQTT.

    Le fix d'ordre d'init publie la *discovery* HA. La régulation lit
    OffPeakClient.is_off_peak(), alimenté par le WebSocket, même si la
    discovery n'a jamais été publiée.
    """

    def test_is_off_peak_updates_from_ha_state_without_mqtt(self):
        from off_peak_client import OffPeakClient

        client = OffPeakClient(
            {"off_peak_entity": "binary_sensor.heures_creuses", "ha_token": "token"}
        )
        client.mqtt_handler = None
        assert client.is_off_peak() is False

        client._update_state("on")
        assert client.is_off_peak() is True
        assert client._state_received is True

        client._update_state("off")
        assert client.is_off_peak() is False

    def test_unknown_or_unavailable_is_treated_as_peak(self):
        from off_peak_client import OffPeakClient

        client = OffPeakClient(
            {"off_peak_entity": "binary_sensor.heures_creuses", "ha_token": "token"}
        )
        client._update_state("on")
        client._update_state("unavailable")
        assert client.is_off_peak() is False
        client._update_state("unknown")
        assert client.is_off_peak() is False

    def test_regulation_uses_off_peak_client_not_mqtt_entity(self):
        off_peak = MagicMock()
        off_peak.is_off_peak.return_value = True
        handler = make_handler(
            heating_duration=1.0,
            hottest_hour=10.0,
            off_peak_client=off_peak,
            amplitude=20.0,
            setpoint=50.0,
        )
        handler._get_current_hour = lambda: 12.5
        # Fenêtre météo passée (min) mais HC → max si priorite off_peak
        temp, level = handler._resolve_target_level(
            in_weather_window=False, is_off_peak=True
        )
        assert level == "max"
        assert temp == pytest.approx(50.0)

        temp, level = handler._resolve_target_level(
            in_weather_window=False, is_off_peak=False
        )
        assert level == "min"
        assert temp == pytest.approx(30.0)

        # Client absent → is_off_peak None : fallback météo uniquement
        temp, level = handler._resolve_target_level(
            in_weather_window=False, is_off_peak=None
        )
        assert level == "min"
