# PHONY does not check if the file exists or not, it will always run the command
.PHONY: all test unit-test integration-test unit-test-coverage integration-test-coverage lint lint-pylint lint-black lint-mypy

all: test

test: unit-test integration-test

test-coverage: unit-test-coverage integration-test-coverageF

unit-test:
	pytest -v -s ./tests/*_unit_test.py

unit-test-coverage:
	coverage run --omit="./tests/*" -m pytest -v -s ./tests/*unit_test.py && coverage html

integration-test:
	pytest -v -s ./tests/*_integration_test.py

integration-test-coverage:
	coverage run --omit="./tests/*" -m pytest -v -s ./tests/*_integration_test.py && coverage html

lint: lint-pylint lint-black lint-mypy

lint-pylint:
	pylint **/*.py

lint-black:
	black **/*.py

lint-mypy:
	mypy deps
	mypy cogs
	mypy tests
