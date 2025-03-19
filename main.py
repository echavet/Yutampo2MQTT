# main.py
import subprocess
import logging
from datetime import datetime
from yutampo_addon import YutampoAddon

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("Yutampo_ha_addon")


# def log_startup_message():
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     msg = f"Démarrage de l'addon Yutampo HA - {timestamp}"
#     border = "*" * (len(msg) + 4)
#     # Formatage sans codes ANSI, en s'appuyant sur le niveau de log
#     framed_message = f"{border}\n* {msg} *\n{border}"
#     LOGGER.info(framed_message)  # Utilise INFO pour imiter bashio::log.info
def log_startup_message():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"Démarrage de l'addon Yutampo HA - {timestamp}"
    border = "*" * (len(msg) + 4)
    framed_message = f"\\n{border}\\n* {msg} *\\n{border}"
    # Rediriger explicitement stderr vers stdout
    command = (
        f'/usr/bin/with-contenv bash -c "bashio::log.info \\"{framed_message}\\"" 2>&1'
    )
    subprocess.run(command, shell=True, check=True)


if __name__ == "__main__":
    log_startup_message()
    addon = YutampoAddon(config_path="/data/options.json")
    addon.start()
