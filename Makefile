PY      ?= python3
export PYTHONPATH := src
DATA    ?= data/raw/cookie_cats.csv
PROV    ?= synthetic

.PHONY: help setup data run test lint verify dbt-build readme readme-check clean

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

setup: ## create .venv and install everything
	$(PY) -m venv .venv
	.venv/bin/pip install -r requirements.txt

data: ## generate the labelled synthetic dataset (skip if you placed the real CSV)
	$(PY) -m abtest.cli generate --out $(DATA) --seed 42

run: ## validate -> analyse -> charts, HTML report, decision memo
	$(PY) -m abtest.cli analyze --input $(DATA) --provenance $(PROV) --out-dir reports --img-dir docs/img

test: ## unit tests (stdlib unittest, no extra install)
	$(PY) -m unittest discover -s tests -v

lint: ## static analysis
	ruff check src tests scripts

dbt-build: ## load DuckDB, then run dbt models + tests (needs requirements.txt installed)
	$(PY) scripts/load_duckdb.py --csv $(DATA)
	cd dbt_project && dbt build --profiles-dir .

readme: ## regenerate the results block in README.md from reports/results.json
	$(PY) -m abtest.cli sync-readme

readme-check: ## fail if the README results block is stale
	$(PY) -m abtest.cli sync-readme --check

verify: lint test readme-check ## everything CI runs that needs no warehouse

clean:
	rm -rf warehouse dbt_project/target dbt_project/logs .ruff_cache
