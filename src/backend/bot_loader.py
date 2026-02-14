"""YAML-based bot config loader for ClawdXCraft (OpenClaw integration).

Reads a YAML file defining a bot's personality, goals, schedule, and skills,
validates it with Pydantic v2, and returns the config as a dict.

Sample YAML template:

    name: "techbot_01"
    persona: "A tech-savvy bot that posts about AI and programming trends"
    goals:
      - "Post 3 times daily about trending tech topics"
      - "Reply to bots discussing AI"
    reply_probability: 0.5
    auto_follow_count: 2
    memory_window: 5
    schedule:
      interval_seconds: 3600
    skills:
      - name: "post"
        description: "Create original posts"
        params:
          max_length: 280
          hashtag_count: 2
      - name: "reply"
        description: "Reply to posts from followed bots"
"""

from pathlib import Path
import yaml
from pydantic import ValidationError
from models import BotConfig


def load_bot_config(path: str) -> dict:
    """Load and validate a bot YAML config file.

    Args:
        path: Filesystem path to the YAML config file.

    Returns:
        Validated config as a dict.

    Raises:
        ValueError: If the file is missing, unparseable, or fails validation.
    """
    config_path = Path(path)

    if not config_path.is_file():
        raise ValueError(f"Config file not found: {path}")

    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read config file: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML syntax: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping (dict), got: "
                         f"{type(data).__name__}")

    try:
        config = BotConfig(**data)
    except Exception as exc:
        raise ValueError(f"Config validation failed: {exc}") from exc

    return config.model_dump()


# Next: create background task that runs bot loop using this config
