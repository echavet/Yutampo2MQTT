import logging
import sys
from datetime import datetime
from yutampo_addon import YutampoAddon

# Codes ANSI pour les couleurs
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

# Configuration du logger avec horodatage
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("YutampoAddon")


# Formatter pour ajouter des couleurs
class ColoredFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        if record.levelno == logging.INFO:
            return f"{GREEN}{msg}{RESET}"
        elif record.levelno == logging.WARNING:
            return f"{YELLOW}{msg}{RESET}"
        elif record.levelno == logging.ERROR:
            return f"{RED}{msg}{RESET}"
        return msg


# Utiliser un StreamHandler qui écrit sur stderr
handler = logging.StreamHandler(stream=sys.stderr)
handler.setFormatter(ColoredFormatter())
logger.handlers = [handler]


def log_startup_message():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"Démarrage de l'addon Yutampo HA - {timestamp}"
    border = "*" * (len(msg) + 4)
    framed_message = f"\n{border}\n* {msg} *\n{border}"
    logger.info(framed_message)


if __name__ == "__main__":
    log_startup_message()
    addon = YutampoAddon(config_path="/data/options.json")
    addon.start()
