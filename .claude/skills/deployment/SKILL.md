---
name: deployment
description: Generate deployment scripts, Dockerfiles, CI/CD for ClawdXCraft.
invoke: user
---
# Deployment Skill Instructions

Minimal impact per principles.

1. Read config: cat deployment/* .env.
2. Generate: Docker-compose, GitHub Actions YAML, hosting guides (Vercel/Heroku).
3. Scale: Add rate limiting, monitoring (Sentry/Prometheus).
4. Launch steps: Open-source repo setup.

Example: /deployment Dockerize backend.
