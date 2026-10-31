import argparse
import logging

from src.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NFL AI Predictor")
    parser.add_argument("--update", action="store_true", help="Recalcule les Elo et les prédictions")
    if parser.parse_args().update:
        run_pipeline()
    else:
        parser.print_help()
