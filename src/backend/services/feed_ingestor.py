"""
feed_ingestor.py — Async-native data ingestor for multi-modal markets.

Uses httpx for ALL external I/O (no sync libraries).
Sources: RSS feeds (via xmltodict), GitHub REST API, Open-Meteo weather API.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
import xmltodict

logger = logging.getLogger(__name__)

# Optional GitHub token for higher rate limits (60/hr unauthenticated, 5000/hr with token)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Shared timeout for all external calls
REQUEST_TIMEOUT = 10.0


class AsyncFeedIngestor:
    """Async-native data ingestor. httpx for all I/O, no sync libraries."""

    async def fetch_rss(self, url: str) -> list[dict]:
        """Fetch RSS feed, parse with xmltodict. Returns list of item dicts.

        Each item contains: title, link, pubDate (when available).
        On any error: logs warning, returns empty list.
        """
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()

            parsed = xmltodict.parse(resp.text)
            channel = parsed.get("rss", {}).get("channel", {})
            items = channel.get("item", [])

            # xmltodict returns a dict (not list) when there's exactly one item
            if isinstance(items, dict):
                items = [items]

            return [
                {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "pubDate": item.get("pubDate", ""),
                }
                for item in items
            ]
        except Exception as e:
            logger.warning("RSS fetch failed for %s: %s", url, e)
            return []

    async def fetch_github_velocity(self, repo: str) -> dict | None:
        """Count merged PRs in last 24h for a GitHub repo via REST API.

        Args:
            repo: "owner/repo" format, e.g. "anthropics/claude-code"

        Returns dict with repo, merged_prs_24h, fetched_at — or None on error.
        """
        try:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if GITHUB_TOKEN:
                headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

            url = f"https://api.github.com/repos/{repo}/pulls"
            params = {
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
                "per_page": 50,
            }

            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(url, headers=headers, params=params)

                if resp.status_code == 403:
                    logger.warning("GitHub rate limit hit for %s", repo)
                    return None
                resp.raise_for_status()

            pulls = resp.json()
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

            merged_count = 0
            for pr in pulls:
                merged_at = pr.get("merged_at")
                if merged_at:
                    merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                    if merged_dt >= cutoff:
                        merged_count += 1

            return {
                "repo": repo,
                "merged_prs_24h": merged_count,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning("GitHub velocity fetch failed for %s: %s", repo, e)
            return None

    async def fetch_weather(self, lat: float, lon: float) -> dict | None:
        """Fetch current weather from Open-Meteo API (free, no key required).

        Returns dict with city coords, temperature_c, windspeed_kmh — or None on error.
        """
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current_weather": "true",
            }

            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()

            data = resp.json()
            current = data.get("current_weather", {})

            return {
                "latitude": lat,
                "longitude": lon,
                "temperature_c": current.get("temperature"),
                "windspeed_kmh": current.get("windspeed"),
                "weathercode": current.get("weathercode"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning("Weather fetch failed for lat=%s lon=%s: %s", lat, lon, e)
            return None
