"""Tests for bootstrap protection against retained MQTT command messages.

On addon restart, the MQTT broker may redeliver retained messages on command topics
(e.g., .../set) as if the user had just sent those commands. This would overwrite
config values with stale retained data.

The fix:
1. _bootstrap_complete flag prevents number commands from being processed at startup
2. Retained messages (msg.retain=True) on number command topics are always ignored
3. complete_bootstrap() is called after initial state publication
4. Retained messages on command topics are cleared on every connect/reconnect
5. Discovery payloads for number entities use retain=False
"""

from unittest.mock import MagicMock, patch, call

import pytest


class FakeMessage:
    """Simulates a paho-mqtt message object."""
    def __init__(self, topic, payload, retain=False):
        self.topic = topic
        self.payload = payload.encode() if isinstance(payload, str) else payload
        self.retain = retain


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

    def test_number_commands_processed_after_bootstrap_non_retained(self):
        """Non-retained live commands work after bootstrap."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "15", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_amplitude.assert_called_once_with(15.0)

    def test_heating_duration_ignored_during_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()

        msg = FakeMessage("yutampo/number/yutampo_heating_duration/set", "2")
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_heating_duration.assert_not_called()

    def test_heating_duration_processed_after_bootstrap_non_retained(self):
        """Non-retained live commands work after bootstrap."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_heating_duration/set", "2", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_heating_duration.assert_called_once_with(2.0)

    def test_setpoint_ignored_during_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()

        msg = FakeMessage("yutampo/number/yutampo_setpoint/set", "45")
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_setpoint.assert_not_called()

    def test_setpoint_processed_after_bootstrap_non_retained(self):
        """Non-retained live commands work after bootstrap."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_setpoint/set", "45", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_setpoint.assert_called_once_with(45.0)


class TestRetainedMessagesIgnoredAfterBootstrap:
    """Tests that retained messages on number topics are ALWAYS ignored, even post-bootstrap."""

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

    def test_retained_amplitude_ignored_after_bootstrap(self):
        """Retained messages are ignored even after bootstrap (e.g., on reconnect)."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "15", retain=True)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_amplitude.assert_not_called()

    def test_retained_heating_duration_ignored_after_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_heating_duration/set", "2", retain=True)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_heating_duration.assert_not_called()

    def test_retained_setpoint_ignored_after_bootstrap(self):
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_setpoint/set", "45", retain=True)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_setpoint.assert_not_called()

    def test_non_retained_still_processed_after_retained_ignored(self):
        """After ignoring a retained message, non-retained messages still work."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        # First, a retained message (ignored)
        retained_msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "15", retain=True)
        mqtt._on_message(None, None, retained_msg)
        mqtt.automation_handler.set_amplitude.assert_not_called()

        # Then, a live non-retained message (processed)
        live_msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "20", retain=False)
        mqtt._on_message(None, None, live_msg)
        mqtt.automation_handler.set_amplitude.assert_called_once_with(20.0)


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
        topics_cleared = [c.args[0] for c in publish_calls]

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

    def test_clears_all_number_command_topics_with_qos1(self):
        """Clear uses QoS 1 for durability."""
        mqtt = self._mqtt()

        mqtt.clear_retained_command_topics()

        expected_calls = [
            call("yutampo/number/yutampo_amplitude/set", "", qos=1, retain=True),
            call("yutampo/number/yutampo_heating_duration/set", "", qos=1, retain=True),
            call("yutampo/number/yutampo_setpoint/set", "", qos=1, retain=True),
        ]
        mqtt.client.publish.assert_has_calls(expected_calls, any_order=True)

    def test_clears_with_empty_payload(self):
        """Clear uses empty string payload to remove retained message."""
        mqtt = self._mqtt()

        mqtt.clear_retained_command_topics()

        for call_args in mqtt.client.publish.call_args_list:
            assert call_args.args[1] == "", "Payload must be empty string to clear retained"
            assert call_args.kwargs.get("retain") is True, "Must use retain=True to clear"


class TestOnConnectClearsRetained:
    """Tests that _on_connect clears retained command topics before subscribing."""

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

    def test_on_connect_clears_retained_before_subscribe(self):
        """On connect/reconnect, retained are cleared before subscribe."""
        mqtt = self._mqtt()

        # Track call order
        call_order = []
        original_clear = mqtt.clear_retained_command_topics
        original_subscribe = mqtt.subscribe_topics

        def tracked_clear():
            call_order.append("clear")
            original_clear()

        def tracked_subscribe():
            call_order.append("subscribe")
            original_subscribe()

        mqtt.clear_retained_command_topics = tracked_clear
        mqtt.subscribe_topics = tracked_subscribe

        # Simulate connection
        mqtt._on_connect(mqtt.client, None, None, 0)

        assert "clear" in call_order
        assert "subscribe" in call_order
        assert call_order.index("clear") < call_order.index("subscribe"), \
            "clear_retained_command_topics must be called before subscribe_topics"

    def test_on_connect_clears_retained_even_after_bootstrap(self):
        """On reconnect (post-bootstrap), retained are still cleared."""
        mqtt = self._mqtt()
        mqtt._bootstrap_complete = True

        mqtt._on_connect(mqtt.client, None, None, 0)

        # Verify clear was called - check for empty payload publishes to /set topics
        clear_calls = []
        for c in mqtt.client.publish.call_args_list:
            topic = c.args[0] if c.args else c.kwargs.get("topic", "")
            payload = c.args[1] if len(c.args) > 1 else c.kwargs.get("payload", None)
            if payload == "" and "set" in topic:
                clear_calls.append(c)
        assert len(clear_calls) == 3, "Should clear all 3 command topics on reconnect"


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


class TestDiscoveryPayloadsRetainFalse:
    """Verify number entity discovery payloads use retain=False."""

    def test_amplitude_payload_retain_false(self):
        from mqtt_handler import AMPLITUDE_PAYLOAD
        assert AMPLITUDE_PAYLOAD.get("retain") is False, \
            "AMPLITUDE_PAYLOAD must have retain=False to prevent HA republishing stale commands"

    def test_heating_duration_payload_retain_false(self):
        from mqtt_handler import HEATING_DURATION_PAYLOAD
        assert HEATING_DURATION_PAYLOAD.get("retain") is False, \
            "HEATING_DURATION_PAYLOAD must have retain=False to prevent HA republishing stale commands"

    def test_setpoint_payload_retain_false(self):
        from mqtt_handler import SETPOINT_PAYLOAD
        assert SETPOINT_PAYLOAD.get("retain") is False, \
            "SETPOINT_PAYLOAD must have retain=False to prevent HA republishing stale commands"

    def test_sensor_payloads_can_still_retain(self):
        """Sensor payloads (non-command) can use retain=True as they have no command_topic."""
        from mqtt_handler import HOTTEST_HOUR_PAYLOAD, REGULATION_STATE_PAYLOAD
        # These are sensors/binary_sensors - retain is fine for state
        assert HOTTEST_HOUR_PAYLOAD.get("retain") is True
        assert REGULATION_STATE_PAYLOAD.get("retain") is True


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

    def test_on_connect_calls_clear_before_subscribe(self):
        """Verify _on_connect clears retained before subscribing."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[1]
        source = (repo_root / "mqtt_handler.py").read_text(encoding="utf-8")
        on_connect_src = source.split("def _on_connect(", 1)[1].split("\n    def ")[0]

        clear_at = on_connect_src.find("self.clear_retained_command_topics()")
        subscribe_at = on_connect_src.find("self.subscribe_topics()")

        assert clear_at != -1, "clear_retained_command_topics not found in _on_connect"
        assert subscribe_at != -1, "subscribe_topics not found in _on_connect"
        assert clear_at < subscribe_at, \
            "clear_retained_command_topics must be called before subscribe_topics in _on_connect"
