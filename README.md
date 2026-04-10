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
| **Orchestrator** | Plans, delegates, synthesizes | `research`, `write`, `execute` (delegates to sub-agents) |
| **Researcher** | Gathers data from PM tools | Linear, Jira, GitHub, Slack, Calendar |
| **Writer** | Produces polished PM artifacts | None — pure generation from context |
| **Executor** | Takes actions in PM tools | Linear, Jira, Slack, Calendar (write operations) |

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
| `pm chat` | Alias for interactive mode |
| `pm examples` | Show example commands |

### Ticket command options

```bash
pm ticket "Add dark mode to dashboard" --tool linear   # Create in Linear
pm ticket "Fix login bug" --tool jira                  # Create in Jira
```

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
├── setup.py                   # Package config + CLI entry point
├── requirements.txt
├── .env.example               # Environment template
└── pm_superpower/
    ├── __init__.py
    ├── cli.py                 # Click CLI + Rich UI
    ├── team.py                # Agent team orchestration
    ├── config.py              # Configuration from environment
    ├── prompts.py             # System prompts for each agent
    └── tools.py               # PM tool schemas + API handlers
```
