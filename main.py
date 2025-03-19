import subprocess
from datetime import datetime
from yutampo_addon import YutampoAddon


def log_startup_message():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"Démarrage de l'addon Yutampo HA - {timestamp}"
    border = "*" * (len(msg) + 4)
    framed_message = f"\\n{border}\\n* {msg} *\\n{border}"
    # Charger bashio explicitement et appeler bashio::log.info
    command = f'/usr/bin/with-contenv bash -c "source /usr/lib/bashio/bashio.sh && bashio::log.info \\"{framed_message}\\"" 2>&1'
    subprocess.run(command, shell=True, check=True)


if __name__ == "__main__":
    log_startup_message()
    addon = YutampoAddon(config_path="/data/options.json")
    addon.start()
