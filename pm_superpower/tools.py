"""PM tool definitions (schemas) and handlers (real API + mock fallback)."""

import json
from datetime import datetime, timedelta

import httpx

# ---------------------------------------------------------------------------
# Tool schemas — used as Claude tool definitions
# ---------------------------------------------------------------------------

_QUERY_SCHEMAS: dict[str, dict] = {
    "linear": {
        "name": "linear_issues",
        "description": "Get issues from Linear project management",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": (
                        "Filter preset: 'my_issues' (assigned to me), "
                        "'in_progress', 'blocked', 'all_open', or a team name"
                    ),
                    "default": "my_issues",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of issues to return",
                    "default": 20,
                },
            },
            "required": [],
        },
    },
    "jira": {
        "name": "jira_issues",
        "description": "Get issues from Jira using a JQL query",
        "input_schema": {
            "type": "object",
            "properties": {
                "jql": {
                    "type": "string",
                    "description": (
                        "JQL query string, e.g. "
                        "'project = PROD AND status = \"In Progress\" AND assignee = currentUser()'"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 20,
                },
            },
            "required": ["jql"],
        },
    },
    "github": {
        "name": "github_activity",
        "description": "Get recent GitHub activity: open PRs, issues, and commits",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/name' format (optional — searches all repos if omitted)",
                },
                "type": {
                    "type": "string",
                    "enum": ["prs", "issues", "commits", "all"],
                    "description": "Type of activity to fetch",
                    "default": "all",
                },
                "days": {
                    "type": "integer",
                    "description": "How many days of history to include",
                    "default": 7,
                },
            },
            "required": [],
        },
    },
    "slack": {
        "name": "slack_search",
        "description": "Search Slack messages across channels",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (supports Slack search modifiers like in:#channel or from:@user)",
                },
                "days": {
                    "type": "integer",
                    "description": "Limit results to the last N days",
                    "default": 7,
                },
            },
            "required": ["query"],
        },
    },
    "calendar": {
        "name": "calendar_events",
        "description": "Get upcoming calendar events",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many days ahead to look",
                    "default": 7,
                },
                "type": {
                    "type": "string",
                    "enum": ["all", "meetings", "deadlines"],
                    "description": "Event type filter",
                    "default": "all",
                },
            },
            "required": [],
        },
    },
    "product_metrics": {
        "name": "get_product_metrics",
        "description": "Get product KPIs and usage metrics (DAU, MAU, conversion, retention, revenue)",
        "input_schema": {
            "type": "object",
            "properties": {
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["dau", "mau", "conversion", "retention", "revenue", "churn", "nps", "all"],
                    },
                    "description": "Which metrics to fetch. Use 'all' for a full dashboard.",
                    "default": ["all"],
                },
                "period": {
                    "type": "string",
                    "enum": ["day", "week", "month", "quarter"],
                    "description": "Time period for the metrics",
                    "default": "week",
                },
                "compare_to": {
                    "type": "string",
                    "enum": ["previous_period", "last_year", "target"],
                    "description": "What to compare against",
                    "default": "previous_period",
                },
            },
            "required": [],
        },
    },
    "sprint_velocity": {
        "name": "get_sprint_velocity",
        "description": "Get engineering team sprint velocity, story points completed, and cycle time",
        "input_schema": {
            "type": "object",
            "properties": {
                "sprints": {
                    "type": "integer",
                    "description": "Number of past sprints to include",
                    "default": 6,
                },
                "team": {
                    "type": "string",
                    "description": "Team name or ID (optional — returns all teams if omitted)",
                },
            },
            "required": [],
        },
    },
}

_ACTION_SCHEMAS: dict[str, dict] = {
    "linear": {
        "name": "create_linear_ticket",
        "description": "Create a new ticket in Linear",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Ticket title"},
                "description": {
                    "type": "string",
                    "description": "Ticket body (markdown supported)",
                },
                "priority": {
                    "type": "integer",
                    "enum": [0, 1, 2, 3, 4],
                    "description": "Priority: 0=none, 1=urgent, 2=high, 3=medium, 4=low",
                    "default": 3,
                },
                "estimate": {
                    "type": "integer",
                    "description": "Story point estimate",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Label names to apply",
                },
            },
            "required": ["title"],
        },
    },
    "jira": {
        "name": "create_jira_ticket",
        "description": "Create a new issue in Jira",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Jira project key (e.g. 'PROD', 'ENG')",
                },
                "summary": {"type": "string", "description": "Issue summary / title"},
                "description": {
                    "type": "string",
                    "description": "Issue description",
                },
                "issue_type": {
                    "type": "string",
                    "enum": ["Story", "Bug", "Task", "Epic"],
                    "description": "Issue type",
                    "default": "Story",
                },
                "priority": {
                    "type": "string",
                    "enum": ["Highest", "High", "Medium", "Low", "Lowest"],
                    "description": "Priority level",
                    "default": "Medium",
                },
            },
            "required": ["project", "summary"],
        },
    },
    "slack": {
        "name": "send_slack_message",
        "description": "Post a message to a Slack channel",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel name without # (e.g. 'product', 'engineering')",
                },
                "message": {
                    "type": "string",
                    "description": "Message text (Slack markdown supported)",
                },
            },
            "required": ["channel", "message"],
        },
    },
    "calendar": {
        "name": "schedule_meeting",
        "description": "Create a calendar event / meeting",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Meeting title"},
                "description": {
                    "type": "string",
                    "description": "Meeting agenda or description",
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format (e.g. '2025-01-15T14:00:00')",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes",
                    "default": 30,
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Attendee email addresses",
                },
            },
            "required": ["title", "start_time"],
        },
    },
}


def get_pm_query_tools(tool_names: list[str]) -> list[dict]:
    """Return tool schemas for querying the given PM tools."""
    return [_QUERY_SCHEMAS[n] for n in tool_names if n in _QUERY_SCHEMAS]


def get_pm_action_tools(tool_names: list[str]) -> list[dict]:
    """Return tool schemas for taking actions in the given PM tools."""
    return [_ACTION_SCHEMAS[n] for n in tool_names if n in _ACTION_SCHEMAS]


# ---------------------------------------------------------------------------
# Query handlers
# ---------------------------------------------------------------------------

def get_pm_metrics_tools(tool_names: list[str]) -> list[dict]:
    """Return tool schemas for the Analyst agent."""
    metrics_keys = {"product_metrics", "sprint_velocity"}
    return [_QUERY_SCHEMAS[n] for n in tool_names if n in metrics_keys and n in _QUERY_SCHEMAS]


def execute_pm_tool(tool_name: str, tool_input: dict, config) -> str:
    """Execute a PM query tool; falls back to mock data if not configured."""
    dispatch = {
        "linear_issues": _linear_issues,
        "jira_issues": _jira_issues,
        "github_activity": _github_activity,
        "slack_search": _slack_search,
        "calendar_events": _calendar_events,
        "get_product_metrics": _get_product_metrics,
        "get_sprint_velocity": _get_sprint_velocity,
    }
    handler = dispatch.get(tool_name)
    if handler is None:
        return f"Unknown tool: {tool_name}"
    return handler(tool_input, config)


def execute_pm_action(tool_name: str, tool_input: dict, config) -> str:
    """Execute a PM action; falls back to demo output if not configured."""
    dispatch = {
        "create_linear_ticket": _create_linear_ticket,
        "create_jira_ticket": _create_jira_ticket,
        "send_slack_message": _send_slack_message,
        "schedule_meeting": _schedule_meeting,
    }
    handler = dispatch.get(tool_name)
    if handler is None:
        return f"Unknown action: {tool_name}"
    return handler(tool_input, config)


# ---------------------------------------------------------------------------
# Linear
# ---------------------------------------------------------------------------

def _linear_issues(params: dict, config) -> str:
    if not config.linear_api_key:
        return _mock_linear(params)

    filter_type = params.get("filter", "my_issues")
    limit = params.get("limit", 20)

    if filter_type == "my_issues":
        query = """
        query { viewer { assignedIssues(first: %d) { nodes {
            title identifier priority
            state { name }
            assignee { name }
            updatedAt url
        } } } }
        """ % limit
    else:
        query = """
        query { issues(first: %d, filter: { state: { name: { neq: "Done" } } }) { nodes {
            title identifier priority
            state { name }
            assignee { name }
            updatedAt url
        } } }
        """ % limit

    try:
        resp = httpx.post(
            "https://api.linear.app/graphql",
            headers={"Authorization": config.linear_api_key, "Content-Type": "application/json"},
            json={"query": query},
            timeout=10,
        )
        data = resp.json()
        if "errors" in data:
            return f"Linear error: {data['errors']}\n\n{_mock_linear(params)}"

        if filter_type == "my_issues":
            issues = data["data"]["viewer"]["assignedIssues"]["nodes"]
        else:
            issues = data["data"]["issues"]["nodes"]

        if not issues:
            return "No issues found in Linear."

        priority_label = {0: "–", 1: "🔴 Urgent", 2: "🟠 High", 3: "🟡 Medium", 4: "🟢 Low"}
        lines = [f"**Linear issues ({len(issues)}):**\n"]
        for i in issues:
            p = priority_label.get(i.get("priority", 0), "–")
            s = i.get("state", {}).get("name", "?")
            a = (i.get("assignee") or {}).get("name", "Unassigned")
            lines.append(f"- [{i['identifier']}] {i['title']}")
            lines.append(f"  Status: {s} | Priority: {p} | Assignee: {a}")
            lines.append(f"  {i.get('url', '')}\n")
        return "\n".join(lines)

    except Exception as exc:
        return f"Error querying Linear: {exc}\n\n{_mock_linear(params)}"


def _mock_linear(params: dict) -> str:
    issues = [
        {"id": "ENG-123", "title": "Implement OAuth2 login flow", "status": "In Progress", "priority": "🟠 High", "assignee": "Alice"},
        {"id": "ENG-124", "title": "Fix dashboard slow load (>5s on large orgs)", "status": "In Progress", "priority": "🟡 Medium", "assignee": "Bob"},
        {"id": "ENG-125", "title": "Add export to CSV for reports", "status": "Todo", "priority": "🟢 Low", "assignee": "Carol"},
        {"id": "ENG-126", "title": "API rate limiting broken for enterprise tier", "status": "In Progress", "priority": "🔴 Urgent", "assignee": "Alice"},
        {"id": "PM-45", "title": "Q3 roadmap finalization", "status": "In Progress", "priority": "🟠 High", "assignee": "You"},
    ]
    lines = ["[Demo] **Linear issues (5):**\n"]
    for i in issues:
        lines.append(f"- [{i['id']}] {i['title']}")
        lines.append(f"  Status: {i['status']} | Priority: {i['priority']} | Assignee: {i['assignee']}\n")
    return "\n".join(lines)


def _create_linear_ticket(params: dict, config) -> str:
    if not config.linear_api_key:
        return (
            f"[Demo] Would create Linear ticket: **{params['title']}**\n"
            f"Priority: {params.get('priority', 3)} | Estimate: {params.get('estimate', '–')} pts\n"
            "→ Add LINEAR_API_KEY to .env to create real tickets."
        )

    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            success
            issue { id identifier title url }
        }
    }
    """
    variables = {
        "input": {
            "title": params["title"],
            "description": params.get("description", ""),
            "priority": params.get("priority", 3),
        }
    }
    try:
        resp = httpx.post(
            "https://api.linear.app/graphql",
            headers={"Authorization": config.linear_api_key, "Content-Type": "application/json"},
            json={"query": mutation, "variables": variables},
            timeout=10,
        )
        data = resp.json()
        if "errors" in data:
            return f"Failed to create Linear ticket: {data['errors']}"
        issue = data["data"]["issueCreate"]["issue"]
        return f"✅ Created [{issue['identifier']}]: {issue['title']}\n{issue['url']}"
    except Exception as exc:
        return f"Error creating Linear ticket: {exc}"


# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------

def _jira_issues(params: dict, config) -> str:
    if not (config.jira_base_url and config.jira_email and config.jira_api_token):
        return _mock_jira(params)

    jql = params.get("jql", "assignee = currentUser() AND status != Done ORDER BY updated DESC")
    limit = params.get("limit", 20)

    try:
        import base64
        creds = base64.b64encode(f"{config.jira_email}:{config.jira_api_token}".encode()).decode()
        resp = httpx.get(
            f"{config.jira_base_url}/rest/api/3/search",
            headers={"Authorization": f"Basic {creds}", "Content-Type": "application/json"},
            params={"jql": jql, "maxResults": limit, "fields": "summary,status,priority,assignee,updated"},
            timeout=10,
        )
        if resp.status_code != 200:
            return f"Jira error {resp.status_code}\n\n{_mock_jira(params)}"

        issues = resp.json().get("issues", [])
        if not issues:
            return "No Jira issues found for that query."

        lines = [f"**Jira issues ({len(issues)}):**\n"]
        for i in issues:
            f = i.get("fields", {})
            status = f.get("status", {}).get("name", "?")
            priority = f.get("priority", {}).get("name", "?")
            assignee = (f.get("assignee") or {}).get("displayName", "Unassigned")
            lines.append(f"- [{i['key']}] {f.get('summary', '(no title)')}")
            lines.append(f"  Status: {status} | Priority: {priority} | Assignee: {assignee}\n")
        return "\n".join(lines)

    except Exception as exc:
        return f"Error querying Jira: {exc}\n\n{_mock_jira(params)}"


def _mock_jira(params: dict) -> str:
    issues = [
        {"key": "PROD-567", "summary": "User onboarding flow redesign", "status": "In Progress", "priority": "High"},
        {"key": "PROD-568", "summary": "Payment gateway integration (Stripe v3)", "status": "In Review", "priority": "Critical"},
        {"key": "PROD-569", "summary": "API v2 documentation update", "status": "Todo", "priority": "Medium"},
        {"key": "BUG-234", "summary": "SSO login fails intermittently on mobile Safari", "status": "In Progress", "priority": "Critical"},
    ]
    lines = ["[Demo] **Jira issues (4):**\n"]
    for i in issues:
        lines.append(f"- [{i['key']}] {i['summary']}")
        lines.append(f"  Status: {i['status']} | Priority: {i['priority']}\n")
    return "\n".join(lines)


def _create_jira_ticket(params: dict, config) -> str:
    if not (config.jira_base_url and config.jira_email and config.jira_api_token):
        return (
            f"[Demo] Would create Jira {params.get('issue_type', 'Story')} in "
            f"project {params.get('project', 'PROJ')}: **{params['summary']}**\n"
            "→ Add JIRA_* env vars to .env to create real tickets."
        )

    import base64
    creds = base64.b64encode(f"{config.jira_email}:{config.jira_api_token}".encode()).decode()
    payload = {
        "fields": {
            "project": {"key": params["project"]},
            "summary": params["summary"],
            "issuetype": {"name": params.get("issue_type", "Story")},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": params.get("description", "")}]}],
            },
        }
    }
    if params.get("priority"):
        payload["fields"]["priority"] = {"name": params["priority"]}

    try:
        resp = httpx.post(
            f"{config.jira_base_url}/rest/api/3/issue",
            headers={"Authorization": f"Basic {creds}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        if resp.status_code == 201:
            key = resp.json()["key"]
            return f"✅ Created [{key}]: {params['summary']}\n{config.jira_base_url}/browse/{key}"
        return f"Failed to create Jira ticket: {resp.status_code} — {resp.text}"
    except Exception as exc:
        return f"Error creating Jira ticket: {exc}"


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

def _github_activity(params: dict, config) -> str:
    if not config.github_token:
        return _mock_github(params)

    activity_type = params.get("type", "all")
    days = params.get("days", 7)
    repo = params.get("repo")
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    headers = {
        "Authorization": f"Bearer {config.github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    lines = []
    try:
        if activity_type in ("prs", "all"):
            if repo:
                resp = httpx.get(f"https://api.github.com/repos/{repo}/pulls",
                                 headers=headers, params={"state": "open", "per_page": 10}, timeout=10)
                prs = resp.json() if resp.status_code == 200 else []
            else:
                resp = httpx.get("https://api.github.com/search/issues", headers=headers,
                                 params={"q": f"is:pr is:open updated:>={since}", "per_page": 10}, timeout=10)
                prs = resp.json().get("items", []) if resp.status_code == 200 else []
            if prs:
                lines.append(f"**Open PRs ({len(prs)}):**")
                for pr in prs[:8]:
                    lines.append(f"- #{pr.get('number')} {pr.get('title')} — @{pr.get('user', {}).get('login', '?')}")

        if activity_type in ("issues", "all"):
            if repo:
                resp = httpx.get(f"https://api.github.com/repos/{repo}/issues",
                                 headers=headers, params={"state": "open", "per_page": 8, "since": since + "T00:00:00Z"}, timeout=10)
                issues = [i for i in (resp.json() if resp.status_code == 200 else []) if "pull_request" not in i]
            else:
                resp = httpx.get("https://api.github.com/search/issues", headers=headers,
                                 params={"q": f"is:issue is:open updated:>={since}", "per_page": 8}, timeout=10)
                issues = resp.json().get("items", []) if resp.status_code == 200 else []
            if issues:
                lines.append(f"\n**Open Issues ({len(issues)}):**")
                for i in issues[:8]:
                    lines.append(f"- #{i.get('number')} {i.get('title')} — @{i.get('user', {}).get('login', '?')}")

        return "\n".join(lines) if lines else "No recent GitHub activity found."

    except Exception as exc:
        return f"Error querying GitHub: {exc}\n\n{_mock_github(params)}"


def _mock_github(params: dict) -> str:
    lines = ["[Demo] **Recent GitHub Activity:**\n"]
    lines.append("**Open PRs (3):**")
    lines.append("- #892 feat: Add dark mode support — @alice (Review requested)")
    lines.append("- #893 fix: Resolve auth token expiry bug — @bob (Approved, ready to merge)")
    lines.append("- #894 chore: Upgrade Next.js to 15 — @carol (Draft)\n")
    lines.append("**Open Issues (2):**")
    lines.append("- #340 Mobile: keyboard covers input fields on iOS — @dave (P1)")
    lines.append("- #341 CSV export fails for datasets >10k rows — @alice (P2)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

def _slack_search(params: dict, config) -> str:
    if not config.slack_bot_token:
        return _mock_slack(params)

    query = params["query"]
    try:
        resp = httpx.get(
            "https://slack.com/api/search.messages",
            headers={"Authorization": f"Bearer {config.slack_bot_token}"},
            params={"query": query, "count": 10, "sort": "timestamp"},
            timeout=10,
        )
        data = resp.json()
        if not data.get("ok"):
            return f"Slack error: {data.get('error')}\n\n{_mock_slack(params)}"

        messages = data.get("messages", {}).get("matches", [])
        if not messages:
            return f"No Slack messages found for '{query}'."

        lines = [f"**Slack messages for '{query}' ({len(messages)}):**\n"]
        for m in messages[:6]:
            channel = m.get("channel", {}).get("name", "?")
            user = m.get("username", "?")
            text = (m.get("text") or "")[:200]
            lines.append(f"**#{channel}** @{user}:")
            lines.append(f"{text}\n")
        return "\n".join(lines)

    except Exception as exc:
        return f"Error searching Slack: {exc}\n\n{_mock_slack(params)}"


def _mock_slack(params: dict) -> str:
    query = params.get("query", "")
    lines = [f"[Demo] **Slack messages mentioning '{query}':**\n"]
    lines.append("**#engineering** @alice:")
    lines.append(f"Just pushed the fix for {query}. Can someone review PR #893? It's blocking the release.\n")
    lines.append("**#product** @carol:")
    lines.append(f"The {query} issue is impacting 3 enterprise customers. We should bump it to P1.\n")
    lines.append("**#standup** @bob:")
    lines.append(f"Yesterday: investigated {query}. Today: writing the fix. Blockers: need design sign-off on the empty state.\n")
    return "\n".join(lines)


def _send_slack_message(params: dict, config) -> str:
    if not config.slack_bot_token:
        return (
            f"[Demo] Would send to **#{params['channel']}**:\n\n"
            f"{params['message']}\n\n"
            "→ Add SLACK_BOT_TOKEN to .env to send real messages."
        )

    try:
        resp = httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {config.slack_bot_token}", "Content-Type": "application/json"},
            json={"channel": params["channel"], "text": params["message"]},
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            return f"✅ Message sent to #{params['channel']}"
        return f"Failed to send message: {data.get('error', 'unknown error')}"
    except Exception as exc:
        return f"Error sending Slack message: {exc}"


# ---------------------------------------------------------------------------
# Calendar (demo only — Google Calendar requires OAuth2 setup)
# ---------------------------------------------------------------------------

def _calendar_events(params: dict, config) -> str:
    days = params.get("days", 7)
    today = datetime.now()
    events = [
        {"title": "Product Standup", "when": "Tomorrow 9:30 AM", "duration": "30 min", "with": "Full product team"},
        {"title": "Engineering Sync", "when": "Tomorrow 2:00 PM", "duration": "1 hour", "with": "Engineering leads"},
        {"title": "Q3 Roadmap Review", "when": f"{(today + timedelta(days=2)).strftime('%A')} 10:00 AM", "duration": "2 hours", "with": "PM team + VP Product"},
        {"title": "Customer Interview: Acme Corp", "when": f"{(today + timedelta(days=3)).strftime('%A')} 3:00 PM", "duration": "45 min", "with": "carol@acme.com"},
        {"title": "Sprint Planning", "when": f"{(today + timedelta(days=4)).strftime('%A')} 9:00 AM", "duration": "2 hours", "with": "Engineering team"},
    ]
    lines = [f"**Upcoming calendar events (next {days} days):**\n"]
    for e in events:
        lines.append(f"📅 **{e['title']}**")
        lines.append(f"   {e['when']} ({e['duration']}) — with {e['with']}\n")
    return "\n".join(lines)


def _schedule_meeting(params: dict, config) -> str:
    attendees = ", ".join(params.get("attendees", [])) or "No attendees specified"
    return (
        f"[Demo] Would schedule:\n"
        f"📅 **{params['title']}**\n"
        f"   Time: {params['start_time']} ({params.get('duration_minutes', 30)} min)\n"
        f"   Attendees: {attendees}\n\n"
        "→ Configure Google Calendar credentials to schedule real meetings."
    )


# ---------------------------------------------------------------------------
# Product Metrics (demo — wire up to your analytics backend)
# ---------------------------------------------------------------------------

def _get_product_metrics(params: dict, config) -> str:
    requested = params.get("metrics", ["all"])
    period = params.get("period", "week")
    compare_to = params.get("compare_to", "previous_period")

    all_metrics = {
        "dau": {"name": "Daily Active Users", "value": "24,831", "prev": "22,104", "change": "+12.3%", "target": "25,000", "vs_target": "-0.7%"},
        "mau": {"name": "Monthly Active Users", "value": "187,420", "prev": "179,200", "change": "+4.6%", "target": "200,000", "vs_target": "-6.3%"},
        "conversion": {"name": "Free → Paid Conversion", "value": "4.2%", "prev": "4.8%", "change": "-12.5%", "target": "5.0%", "vs_target": "-16.0%"},
        "retention": {"name": "30-Day Retention", "value": "68.4%", "prev": "71.2%", "change": "-3.9%", "target": "70.0%", "vs_target": "-2.3%"},
        "revenue": {"name": "MRR", "value": "$284,500", "prev": "$261,300", "change": "+8.9%", "target": "$300,000", "vs_target": "-5.2%"},
        "churn": {"name": "Monthly Churn Rate", "value": "2.8%", "prev": "2.3%", "change": "+21.7%", "target": "2.0%", "vs_target": "+40.0%"},
        "nps": {"name": "NPS Score", "value": "42", "prev": "38", "change": "+10.5%", "target": "50", "vs_target": "-16.0%"},
    }

    show_all = "all" in requested
    metrics_to_show = all_metrics if show_all else {k: v for k, v in all_metrics.items() if k in requested}

    lines = [f"[Demo] **Product Metrics — Last {period.capitalize()} vs {compare_to.replace('_', ' ').title()}**\n"]
    lines.append(f"| Metric | Current | {'vs ' + compare_to.replace('_', ' ').title()} | Target | vs Target |")
    lines.append("|--------|---------|------------|--------|-----------|")
    for m in metrics_to_show.values():
        change_icon = "🟢" if m["change"].startswith("+") and m["name"] != "Monthly Churn Rate" else "🔴"
        if m["name"] == "Monthly Churn Rate":
            change_icon = "🔴" if m["change"].startswith("+") else "🟢"
        lines.append(
            f"| {m['name']} | **{m['value']}** | {change_icon} {m['change']} | {m['target']} | {m['vs_target']} |"
        )

    lines.append("\n**Key signals:**")
    lines.append("- 🔴 Conversion dropped 12.5% WoW — checkout funnel analysis needed")
    lines.append("- 🔴 Churn spiked 21.7% — enterprise segment most affected (check Slack #customer-success)")
    lines.append("- 🟢 DAU near target, driven by new onboarding flow shipped Monday")
    lines.append("- 🟢 MRR growing 8.9% but conversion drag will slow this by Q3 if not addressed")

    return "\n".join(lines)


def _get_sprint_velocity(params: dict, config) -> str:
    num_sprints = params.get("sprints", 6)
    team = params.get("team", "all teams")

    sprints = [
        {"name": "Sprint 42", "points": 47, "completed": 44, "cycle_time": 3.2},
        {"name": "Sprint 43", "points": 52, "completed": 49, "cycle_time": 2.9},
        {"name": "Sprint 44", "points": 50, "completed": 38, "cycle_time": 4.1},
        {"name": "Sprint 45", "points": 48, "completed": 47, "cycle_time": 3.0},
        {"name": "Sprint 46", "points": 55, "completed": 53, "cycle_time": 2.7},
        {"name": "Sprint 47 (current)", "points": 51, "completed": 31, "cycle_time": 2.8},
    ]

    sprints = sprints[-num_sprints:]
    completed = [s["completed"] for s in sprints if "current" not in s["name"]]
    avg_velocity = sum(completed) / len(completed) if completed else 0

    lines = [f"[Demo] **Sprint Velocity — {team.title()} (last {num_sprints} sprints)**\n"]
    lines.append("| Sprint | Planned | Completed | Hit Rate | Avg Cycle Time |")
    lines.append("|--------|---------|-----------|----------|----------------|")
    for s in sprints:
        hit_rate = f"{s['completed'] / s['points'] * 100:.0f}%"
        icon = "🟢" if s["completed"] / s["points"] >= 0.9 else "🟡" if s["completed"] / s["points"] >= 0.75 else "🔴"
        lines.append(
            f"| {s['name']} | {s['points']} pts | {s['completed']} pts | {icon} {hit_rate} | {s['cycle_time']}d |"
        )

    lines.append(f"\n**Average velocity (last {len(completed)} completed sprints):** {avg_velocity:.0f} pts/sprint")
    lines.append("**Trend:** Velocity recovering after Sprint 44 dip (caused by infra incident + 2 engineers OOO)")
    lines.append("**Cycle time:** Improving — down from 4.1d to 2.8d after introducing async code reviews")

    return "\n".join(lines)
