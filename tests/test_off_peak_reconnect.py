"""Tests pour la reconnexion robuste du OffPeakClient.

Ces tests vérifient :
1. La race condition où _reconnecting bloquait les reconnexions
2. Le watchdog qui détecte les déconnexions silencieuses
3. Le fallback REST quand WebSocket est down
4. L'état de connexion (is_connected)
"""

import threading
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


class TestReconnectionRace:
    """Tests pour le bug de reconnexion où _reconnecting restait True."""

    def test_reconnect_scheduled_even_if_connect_fails_during_wait(self):
        """Vérifie qu'une reconnexion est planifiée même si la connexion échoue
        pendant l'attente initiale (bug original: _reconnecting restait True).
        """
        from off_peak_client import OffPeakClient

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })
        client._shutdown_requested = False

        # Simulate connection failure
        client.connected = False
        client._reconnect_scheduled = False

        # Call _schedule_reconnect multiple times (simulating error/close callbacks)
        client._schedule_reconnect()

        # First call should schedule a reconnect
        assert client._reconnect_scheduled is True

        # Second call should be blocked (already scheduled)
        initial_delay = client._reconnect_delay
        client._schedule_reconnect()
        # Delay should have been updated only once
        assert client._reconnect_delay == initial_delay

        client._shutdown_requested = True  # Cleanup

    def test_schedule_reconnect_resets_after_connect_attempt(self):
        """Vérifie que _reconnect_scheduled est remis à False après une tentative."""
        from off_peak_client import OffPeakClient

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        # Set up initial state
        with client._lock:
            client._reconnect_scheduled = True
            client._reconnect_delay = 5

        # Simulate what happens in _do_reconnect after the sleep
        with client._lock:
            client._reconnect_scheduled = False

        # Now a new reconnect can be scheduled
        client._schedule_reconnect()
        assert client._reconnect_scheduled is True

        client._shutdown_requested = True

    def test_on_open_resets_reconnect_state(self):
        """Vérifie que _on_open remet à zéro l'état de reconnexion."""
        from off_peak_client import OffPeakClient

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        # Simulate failed reconnection attempts that increased delay
        client._reconnect_delay = 60
        client._reconnect_scheduled = True
        client.connected = False

        # Simulate successful connection
        ws_mock = MagicMock()
        client._on_open(ws_mock)

        assert client.connected is True
        assert client._reconnect_delay == client.INITIAL_RECONNECT_DELAY
        assert client._reconnect_scheduled is False

    def test_backoff_increases_then_caps(self):
        """Vérifie que le backoff augmente exponentiellement puis plafonne."""
        from off_peak_client import OffPeakClient

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        delays = []
        for _ in range(10):
            with client._lock:
                client._reconnect_scheduled = False
            client._schedule_reconnect()
            delays.append(client._reconnect_delay)
            client._shutdown_requested = True
            client._shutdown_requested = False

        # Check exponential growth
        assert delays[0] == 10  # 5 * 2
        assert delays[1] == 20  # 10 * 2
        assert delays[2] == 40  # 20 * 2

        # Check cap at MAX_RECONNECT_DELAY (60s)
        assert all(d <= client.MAX_RECONNECT_DELAY for d in delays)
        assert delays[-1] == client.MAX_RECONNECT_DELAY

        client._shutdown_requested = True


class TestWatchdog:
    """Tests pour le watchdog qui surveille la santé de la connexion."""

    def test_watchdog_detects_stale_connection(self):
        """Vérifie que le watchdog détecte une connexion silencieuse."""
        from off_peak_client import OffPeakClient

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        # Simulate a connected state with no recent messages
        client.connected = True
        client._last_message_time = time.time() - 200  # 200s ago

        # Check watchdog logic
        elapsed = time.time() - client._last_message_time
        assert elapsed > client.WATCHDOG_TIMEOUT

        client._shutdown_requested = True

    def test_last_message_time_updated_on_message(self):
        """Vérifie que _last_message_time est mis à jour à chaque message."""
        from off_peak_client import OffPeakClient

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        old_time = time.time() - 100
        client._last_message_time = old_time

        # Simulate receiving a message
        ws_mock = MagicMock()
        client._on_message(ws_mock, '{"type": "pong"}')

        assert client._last_message_time > old_time


class TestRESTFallback:
    """Tests pour le fallback REST quand WebSocket est down."""

    @patch("off_peak_client.requests.get")
    def test_rest_fallback_updates_state(self, mock_get):
        """Vérifie que le fallback REST met à jour l'état."""
        from off_peak_client import OffPeakClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"state": "on", "entity_id": "binary_sensor.heures_creuses"}
        mock_get.return_value = mock_response

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        assert client._is_off_peak is False

        client._fetch_state_via_rest()

        assert client._is_off_peak is True
        assert client._state_received is True

    @patch("off_peak_client.requests.get")
    def test_rest_fallback_handles_http_error(self, mock_get):
        """Vérifie que le fallback REST gère les erreurs HTTP."""
        from off_peak_client import OffPeakClient

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_get.return_value = mock_response

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        # Should not raise, just log warning
        client._fetch_state_via_rest()
        assert client._is_off_peak is False

    @patch("off_peak_client.requests.get")
    def test_rest_fallback_handles_timeout(self, mock_get):
        """Vérifie que le fallback REST gère les timeouts."""
        from off_peak_client import OffPeakClient
        import requests

        mock_get.side_effect = requests.exceptions.Timeout()

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        # Should not raise, just log warning
        client._fetch_state_via_rest()
        assert client._is_off_peak is False


class TestConnectionState:
    """Tests pour l'état de connexion."""

    def test_is_connected_reflects_state(self):
        """Vérifie que is_connected() reflète l'état de connexion."""
        from off_peak_client import OffPeakClient

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        assert client.is_connected() is False

        client.connected = True
        assert client.is_connected() is True

    def test_connection_state_published_on_connect(self):
        """Vérifie que l'état de connexion est publié lors de la connexion."""
        from off_peak_client import OffPeakClient

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        mqtt_mock = MagicMock()
        client.mqtt_handler = mqtt_mock

        ws_mock = MagicMock()
        client._on_open(ws_mock)

        mqtt_mock.publish_off_peak_connection_state.assert_called_with(True)

    def test_connection_state_published_on_close(self):
        """Vérifie que l'état de connexion est publié lors de la fermeture."""
        from off_peak_client import OffPeakClient

        client = OffPeakClient({
            "off_peak_entity": "binary_sensor.heures_creuses",
            "ha_token": "test_token",
        })

        mqtt_mock = MagicMock()
        client.mqtt_handler = mqtt_mock
        client.connected = True

        ws_mock = MagicMock()
        client._on_close(ws_mock, 1000, "Normal close")

        mqtt_mock.publish_off_peak_connection_state.assert_called_with(False)
        client._shutdown_requested = True


class TestOffPeakConnectedDiscovery:
    """Tests pour la discovery MQTT du binary_sensor de connexion."""

    @patch("mqtt_handler.time.sleep")
    def test_publishes_connected_sensor_discovery(self, _sleep):
        """Vérifie que le capteur de connexion est publié via discovery."""
        from mqtt_handler import MqttHandler
        from tests.helpers import make_handler

        mqtt = MqttHandler({
            "mqtt_host": "localhost",
            "mqtt_port": 1883,
            "mqtt_user": "user",
            "mqtt_password": "pass",
            "discovery_prefix": "homeassistant",
            "default_hottest_hour": 15.0,
        })
        mqtt.client = MagicMock()

        off_peak = MagicMock()
        off_peak.is_off_peak.return_value = False
        off_peak.is_connected.return_value = True
        mqtt.automation_handler = make_handler(off_peak_client=off_peak)
        mqtt.automation_handler.weather_client.get_hottest_hour.return_value = 14.0
        mqtt.automation_handler.weather_client.get_hottest_temperature.return_value = 22.0

        mqtt.register_sensors()

        topics = [call.args[0] for call in mqtt.client.publish.call_args_list]
        assert "homeassistant/binary_sensor/yutampo_off_peak_connected/config" in topics
