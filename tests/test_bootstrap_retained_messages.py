"""Tests for bootstrap protection against retained MQTT command messages.

On addon restart, the MQTT broker may redeliver retained messages on command topics
(e.g., .../set) as if the user had just sent those commands. This would overwrite
config values with stale retained data.

The fix:
1. _bootstrap_complete flag prevents number commands from being processed at startup
2. complete_bootstrap() is called after initial state publication
3. Retained messages on command topics are cleared at bootstrap completion
"""

from unittest.mock import MagicMock, patch, call

import pytest


class FakeMessage:
    """Simulates a paho-mqtt message object."""
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload.encode() if isinstance(payload, str) else payload


class TestBootstrapProtection:
    """Tests that number commands are ignored during bootstrap."""

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

    def test_bootstrap_complete_defaults_to_false(self):
        mqtt = self._mqtt()
        assert mqtt._bootstrap_complete is False

    def test_number_commands_ignored_during_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()

        # Simulate retained message arriving during bootstrap
        msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "15")
        mqtt._on_message(None, None, msg)

        # automation_handler.set_amplitude should NOT have been called
        mqtt.automation_handler.set_amplitude.assert_not_called()

    def test_number_commands_processed_after_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "15")
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_amplitude.assert_called_once_with(15.0)

    def test_heating_duration_ignored_during_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()

        msg = FakeMessage("yutampo/number/yutampo_heating_duration/set", "2")
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_heating_duration.assert_not_called()

    def test_heating_duration_processed_after_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_heating_duration/set", "2")
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_heating_duration.assert_called_once_with(2.0)

    def test_setpoint_ignored_during_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()

        msg = FakeMessage("yutampo/number/yutampo_setpoint/set", "45")
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_setpoint.assert_not_called()

    def test_setpoint_processed_after_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_setpoint/set", "45")
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_setpoint.assert_called_once_with(45.0)


class TestCompleteBootstrap:
    """Tests for the complete_bootstrap() method."""

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

    def test_complete_bootstrap_sets_flag(self):
        mqtt = self._mqtt()
        assert mqtt._bootstrap_complete is False

        mqtt.complete_bootstrap()

        assert mqtt._bootstrap_complete is True

    def test_complete_bootstrap_clears_retained_command_topics(self):
        mqtt = self._mqtt()

        mqtt.complete_bootstrap()

        # Check that empty retained messages were published to clear old retained values
        publish_calls = mqtt.client.publish.call_args_list
        topics_cleared = [c.args[0] for c in publish_calls if c.args[1] == "" and c.kwargs.get("retain", c.args[2] if len(c.args) > 2 else False)]

        assert "yutampo/number/yutampo_amplitude/set" in topics_cleared
        assert "yutampo/number/yutampo_heating_duration/set" in topics_cleared
        assert "yutampo/number/yutampo_setpoint/set" in topics_cleared


class TestClearRetainedCommandTopics:
    """Tests for clearing retained messages on command topics."""

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

    def test_clears_all_number_command_topics(self):
        mqtt = self._mqtt()

        mqtt.clear_retained_command_topics()

        expected_calls = [
            call("yutampo/number/yutampo_amplitude/set", "", retain=True),
            call("yutampo/number/yutampo_heating_duration/set", "", retain=True),
            call("yutampo/number/yutampo_setpoint/set", "", retain=True),
        ]
        mqtt.client.publish.assert_has_calls(expected_calls, any_order=True)


class TestClimateCommandsNotAffected:
    """Verify climate commands still work during bootstrap (if automation_handler exists)."""

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

    def test_climate_mode_command_works_during_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()

        device = MagicMock()
        device.mode = "heat"
        mqtt.devices = {"device1": device}

        msg = FakeMessage("yutampo/climate/device1/mode/set", "off")
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_mode.assert_called_once_with("off")


class TestBootstrapSequence:
    """Integration test verifying the bootstrap sequence in YutampoAddon.start()."""

    def test_complete_bootstrap_called_after_initial_state_publish(self):
        """Verify complete_bootstrap is called after register_numbers in start()."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[1]
        source = (repo_root / "yutampo_addon.py").read_text(encoding="utf-8")
        start_src = source.split("def start(self):", 1)[1]

        register_numbers_at = start_src.find("self.mqtt_handler.register_numbers()")
        complete_bootstrap_at = start_src.find("self.mqtt_handler.complete_bootstrap()")

        assert register_numbers_at != -1, "register_numbers() not found in start()"
        assert complete_bootstrap_at != -1, "complete_bootstrap() not found in start()"
        assert register_numbers_at < complete_bootstrap_at, \
            "complete_bootstrap() must be called after register_numbers()"

    def test_complete_bootstrap_called_after_publish_input_number_state(self):
        """Verify complete_bootstrap is called after initial states are published."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[1]
        source = (repo_root / "yutampo_addon.py").read_text(encoding="utf-8")
        start_src = source.split("def start(self):", 1)[1]

        publish_amplitude_at = start_src.find('publish_input_number_state("yutampo_amplitude"')
        publish_duration_at = start_src.find('publish_input_number_state("yutampo_heating_duration"')
        complete_bootstrap_at = start_src.find("self.mqtt_handler.complete_bootstrap()")

        assert publish_amplitude_at != -1
        assert publish_duration_at != -1
        assert complete_bootstrap_at != -1
        assert publish_amplitude_at < complete_bootstrap_at
        assert publish_duration_at < complete_bootstrap_at
