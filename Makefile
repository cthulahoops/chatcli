
test:
	poetry run pytest

format:
	poetry run black -l 120 .

coverage: chatcli_gpt/*.py tests/*.py
	poetry run pytest --cov=chatcli_gpt --cov-report html:coverage
