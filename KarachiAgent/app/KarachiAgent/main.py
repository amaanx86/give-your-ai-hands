"""AgentCore entrypoint, deferring to the karachi_agent package."""

from karachi_agent.runtime import app

__all__ = ["app"]

if __name__ == "__main__":
    app.run()
