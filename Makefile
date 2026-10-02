.PHONY: install test lint sec eval run cli up down certs
install:   ; pip install -r requirements-dev.txt
test:      ; AEGIS_ENV=dev python -m pytest -q --cov=aegis
lint:      ; ruff check src tests eval scripts
sec:       ; bandit -q -r src && pip-audit -r requirements.txt
eval:      ; AEGIS_ENV=dev PYTHONPATH=src python eval/run_eval.py
run:       ; AEGIS_ENV=dev PYTHONPATH=src uvicorn aegis.main:create_app --factory --reload
cli:       ; AEGIS_ENV=dev PYTHONPATH=src python -m aegis.cli
quiz:      ; python scripts/quiz.py
certs:     ; sh scripts/gen_dev_certs.sh
up:        ; docker compose up --build -d
down:      ; docker compose down
