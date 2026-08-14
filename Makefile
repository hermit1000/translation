.PHONY: install dev-install lint test

PYTHON ?= python

install:
	$(PYTHON) -m pip install -e .

dev-install:
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m pre_commit install --install-hooks

lint:
	$(PYTHON) -m ruff check .

test:
	$(PYTHON) -m pytest
