# Perintah pendek untuk pekerjaan yang sering diulang.
# Jalankan `make` tanpa argumen untuk melihat daftarnya.

.DEFAULT_GOAL := help
PYTHON := python3
VENV := .venv
BIN := $(VENV)/bin

help:  ## Tampilkan daftar perintah
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup:  ## Buat virtualenv dan pasang dependensi
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e .
	@test -f .env || cp .env.example .env
	@echo "Selesai. Isi .env lalu jalankan: make smoke"

lock:  ## Kunci versi persis yang sedang terpasang ke requirements.lock.txt
	$(BIN)/pip freeze --exclude-editable > requirements.lock.txt
	@echo "requirements.lock.txt diperbarui. Commit berkas ini."

smoke:  ## Uji konfigurasi tanpa mengambil data sungguhan
	$(BIN)/python -m src.run_scrape --platform x --limit 1 --dry-run

scrape-x:  ## Jalankan scraping X
	$(BIN)/python -m src.run_scrape --platform x

scrape-tiktok:  ## Jalankan scraping TikTok
	$(BIN)/python -m src.run_scrape --platform tiktok

scrape-instagram:  ## Jalankan scraping Instagram
	$(BIN)/python -m src.run_scrape --platform instagram

stats:  ## Rekap jumlah record per run (bahan C4/C5)
	$(BIN)/python -m src.summarize_runs

clean:  ## Hapus cache Python dan log
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf logs/*.log

.PHONY: help setup lock smoke scrape-x scrape-tiktok scrape-instagram stats clean
