"""Tests des calculs de fenêtre de chauffe (wrap minuit inclus)."""

import pytest

from tests.helpers import make_handler


class TestGetHeatingWindow:
    @pytest.mark.parametrize(
        "hottest, duration, expected_start, expected_end",
        [
            (14.0, 1.0, 13.5, 14.5),
            (14.0, 6.0, 11.0, 17.0),
            (10.0, 1.0, 9.5, 10.5),
            (15.0, 2.0, 14.0, 16.0),
            # Wrap minuit : hottest proche de 0h
            (0.0, 2.0, 23.0, 1.0),
            (1.0, 6.0, 22.0, 4.0),
            (23.0, 2.0, 22.0, 0.0),
            (0.5, 1.0, 0.0, 1.0),
        ],
    )
    def test_window_bounds(self, hottest, duration, expected_start, expected_end):
        handler = make_handler(heating_duration=duration)
        start, end = handler._get_heating_window(hottest)
        assert start == pytest.approx(expected_start)
        assert end == pytest.approx(expected_end)


class TestIsWithinHeatingWindow:
    @pytest.mark.parametrize(
        "current, start, end, expected",
        [
            # Fenêtre diurne 13.5–14.5
            (13.49, 13.5, 14.5, False),
            (13.5, 13.5, 14.5, True),  # borne début inclusive
            (14.0, 13.5, 14.5, True),
            (14.49, 13.5, 14.5, True),
            (14.5, 13.5, 14.5, False),  # borne fin exclusive
            (12.25, 13.5, 14.5, False),
            (12.25, 9.5, 10.5, False),
            # Wrap 23h–01h
            (23.0, 23.0, 1.0, True),
            (23.5, 23.0, 1.0, True),
            (0.0, 23.0, 1.0, True),
            (0.5, 23.0, 1.0, True),
            (1.0, 23.0, 1.0, False),  # fin exclusive
            (1.5, 23.0, 1.0, False),
            (22.0, 23.0, 1.0, False),  # avant le début
            (12.0, 23.0, 1.0, False),
            # Wrap 22h–00h (end == 0)
            (22.0, 22.0, 0.0, True),
            (23.5, 22.0, 0.0, True),
            (0.0, 22.0, 0.0, False),
            (21.0, 22.0, 0.0, False),
        ],
    )
    def test_within_window(self, current, start, end, expected):
        handler = make_handler()
        assert handler._is_within_heating_window(current, start, end) is expected


class TestIsWindowEntirelyPast:
    """Contrats de _is_window_entirely_past pour le anti-window-chasing."""

    @pytest.mark.parametrize(
        "current, start, end, expected",
        [
            # Fenêtre diurne 13.5–14.5
            (12.25, 13.5, 14.5, False),  # encore à venir
            (13.5, 13.5, 14.5, False),  # entrée
            (14.0, 13.5, 14.5, False),  # dedans
            (14.5, 13.5, 14.5, False),  # égalité : pas strictement passé
            (14.51, 13.5, 14.5, True),
            (18.0, 13.5, 14.5, True),
            # Scénario 18 sept : forecast 10h à 12h25, duration=1h → [9.5–10.5]
            (12.4167, 9.5, 10.5, True),
            (10.5, 9.5, 10.5, False),
            (10.51, 9.5, 10.5, True),
            (9.0, 9.5, 10.5, False),
        ],
    )
    def test_non_wrapping_windows(self, current, start, end, expected):
        handler = make_handler()
        assert handler._is_window_entirely_past(current, start, end) is expected

    @pytest.mark.parametrize(
        "current, start, end, expected",
        [
            # Wrap 23h–01h : pendant la fenêtre → pas passé
            (23.0, 23.0, 1.0, False),
            (23.5, 23.0, 1.0, False),
            (0.0, 23.0, 1.0, False),
            (0.99, 23.0, 1.0, False),
            # Juste après la fin → passé
            (1.01, 23.0, 1.0, True),
            (2.0, 23.0, 1.0, True),
            (12.0, 23.0, 1.0, True),
        ],
    )
    def test_wrapping_window_in_and_after(self, current, start, end, expected):
        handler = make_handler()
        assert handler._is_window_entirely_past(current, start, end) is expected

    def test_wrapping_gap_before_start_known_limitation(self):
        """À 22h, la fenêtre 23h–01h n'a pas encore commencé.

        L'implémentation actuelle traite tout le « gap » wrap
        (`end < current < start`) comme passé, y compris la période
        *avant* le début. C'est le cas limite signalé en revue de PR #57.

        Impact pratique faible (hottest_hour est typiquement diurne).
        """
        handler = make_handler()
        assert handler._is_window_entirely_past(22.0, 23.0, 1.0) is True

    @pytest.mark.xfail(
        reason=(
            "Limitation wrap minuit : à 22h une fenêtre 23h-01h est encore "
            "atteignable et ne devrait pas être considérée comme passée."
        ),
        strict=False,
    )
    def test_wrapping_window_not_past_when_start_still_ahead(self):
        handler = make_handler()
        assert handler._is_window_entirely_past(22.0, 23.0, 1.0) is False

    def test_entirely_past_implies_not_within(self):
        """Invariant : une fenêtre entièrement passée n'est jamais 'within'."""
        handler = make_handler()
        samples = [
            (12.25, 9.5, 10.5),
            (18.0, 13.5, 14.5),
            (2.0, 23.0, 1.0),
            (12.0, 23.0, 1.0),
            (14.51, 13.5, 14.5),
        ]
        for current, start, end in samples:
            if handler._is_window_entirely_past(current, start, end):
                assert handler._is_within_heating_window(current, start, end) is False
