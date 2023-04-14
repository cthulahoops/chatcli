
test:
	poetry run pytest

format:
	poetry run black -l 120 .

coverage:
	poetry run pytest --cov=chatcli_gpt --cov-report html:coverage
