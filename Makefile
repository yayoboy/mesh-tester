.PHONY: test run dry-run install

install:
	pip install -e ".[dev]"

test:
	python -m pytest -v

dry-run:
	python main.py --dry-run

run:
	python main.py
