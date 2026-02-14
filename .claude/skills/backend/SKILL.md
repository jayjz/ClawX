---
name: backend
description: Generate complete backend code for ClawdXCraft using FastAPI, including models, endpoints, DB integration.
invoke: user
---
# Backend Skill Instructions

Per claude.md: Complete code, no placeholders. Read memory.md for prior outputs.

1. Read specs: cat src/backend/* if relevant.
2. Generate: Pydantic models, endpoints (e.g., /posts/create), auth, WebSockets.
3. Integrate: Redis for real-time, OpenClaw hooks.
4. Test snippet: Include pytest example.

Example: /backend Implement posting endpoint.
