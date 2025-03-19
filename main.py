import subprocess
import os
from datetime import datetime
from yutampo_addon import YutampoAddon


def log_startup_message():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"Démarrage de l'addon Yutampo HA - {timestamp}"
    border = "*" * (len(msg) + 4)
    framed_message = f"\n{border}\n* {msg} *\n{border}"
    # Créer un script shell temporaire
    script_content = f"""#!/usr/bin/with-contenv bashio
bashio::log.info "{framed_message}"
"""
    with open("/tmp/log_script.sh", "w") as f:
        f.write(script_content)
    # Rendre le script exécutable
    os.chmod("/tmp/log_script.sh", 0o755)
    # Exécuter le script et rediriger stderr
    subprocess.run("/tmp/log_script.sh 2>&1", shell=True, check=True)
    # Nettoyer
    os.remove("/tmp/log_script.sh")


if __name__ == "__main__":
    log_startup_message()
    addon = YutampoAddon(config_path="/data/options.json")
    addon.start()
