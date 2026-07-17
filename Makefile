applications := load ratios test report dashboard api clean
.DEFAULT_GOAL := help
.PHONY: help $(applications)

PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
STREAMLIT := .venv/bin/streamlit
UVICORN := .venv/bin/uvicorn

help: ## Show this help message
	@echo "Nifty 100 Financial Intelligence Platform — Makefile targets"
	@echo ""
	@echo "  make load       Run ETL: load all 12 source files into nifty100.db (Module 1)"
	@echo "  make ratios     Run Ratio Engine: populate financial_ratios table (Module 2)"
	@echo "  make test       Run full pytest suite, emit HTML report"
	@echo "  make report     Generate all PDF reports: 92 tearsheets + 11 sector + 1 portfolio"
	@echo "  make dashboard  Start Streamlit dashboard on \$$DASHBOARD_PORT"
	@echo "  make api        Start FastAPI/Uvicorn server on \$$PORT"
	@echo "  make clean      Remove .pyc files, __pycache__, and test artifacts (keeps the DB)"

load: ## Idempotent: re-runnable after any source file update
	$(PYTHON) src/etl/loader.py

ratios: ## Run after `make load`; re-run after any KPI formula change
	$(PYTHON) src/analytics/ratios.py

test: ## Must show 0 failures before every commit
	$(PYTEST) tests/ --html=reports/pytest_report.html --self-contained-html

report: ## Sprint 5+: regenerate tearsheets, sector reports, portfolio summary
	$(PYTHON) src/reports/tearsheet.py
	$(PYTHON) src/reports/sector_report.py
	$(PYTHON) src/reports/portfolio_report.py

dashboard: ## Day-to-day analytics work
	$(STREAMLIT) run src/dashboard/app.py --server.port=$${DASHBOARD_PORT:-8501}

api: ## Sprint 6+: required when the dashboard needs live API data
	$(UVICORN) src.api.main:app --host $${API_HOST:-0.0.0.0} --port $${PORT:-8000} --reload

clean: ## Run before packaging final deliverables — never touches data/nifty100.db
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +
	rm -rf .pytest_cache reports/pytest_report.html
