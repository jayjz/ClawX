---
name: architecture
description: Design high-level architecture, diagrams, schemas for ClawdXCraft components.
invoke: auto # Claude auto-loads when architecture/design queried.
---
# Architecture Skill Instructions

Follow lessons.md: Plan first, verify elegance.

1. Read context: bash cat docs/architecture.md if exists.
2. Output: Mermaid diagram, API endpoints list, SQL schema, YAML templates.
3. Ensure bot-centric: Integration with OpenClaw APIs.
4. Think: Scalability for 1000+ bots, real-time via WebSockets.

Example: /architecture Backend API design.
