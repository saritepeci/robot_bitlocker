# =============================================================================
# Developer convenience commands.
# =============================================================================
# A Makefile gives every engineer (and the CI pipeline) ONE canonical way to run
# each task. This removes "works on my machine" drift caused by everyone typing
# slightly different `robot` command lines. Run `make help` for the menu.
#
# NOTE for Windows users: install GNU Make (e.g. via Chocolatey `choco install
# make`) or simply copy the commands below — they are plain CLI invocations.
# -----------------------------------------------------------------------------

# Allow `make test ENV=ci` style overrides from the command line.
ENV ?= default
RESULTS_DIR ?= results

# The chosen environment is passed to the framework through the ROBOT_ENVIRONMENT
# OS variable, which both the Robot variable file (via `%{ROBOT_ENVIRONMENT=...}`)
# and the Python Context read. Exporting it here is how one command targets many
# environments without editing a single file.
export ROBOT_ENVIRONMENT := $(ENV)

ROBOT_COMMON = --pythonpath libraries --pythonpath variables \
               --listener libraries/listeners/DiagnosticsListener.py \
               --outputdir $(RESULTS_DIR)

.DEFAULT_GOAL := help

.PHONY: help install install-dev unit test test-ci smoke lint format clean

help:  ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime dependencies.
	pip install -r requirements.txt

install-dev:  ## Install runtime + developer/CI dependencies.
	pip install -r requirements-dev.txt

unit:  ## Run the fast Python unit tests for the state-machine engine.
	python -m unittest discover -s tests_python -v

test:  ## Run the whole Robot test suite against ENV (default: 'default').
	robot $(ROBOT_COMMON) tests

smoke:  ## Run only the fast smoke tests (tag-based selection).
	robot $(ROBOT_COMMON) --include smoke tests

test-ci:  ## Run unit + Robot tests the way CI does (non-zero exit on failure).
	$(MAKE) unit
	robot $(ROBOT_COMMON) --xunit xunit.xml tests

lint:  ## Static-analyse the .robot files (requires install-dev).
	robocop check .

format:  ## Autoformat the .robot files (requires install-dev).
	robocop format .

clean:  ## Remove generated artifacts.
	rm -rf $(RESULTS_DIR) pabot_results .pabotsuitenames output.xml log.html report.html
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
