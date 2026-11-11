# JalRakshak backend tasks. Usage: make install | test | lint | typecheck | check | run | gauges | demo
PY ?= .venv/bin/python

.PHONY: install test lint format typecheck check run gauges facilities train demo

install:
	python3.13 -m venv .venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev,ml]"

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check jalrakshak tests scripts
	$(PY) -m ruff format --check jalrakshak tests scripts

format:
	$(PY) -m ruff format jalrakshak tests scripts
	$(PY) -m ruff check --fix jalrakshak tests scripts

typecheck:
	$(PY) -m mypy jalrakshak

check: lint typecheck test

run:
	$(PY) -m uvicorn jalrakshak.api.main:app --reload --port 8000

gauges:  ## re-derive GloFAS gauge cells + thresholds (network)
	$(PY) scripts/find_gauges.py

facilities:
	$(PY) -m jalrakshak.data.facilities

train:
	$(PY) scripts/train_model.py

demo:  ## rebuild frontend/public/demo/scenario.json (network + Ollama if available)
	$(PY) scripts/build_demo_scenario.py
