# AgentOS App Protocol (AAP) v1.0

## Overview

The AgentOS App Protocol lets any app become agent-enabled in 5 minutes.
Add a single `agentos.json` file to your app, and AgentOS agents can
interact with your app through typed actions instead of screen scraping.

## Quick Start

Create `agentos.json` in your app's root:

```json
{
  "app_id": "my-app",
  "name": "My App",
  "version": "1.0",
  "protocol_version": "1.0",
  "actions": [
    {
      "id": "my-app.do_thing",
      "name": "Do Thing",
      "description": "Does the thing",
      "params": [
        {"name": "input", "type": "string", "required": true}
      ],
      "risk_level": "safe",
      "endpoint": "/api/agent/do_thing"
    }
  ],
  "events": ["my-app.thing_done"],
  "auth": {
    "type": "api_key",
    "header": "X-Agent-Key"
  }
}
```

That's it. AgentOS discovers this file and registers your app's actions.

## Action Schema

```json
{
  "id": "app_id.action_name",
  "name": "Human-readable name",
  "description": "What this action does (shown to agents)",
  "params": [
    {
      "name": "param_name",
      "type": "string|number|boolean|enum|date|phone|email|url|contact|currency|location",
      "description": "What this param is for",
      "required": true,
      "default": null,
      "enum_values": ["a", "b"],
      "constraints": {"min": 0, "max": 100}
    }
  ],
  "risk_level": "safe|low|medium|high|critical",
  "returns": "Description of what's returned",
  "endpoint": "/api/agent/action_name",
  "method": "POST",
  "cooldown_seconds": 0,
  "requires_auth": false,
  "tags": ["searchable", "tags"]
}
```

## Risk Levels

| Level | Meaning | Confirmation |
|-------|---------|-------------|
| safe | Read-only, no side effects | None |
| low | Minor side effect (create note) | Show in feed |
| medium | Moderate (send non-urgent msg) | Tap to confirm |
| high | Significant (send money <$100) | Biometric |
| critical | Irreversible (large payment) | Biometric + explicit |

## Event Protocol

Apps can emit events that agents subscribe to:

```json
{
  "event": "my-app.thing_happened",
  "data": {"key": "value"},
  "timestamp": 1234567890
}
```

Events are pushed via WebSocket to the Semantic Bus.

## Authentication

### API Key
```json
{"auth": {"type": "api_key", "header": "X-Agent-Key"}}
```

### OAuth2
```json
{
  "auth": {
    "type": "oauth2",
    "authorize_url": "https://...",
    "token_url": "https://...",
    "scopes": ["read", "write"]
  }
}
```

### Session (cookie-based)
```json
{"auth": {"type": "session", "login_url": "https://..."}}
```

## Data Schemas

Apps can declare shared data formats for interoperability:

```json
{
  "data_schemas": {
    "contact": {
      "name": "string",
      "phone": "string",
      "email": "string"
    },
    "payment": {
      "amount": "number",
      "currency": "string",
      "recipient": "contact"
    }
  }
}
```

This lets agents pass data between apps with zero format conversion.

## Discovery

AgentOS discovers `agentos.json` files:
1. In registered app directories
2. Via URL in config.yaml
3. Via the app marketplace
4. Scanned from installed apps (Android ROM)

## Security

- All agent actions go through the Verification Layer
- High-risk actions require biometric confirmation
- Rate limits enforced per action
- Duplicate detection prevents accidental repeats
- Identity Vault manages credentials (agents never see raw tokens)
