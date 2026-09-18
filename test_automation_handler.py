"""
Tests unitaires pour la logique de fenêtre de chauffe.

Ces tests vérifient:
1. _is_window_entirely_past(): détection correcte des fenêtres passées
2. Préservation de locked_hottest_hour quand le forecast donne une fenêtre passée

Note: Tests isolés sans import du module complet (dépendances HA non disponibles).
"""

import unittest


def is_window_entirely_past(current_hour, start_hour, end_hour):
    """Copie de la fonction à tester (évite l'import du module complet)."""
    # Cas avec chevauchement sur minuit (ex: 23h-01h): ne pas considérer comme passée
    if start_hour > end_hour:
        return False
    # Cas normal: start <= end (pas de chevauchement)
    return end_hour < current_hour


class TestIsWindowEntirelyPast(unittest.TestCase):
    """Tests pour _is_window_entirely_past()"""

    def test_diurnal_window_past(self):
        """Fenêtre diurne [10h-12h] est passée à 15h."""
        self.assertTrue(is_window_entirely_past(15.0, 10.0, 12.0))

    def test_diurnal_window_current(self):
        """Fenêtre diurne [10h-12h] n'est pas passée à 11h (on est dedans)."""
        self.assertFalse(is_window_entirely_past(11.0, 10.0, 12.0))

    def test_diurnal_window_future(self):
        """Fenêtre diurne [14h-16h] n'est pas passée à 10h."""
        self.assertFalse(is_window_entirely_past(10.0, 14.0, 16.0))

    def test_diurnal_window_at_end(self):
        """Fenêtre diurne [10h-12h] n'est pas passée à 12h exactement."""
        self.assertFalse(is_window_entirely_past(12.0, 10.0, 12.0))

    def test_midnight_wrap_window_never_past(self):
        """Fenêtre wrap [23h-01h] ne doit JAMAIS être considérée comme passée.
        
        Sans information de date, on ne peut pas distinguer:
        - 15h aujourd'hui (fenêtre à venir ce soir)
        - 15h demain (fenêtre passée hier soir)
        
        Par sécurité, on retourne toujours False pour les fenêtres wrap.
        """
        # À 15h, fenêtre [23h-01h] pourrait être ce soir → pas passée
        self.assertFalse(is_window_entirely_past(15.0, 23.0, 1.0))
        # À 2h, fenêtre [23h-01h] vient de finir mais pourrait revenir → pas passée
        self.assertFalse(is_window_entirely_past(2.0, 23.0, 1.0))
        # À 22h, fenêtre [23h-01h] commence bientôt → pas passée
        self.assertFalse(is_window_entirely_past(22.0, 23.0, 1.0))
        # À 0h30, dans la fenêtre → pas passée
        self.assertFalse(is_window_entirely_past(0.5, 23.0, 1.0))

    def test_edge_case_start_equals_end(self):
        """Cas limite: start == end (fenêtre de durée 0)."""
        # Une fenêtre de durée 0 à 12h est "passée" après 12h
        self.assertTrue(is_window_entirely_past(13.0, 12.0, 12.0))
        self.assertFalse(is_window_entirely_past(11.0, 12.0, 12.0))


class TestLockedHottestHourPreservation(unittest.TestCase):
    """Tests pour la logique de préservation de locked_hottest_hour.
    
    Ces tests simulent la logique sans importer le module complet.
    """

    def _simulate_get_locked_hottest_hour(
        self, current_hour, live_hour, locked_hour, heating_duration, in_window
    ):
        """Simule la logique de _get_locked_hottest_hour."""
        if in_window:
            return locked_hour
        
        def get_window(h):
            return (h - heating_duration / 2, h + heating_duration / 2)
        
        start, end = get_window(live_hour)
        
        if is_window_entirely_past(current_hour, start, end):
            if locked_hour is not None:
                prev_start, prev_end = get_window(locked_hour)
                if not is_window_entirely_past(current_hour, prev_start, prev_end):
                    return locked_hour
        return live_hour

    def test_locked_hour_preserved_when_forecast_past(self):
        """Le locked_hottest_hour est préservé si le forecast donne une fenêtre passée."""
        result = self._simulate_get_locked_hottest_hour(
            current_hour=14.0,
            live_hour=10.0,      # Forecast: 10h → fenêtre [9h-11h] = passée
            locked_hour=15.0,   # Locked: 15h → fenêtre [14h-16h] = valide
            heating_duration=2.0,
            in_window=False
        )
        self.assertEqual(result, 15.0)

    def test_locked_hour_updated_when_forecast_valid(self):
        """Le locked_hottest_hour est mis à jour si le forecast donne une fenêtre valide."""
        result = self._simulate_get_locked_hottest_hour(
            current_hour=10.0,
            live_hour=14.0,     # Forecast: 14h → fenêtre [13h-15h] = future
            locked_hour=12.0,
            heating_duration=2.0,
            in_window=False
        )
        self.assertEqual(result, 14.0)

    def test_both_windows_past_accepts_new_forecast(self):
        """Si les deux fenêtres sont passées, on accepte le nouveau forecast."""
        result = self._simulate_get_locked_hottest_hour(
            current_hour=18.0,
            live_hour=10.0,     # Forecast: 10h → fenêtre [9h-11h] = passée
            locked_hour=12.0,   # Locked: 12h → fenêtre [11h-13h] = aussi passée
            heating_duration=2.0,
            in_window=False
        )
        self.assertEqual(result, 10.0)

    def test_no_locked_hour_accepts_forecast(self):
        """Sans locked_hour précédent, on accepte le forecast même si passé."""
        result = self._simulate_get_locked_hottest_hour(
            current_hour=14.0,
            live_hour=10.0,     # Forecast: 10h → fenêtre [9h-11h] = passée
            locked_hour=None,   # Pas de valeur précédente
            heating_duration=2.0,
            in_window=False
        )
        self.assertEqual(result, 10.0)


if __name__ == '__main__':
    unittest.main()
