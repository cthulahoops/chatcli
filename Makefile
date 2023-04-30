
test:
	poetry run pytest

format:
	poetry run black .

coverage: chatcli_gpt/*.py tests/*.py
	poetry run pytest --cov=chatcli_gpt --cov-report html:.coverage_report
