## Fonctionnalités avancées

### Thermostat virtuel

L'addon crée automatiquement un thermostat virtuel (`climate.yutampo_thermostat_virtual`) qui permet de définir :

- La consigne cible (`target_temperature`).
- La plage de variation (`target_temperature_low` et `target_temperature_high`).
- Les préréglages saisonniers (`preset_mode`), avec les options "Hiver", "Printemps/Automne", et "Été".

Chaque préréglage ajuste automatiquement la consigne, la plage de variation, et la durée de la plage de variation selon les paramètres définis dans les options de l’addon (`preset_durations`).

### Automation interne

L'addon intègre une automation interne qui ajuste graduellement la consigne du Yutampo physique (`climate.chauffe_eau_chauffe_eau`) en fonction :

- De l’heure la plus chaude de la journée, déterminée à partir des prévisions météo de l’entité `weather.home`.
- Des paramètres définis dans le thermostat virtuel et des durées associées aux préréglages dans les options de l’addon.

La consigne varie linéairement entre `target_temperature_low` et `target_temperature_high` sur la durée spécifiée pour le préréglage actif, centrée sur l’heure la plus chaude. En dehors de cette plage, la consigne est fixée à `target_temperature_low`.

### Configuration des préréglages

Les durées de variation pour chaque préréglage sont configurables dans les options de l’addon (`/data/options.json`). Par défaut :

- `"Hiver": 6` heures
- `"Printemps/Automne": 5` heures
- `"Été": 4` heures

Exemple de configuration personnalisée :

```json
{
  "username": "ton_username",
  "password": "ton_password",
  "scan_interval": 300,
  "preset_durations": {
    "Hiver": 7,
    "Printemps/Automne": 5,
    "Été": 3
  },
  "mqtt_host": "<auto_detect>",
  "mqtt_port": "<auto_detect>",
  "mqtt_user": "<auto_detect>",
  "mqtt_password": "<auto_detect>"
}
```
