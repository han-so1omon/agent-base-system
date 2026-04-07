# Base Agent System

Minimal Python scaffold for a base AI agent system.

Live runtime memory uses Graphiti on top of Neo4j. Normal application runs now require valid Neo4j, Postgres, and provider configuration if you want thread memory to persist across restarts.

## Development

Run the smoke tests with:

```bash
pytest tests -q
```
