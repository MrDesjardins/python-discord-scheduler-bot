# PHONY does not check if the file exists or not, it will always run the command
.PHONY: test 
.PHONY: test-coverage
.PHONY: unit-test 
.PHONY: unit-test-coverage-web 
.PHONY: unit-test-coverage 
.PHONY: integration-test 
.PHONY: integration-test-coverage-web
.PHONY: integration-test-coverage
.PHONY: lint
.PHONY: lint-pylint
.PHONY: lint-black
.PHONY: lint-mypy
.PHONY: install-reps
.PHONY: save-deps

test: unit-test integration-test

test-coverage: unit-test-coverage integration-test-coverage

unit-test:
	uv run pytest -v -s ./tests/*_unit_test.py

unit-test-coverage-web:
	uv run coverage run --omit="./tests/*" -m pytest -v -s ./tests/*unit_test.py && uv run coverage html
	explorer.exe `wslpath -w "./htmlcov"`
	# xdg-open ./htmlcov/index.html

unit-test-coverage:
	uv run pytest --cov=deps --cov-report=xml -s ./tests/*unit_test.py

integration-test:
	uv run pytest -v -s ./tests/*_integration_test.py

integration-test-coverage-web:
	uv run coverage run --omit="./tests/*" -m pytest -v -s ./tests/*_integration_test.py && uv run coverage html

integration-test-coverage:
	uv run pytest --cov=deps --cov-report=xml -s ./tests/*_integration_test.py

lint: lint-pylint lint-black lint-mypy

lint-pylint:
	pylint --rcfile=.pylintrc deps/ || true
	pylint --rcfile=.pylintrc cogs/ || true
	pylint --rcfile=.pylintrc ui/ || true
	pylint --rcfile=tests/.pylintrc tests/ || true

lint-black:
	black **/*.py

lint-mypy:
	mypy deps
	mypy cogs
	mypy tests

download-ai-context:
	scp pi@10.0.0.67:/home/pi/python-discord-scheduler-bot/ai_context.txt .