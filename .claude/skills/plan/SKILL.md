---
name: plan
description: Generate or update detailed project plans, roadmaps, and specs for ClawdXCraft. Use for non-trivial tasks (3+ steps).
invoke: user # User invokes with /plan, or auto if planning mentioned.
---
# Plan Skill Instructions

Think step-by-step per claude.md. Read memory.md and lessons.md first.

1. Read project files: Use bash to cat relevant docs (e.g., architecture.md, todo.md).
2. Generate structured plan: Phases, timelines, concrete steps, prompts for sub-tasks.
3. Verify: Ensure alignment with cybersecurity and rush-to-launch goals.
4. Output in markdown with checkable todo items.

Example: /plan Update roadmap for new feature.
