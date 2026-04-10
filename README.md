# PM Superpower

AI-powered PM assistant built with **Claude Agent Teams** — a team of specialized Claude agents that help product managers with daily tasks like standup generation, ticket writing, and status updates.

## Architecture

```
User Request
     │
     ▼
┌─────────────────────────────┐
│   Orchestrator (Opus 4.6)   │  ← Adaptive thinking ON
│   Decides which agents to   │
│   call and synthesizes      │
│   the final response        │
└──────┬──────────┬───────────┘
       │          │           │
       ▼          ▼           ▼
┌──────────┐ ┌──────────┐ ┌───────────┐
│Researcher│ │  Writer  │ │ Executor  │
│+ PM tools│ │ (no tools│ │+ action   │
│ (read)   │ │ pure gen)│ │   tools   │
└──────────┘ └──────────┘ └───────────┘
```

Each sub-agent is a separate Claude API call with a specialized system prompt and targeted tool set. The orchestrator uses [adaptive thinking](https://docs.anthropic.com/en/docs/about-claude/models/claude-opus-4) to decide which agents to invoke, then synthesizes their outputs into a polished response.

### Agent Roles

| Agent | Responsibility | Tools |
|---|---|---|
| **Orchestrator** | Plans, delegates, synthesizes | `research`, `analyze`, `write`, `execute` (delegates to sub-agents) |
| **Researcher** | Gathers data from PM tools | Linear, Jira, GitHub, Slack, Calendar |
| **Analyst** | Analyses metrics, surfaces trends, spots anomalies | Product metrics, Sprint velocity |
| **Writer** | Produces polished PM artifacts | None — pure generation from context |
| **Executor** | Takes actions in PM tools | Linear, Jira, Slack, Calendar (write operations) |

## Use in Claude.ai Chat (MCP)

PM Superpower can run as an **MCP server**, making all its tools available directly inside Claude.ai or Claude Code — no terminal needed.

### 1. Install with MCP support

```bash
pip install -e ".[mcp]"
```

### 2. Add to Claude's MCP config

**Claude Code** (`~/.claude/settings.json` or `.claude/settings.json`):
```json
{
  "mcpServers": {
    "pm-superpower": {
      "command": "pm-mcp",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "LINEAR_API_KEY": "lin_api_...",
        "SLACK_BOT_TOKEN": "xoxb-..."
      }
    }
  }
}
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):
```json
{
  "mcpServers": {
    "pm-superpower": {
      "command": "pm-mcp",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

### 3. Use in chat

After restarting Claude, type naturally:

> "Generate my standup"
> "Write a ticket for the SSO login bug"
> "How is conversion trending this week?"
> "Give me a status update for the mobile launch"

Claude will call the PM Superpower tools automatically. The full agent team (Researcher, Analyst, Writer, Executor) runs under the hood.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/juliascherer-cloud/pm-superpower.git
cd pm-superpower
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY (required)
# Add optional PM tool API keys for real data
```

### 3. Run

```bash
# Interactive chat session
pm

# One-shot commands
pm standup
pm ticket "Auth fails for SSO users on mobile"
pm status "Q3 mobile launch"
pm ask "What's blocking the payments team?"

# Or with python directly
python main.py
```

## Commands

| Command | Description |
|---|---|
| `pm` | Start interactive chat session |
| `pm ask "<question>"` | Ask the PM team anything |
| `pm standup` | Generate today's standup update |
| `pm ticket "<description>"` | Write a production-ready ticket |
| `pm status "<project>"` | Generate a project status update |
| `pm ask "How is conversion trending?"` | Analyse metrics via Analyst agent |
| `pm chat` | Alias for interactive mode |
| `pm examples` | Show example commands |

### Ticket command options

```bash
pm ticket "Add dark mode to dashboard" --tool linear   # Create in Linear
pm ticket "Fix login bug" --tool jira                  # Create in Jira
```

## Metrics Analysis

Ask the Analyst agent about any product or engineering metric:

```bash
pm ask "How is our conversion rate trending this month?"
pm ask "What's the team's sprint velocity over the last 6 sprints?"
pm ask "Why might churn be increasing? What do the numbers show?"
pm ask "Give me a full product metrics dashboard"
```

The Analyst pulls `product_metrics` (DAU, MAU, conversion, retention, MRR, churn, NPS) and `sprint_velocity` data, calculates WoW/MoM trends, spots anomalies, and returns a data table with actionable insights.

To connect your real analytics backend, replace the mock handlers in `tools.py` (`_get_product_metrics`, `_get_sprint_velocity`) with calls to your own data warehouse, Amplitude, Mixpanel, or similar.

---

## PM Tool Integrations

The app works in **demo mode** without any API keys — it generates realistic mock data. Add keys to `.env` to connect real tools:

| Tool | Environment Variable(s) | What it does |
|---|---|---|
| **Linear** | `LINEAR_API_KEY` | Query issues, projects, teams; create tickets |
| **Jira** | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | Query issues, sprints; create tickets |
| **GitHub** | `GITHUB_TOKEN` | Query PRs, issues, commits |
| **Slack** | `SLACK_BOT_TOKEN` | Search messages; send messages |
| **Google Calendar** | *(stub — no key needed)* | Query upcoming events |

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional — enables real data from PM tools
LINEAR_API_KEY=lin_api_...
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=...
SLACK_BOT_TOKEN=xoxb-...
GITHUB_TOKEN=ghp_...
```

## How It Works

### Orchestrator Loop (up to 12 turns)

The orchestrator runs a standard Claude agentic loop with three tools: `research`, `write`, and `execute`. Each tool call delegates to a specialized sub-agent:

```python
response = client.messages.create(
    model="claude-opus-4-6",
    thinking={"type": "adaptive"},   # Orchestrator thinks before acting
    tools=ORCHESTRATOR_TOOLS,        # research, write, execute
    messages=messages,
)
```

### Researcher Sub-Agent (up to 6 turns)

The researcher runs its own agentic loop with PM query tools, gathering data across Linear, Jira, GitHub, Slack, and Calendar before returning a summary.

### Writer Sub-Agent (single call)

The writer receives the task and all research context, then produces a polished artifact (ticket, PRD, status update, meeting notes, etc.) in a single call. No tools needed — the context is pre-loaded.

### Executor Sub-Agent (up to 6 turns)

The executor runs an agentic loop with PM write tools, executing the requested action (create ticket, send message, schedule meeting) and confirming completion.

## Development

```bash
# Install in editable mode with dev tools
pip install -e ".[dev]"

# Run directly
python main.py

# Run a specific command
python -m pm_superpower.cli standup
```

## Project Structure

```
pm-superpower/
├── main.py                    # Entry point
├── setup.py                   # Package config + CLI entry points
├── requirements.txt
├── .env.example               # Environment template
└── pm_superpower/
    ├── __init__.py
    ├── cli.py                 # Click CLI + Rich UI
    ├── mcp_server.py          # MCP server (for Claude.ai / Claude Code)
    ├── team.py                # Agent team orchestration
    ├── config.py              # Configuration from environment
    ├── prompts.py             # System prompts for each agent
    └── tools.py               # PM tool schemas + API handlers
```
