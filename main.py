import argparse
import logging

from src.config import DATA_DIR
from src.notify import send_alerts, send_value_alerts
from src.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NFL AI Predictor")
    parser.add_argument("--update", action="store_true", help="Recalcule les Elo et les prédictions")
    if parser.parse_args().update:
        payload = run_pipeline()
        sent = send_value_alerts(payload, DATA_DIR)
        if sent:
            logging.info("Alerte Telegram : %d nouvelle(s) occasion(s)", sent)
        try:
            n = send_alerts(payload, DATA_DIR)
            if n:
                logging.info("Alertes Telegram envoyées : %d", n)
        except Exception as e:          # une alerte ne doit jamais bloquer la publication
            logging.warning("Alertes Telegram impossibles : %s", e)
    else:
        parser.print_help()
