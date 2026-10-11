"""Logging ke layar sekaligus ke berkas, satu berkas per run."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def setup_logging(run_id: str, level: int = logging.INFO) -> logging.Logger:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("tk2")
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    file_handler = logging.FileHandler(log_dir / f"{run_id}.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def new_run_id(platform: str) -> str:
    return f"{platform}_{datetime.now():%Y%m%d_%H%M%S}"
