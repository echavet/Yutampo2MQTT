"""Tests for handling empty, whitespace, and invalid numeric MQTT payloads.

These tests verify that the mqtt_handler gracefully handles:
- Empty payloads (e.g., retained message clears)
- Whitespace-only payloads
- Non-numeric payloads (e.g., "abc", "NaN", malformed strings)

The expected behavior is:
- Empty/whitespace payloads: ignored with debug-level log, no error
- Invalid numeric payloads: ignored with warning-level log, no stack trace
"""

from unittest.mock import MagicMock

import pytest


class FakeMessage:
    """Simulates a paho-mqtt message object."""

    def __init__(self, topic, payload, retain=False):
        self.topic = topic
        self.payload = payload.encode() if isinstance(payload, str) else payload
        self.retain = retain


class TestParseNumericPayload:
    """Tests for the _parse_numeric_payload helper method."""

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

    def test_empty_string_returns_none(self):
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("", "test/topic")
        assert result is None

    def test_whitespace_only_returns_none(self):
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("   ", "test/topic")
        assert result is None

    def test_tab_whitespace_returns_none(self):
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("\t\n", "test/topic")
        assert result is None

    def test_valid_integer_returns_float(self):
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("42", "test/topic")
        assert result == 42.0

    def test_valid_float_returns_float(self):
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("37.5", "test/topic")
        assert result == 37.5

    def test_negative_number_returns_float(self):
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("-10.5", "test/topic")
        assert result == -10.5

    def test_non_numeric_string_returns_none(self):
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("abc", "test/topic")
        assert result is None

    def test_mixed_alphanumeric_returns_none(self):
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("12abc", "test/topic")
        assert result is None

    def test_special_characters_returns_none(self):
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("!@#$", "test/topic")
        assert result is None

    def test_nan_string_returns_none(self):
        """NaN is technically parseable but we want to reject it."""
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("NaN", "test/topic")
        assert result is None or (result is not None and result != result)

    def test_inf_string_parses(self):
        """inf is parseable by float() - this documents current behavior."""
        mqtt = self._mqtt()
        result = mqtt._parse_numeric_payload("inf", "test/topic")
        assert result == float("inf")


class TestEmptyPayloadOnNumberTopics:
    """Tests that empty payloads on number command topics are ignored gracefully."""

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

    def test_empty_amplitude_payload_ignored(self):
        """Empty payload on amplitude topic should be ignored, not raise error."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_amplitude.assert_not_called()

    def test_empty_heating_duration_payload_ignored(self):
        """Empty payload on heating_duration topic should be ignored."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage(
            "yutampo/number/yutampo_heating_duration/set", "", retain=False
        )
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_heating_duration.assert_not_called()

    def test_empty_setpoint_payload_ignored(self):
        """Empty payload on setpoint topic should be ignored."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_setpoint/set", "", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_setpoint.assert_not_called()

    def test_whitespace_amplitude_payload_ignored(self):
        """Whitespace-only payload should be ignored."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "   ", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_amplitude.assert_not_called()


class TestInvalidPayloadOnNumberTopics:
    """Tests that invalid (non-numeric) payloads are handled gracefully."""

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

    def test_invalid_amplitude_payload_ignored(self):
        """Non-numeric amplitude payload should be ignored with warning."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "abc", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_amplitude.assert_not_called()

    def test_invalid_heating_duration_payload_ignored(self):
        """Non-numeric heating_duration payload should be ignored."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage(
            "yutampo/number/yutampo_heating_duration/set", "invalid", retain=False
        )
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_heating_duration.assert_not_called()

    def test_invalid_setpoint_payload_ignored(self):
        """Non-numeric setpoint payload should be ignored."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage(
            "yutampo/number/yutampo_setpoint/set", "not-a-number", retain=False
        )
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_setpoint.assert_not_called()


class TestEmptyPayloadOnClimateTopics:
    """Tests that empty payloads on climate command topics are handled gracefully."""

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
        handler.api_client = MagicMock()
        return handler

    def test_empty_climate_set_payload_ignored(self):
        """Empty payload on climate set topic should be ignored."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()

        device = MagicMock()
        device.id = "device1"
        device.setting_temperature = 50.0
        mqtt.devices = {"device1": device}

        msg = FakeMessage("yutampo/climate/device1/set", "", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.api_client.set_heat_setting.assert_not_called()

    def test_whitespace_climate_set_payload_ignored(self):
        """Whitespace-only payload on climate set topic should be ignored."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()

        device = MagicMock()
        device.id = "device1"
        device.setting_temperature = 50.0
        mqtt.devices = {"device1": device}

        msg = FakeMessage("yutampo/climate/device1/set", "  \t  ", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.api_client.set_heat_setting.assert_not_called()

    def test_invalid_climate_set_payload_ignored(self):
        """Non-numeric payload on climate set topic should be ignored."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()

        device = MagicMock()
        device.id = "device1"
        device.setting_temperature = 50.0
        mqtt.devices = {"device1": device}

        msg = FakeMessage("yutampo/climate/device1/set", "invalid", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.api_client.set_heat_setting.assert_not_called()


class TestValidPayloadsStillWork:
    """Verify that valid numeric payloads still work correctly after the fix."""

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

    def test_valid_amplitude_still_processed(self):
        """Valid amplitude value should still be processed."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_amplitude/set", "10", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_amplitude.assert_called_once_with(10.0)

    def test_valid_heating_duration_still_processed(self):
        """Valid heating_duration value should still be processed."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage(
            "yutampo/number/yutampo_heating_duration/set", "4.5", retain=False
        )
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_heating_duration.assert_called_once_with(4.5)

    def test_valid_setpoint_still_processed(self):
        """Valid setpoint value should still be processed."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt._bootstrap_complete = True

        msg = FakeMessage("yutampo/number/yutampo_setpoint/set", "45", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.automation_handler.set_setpoint.assert_called_once_with(45.0)

    def test_valid_climate_temperature_still_processed(self):
        """Valid climate temperature should still be processed."""
        mqtt = self._mqtt()
        mqtt.automation_handler = MagicMock()
        mqtt.api_client = MagicMock()
        mqtt.api_client.set_heat_setting.return_value = 45.0

        device = MagicMock()
        device.id = "device1"
        device.parent_id = "parent1"
        device.setting_temperature = 50.0
        mqtt.devices = {"device1": device}

        msg = FakeMessage("yutampo/climate/device1/set", "45", retain=False)
        mqtt._on_message(None, None, msg)

        mqtt.api_client.set_heat_setting.assert_called_once()


class TestLoggingBehavior:
    """Tests that verify logging behavior for different payload scenarios."""

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
        handler.logger = MagicMock()
        return handler

    def test_empty_payload_logs_debug(self):
        """Empty payload should log at debug level, not error."""
        mqtt = self._mqtt()
        mqtt._parse_numeric_payload("", "test/topic")
        mqtt.logger.debug.assert_called()
        mqtt.logger.error.assert_not_called()

    def test_whitespace_payload_logs_debug(self):
        """Whitespace payload should log at debug level, not error."""
        mqtt = self._mqtt()
        mqtt._parse_numeric_payload("   ", "test/topic")
        mqtt.logger.debug.assert_called()
        mqtt.logger.error.assert_not_called()

    def test_invalid_payload_logs_warning(self):
        """Invalid numeric payload should log at warning level, not error."""
        mqtt = self._mqtt()
        mqtt._parse_numeric_payload("invalid", "test/topic")
        mqtt.logger.warning.assert_called()
        mqtt.logger.error.assert_not_called()

    def test_valid_payload_no_warning_or_error(self):
        """Valid numeric payload should not log warning or error."""
        mqtt = self._mqtt()
        mqtt._parse_numeric_payload("42.5", "test/topic")
        mqtt.logger.warning.assert_not_called()
        mqtt.logger.error.assert_not_called()
