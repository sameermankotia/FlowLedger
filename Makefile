# Convenience targets. Everything here is also documented in the README.
VENV := .venv
PY   := $(VENV)/bin/python

.PHONY: help setup up down data pipeline dry-run reports dashboard site test reset demo all clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## create the virtualenv and install dependencies
	python3 -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.txt

up: ## start PostgreSQL and wait for it to accept connections
	docker compose up -d
	@for i in $$(seq 1 40); do \
	  docker compose exec -T postgres pg_isready -U $${POSTGRES_USER:-erp} >/dev/null 2>&1 && \
	    echo "postgres ready" && exit 0; \
	  sleep 1; \
	done; echo "postgres did not become ready" >&2; exit 1

down: ## stop PostgreSQL (keeps the data volume)
	docker compose down

data: ## regenerate the synthetic source extracts
	$(PY) scripts/generate_data.py

pipeline: ## run the ETL pipeline
	$(PY) -m src.pipeline

dry-run: ## validate the extracts without writing to the database
	$(PY) -m src.pipeline --dry-run

reports: ## print every SQL report
	$(PY) -m src.reports

dashboard: ## open the Streamlit dashboard at http://localhost:8501
	$(VENV)/bin/streamlit run src/dashboard.py

site: ## build the static GitHub Pages snapshot into docs/
	$(PY) scripts/build_site.py

test: ## run the test suite
	$(PY) -m pytest

reset: ## drop all loaded data and run history
	docker compose exec -T postgres psql -U $${POSTGRES_USER:-erp} -d $${POSTGRES_DB:-erp} \
	  -c "TRUNCATE load_audit, rejected_records, pipeline_runs, invoices, projects, customers RESTART IDENTITY CASCADE;"

demo: up pipeline reports ## start the database, load the data, print the reports

all: up pipeline dashboard ## load the data and open the dashboard

clean: ## remove the virtualenv, caches and the database volume
	docker compose down -v
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
