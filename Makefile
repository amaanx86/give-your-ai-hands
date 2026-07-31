.DEFAULT_GOAL := help
.PHONY: help install fmt lint types check run repl tools serve package deploy dry-run invoke logs clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies, including the AgentCore runtime extra
	uv sync --extra runtime

fmt: ## Format and autofix
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Lint without fixing
	uv run ruff check .
	uv run ruff format --check .

types: ## Type check
	uv run mypy src

check: lint types ## Lint and type check

run: ## Ask one question, e.g. make run Q="when is Maghrib?"
	uv run karachi-agent --trace "$(Q)"

repl: ## Interactive session
	uv run karachi-agent

tools: ## Print the tool schemas Strands generated from the Python
	uv run karachi-agent --show-tools

serve: ## Serve the AgentCore contract locally on port 8080
	uv run python -m karachi_agent.runtime

package: ## Vendor karachi_agent into the AgentCore app directory
	rm -rf KarachiAgent/app/KarachiAgent/karachi_agent
	cp -R src/karachi_agent KarachiAgent/app/KarachiAgent/karachi_agent
	find KarachiAgent/app/KarachiAgent/karachi_agent -name __pycache__ -type d -prune -exec rm -rf {} +

deploy: package ## Deploy to AgentCore Runtime
	cd KarachiAgent && bunx @aws/agentcore deploy

dry-run: package ## Preview the deployment without changing anything
	cd KarachiAgent && bunx @aws/agentcore deploy --dry-run

invoke: ## Invoke the deployed agent, e.g. make invoke Q="when is Maghrib?"
	cd KarachiAgent && bunx @aws/agentcore invoke --stream "$(Q)"

logs: ## Stream logs from the deployed agent
	cd KarachiAgent && bunx @aws/agentcore logs

clean: ## Remove caches and build artifacts
	rm -rf .ruff_cache .mypy_cache dist build cdk.out
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
