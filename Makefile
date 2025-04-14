.PHONY: test run

test:
	uv run pytest src/tests

run:
	uv run python src/main.py
