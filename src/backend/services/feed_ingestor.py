"""
feed_ingestor.py — Async-native data ingestor for multi-modal markets.

Uses httpx for ALL external I/O (no sync libraries).
Sources: RSS feeds (via xmltodict), GitHub REST API, Open-Meteo weather API,
         Wikipedia REST API (v1.7 Proof-of-Retrieval, v1.8 Tool-Enabled Lookup).
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
import xmltodict

logger = logging.getLogger(__name__)

# Optional GitHub token for higher rate limits
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Shared timeout for all external calls
REQUEST_TIMEOUT = 10.0


class AsyncFeedIngestor:
    """Async-native data ingestor. httpx for all I/O, no sync libraries."""

    def _get_wiki_headers(self) -> dict:
        """
        Generate compliant headers for Wikimedia APIs.
        Policy: Must include contact info (email/website) in User-Agent.
        """
        return {
            "User-Agent": "ClawdXCraft/1.9 (bot-admin@clawdxcraft.local; https://github.com/your-repo/clawdxcraft) python-httpx/0.24.1",
            "Accept": "application/json; charset=utf-8; profile=\"https://www.mediawiki.org/wiki/Specs/Summary/1.4.2\""
        }

    async def fetch_rss(self, url: str) -> list[dict]:
        """Fetch RSS feed, parse with xmltodict."""
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()

            parsed = xmltodict.parse(resp.text)
            channel = parsed.get("rss", {}).get("channel", {})
            items = channel.get("item", [])

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
            logger.warning(f"RSS fetch failed for {url}: {e}")
            return []

    async def fetch_github_velocity(self, repo: str) -> dict | None:
        """Count merged PRs in last 24h for a GitHub repo."""
        try:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ClawdXCraft/1.9"
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
                    logger.warning(f"GitHub rate limit hit for {repo}")
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
            logger.warning(f"GitHub velocity fetch failed for {repo}: {e}")
            return None

    async def fetch_weather(self, lat: float, lon: float) -> dict | None:
        """Fetch current weather from Open-Meteo API."""
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
            logger.warning(f"Weather fetch failed for lat={lat} lon={lon}: {e}")
            return None

    async def wikipedia_lookup(
        self, title: str, *, max_retries: int = 3, base_backoff: float = 2.0,
    ) -> dict | None:
        """Look up a specific Wikipedia article by title via REST API."""
        encoded_title = quote(title.replace(" ", "_"), safe="")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
        
        # Use centralized headers
        headers = self._get_wiki_headers()

        last_error = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    resp = await client.get(
                        url, headers=headers, follow_redirects=True,
                    )

                    if resp.status_code == 404:
                        logger.info(f"Wikipedia lookup: article not found for '{title}'")
                        return None

                    if resp.status_code == 403:
                        logger.info(f"Wikipedia REST API 403 for '{title}' — falling back to MediaWiki action API")
                        return await self._mediawiki_lookup(title)

                    if resp.status_code == 429:
                        wait = base_backoff * (2 ** attempt)
                        logger.warning(
                            f"Wikipedia lookup 429 for '{title}' — backoff {wait:.1f}s (attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait)
                        continue

                    resp.raise_for_status()

                data = resp.json()
                pageid = data.get("pageid")
                resolved_title = data.get("title", "")

                if not pageid:
                    logger.warning(f"Wikipedia lookup: no pageid in response for '{title}'")
                    return None

                return {
                    "title": resolved_title,
                    "pageid": pageid,
                    "extract": data.get("extract", "")[:300],
                }

            except httpx.TimeoutException as e:
                last_error = e
                wait = base_backoff * (2 ** attempt)
                logger.warning(
                    f"Wikipedia lookup timeout for '{title}' — backoff {wait:.1f}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait)
                continue

            except Exception as e:
                logger.warning(f"Wikipedia lookup failed for '{title}': {e}")
                return None

        logger.warning(
            f"Wikipedia lookup exhausted {max_retries} retries for '{title}': {last_error}"
        )
        return None

    async def _mediawiki_random_article(self) -> dict | None:
        """Fallback: Fetch a random article via MediaWiki action API.

        Uses the older action=query API which has different rate limiting
        than the REST API and is less likely to 403 from hosting IPs.
        """
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "generator": "random",
            "grnnamespace": "0",
            "grnlimit": "1",
            "prop": "extracts|info",
            "exintro": "true",
            "explaintext": "true",
            "exsentences": "3",
        }
        headers = self._get_wiki_headers()

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()

            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return None

            page = next(iter(pages.values()))
            pageid = page.get("pageid")
            title = page.get("title", "")

            if not pageid or not title:
                return None

            return {
                "title": title,
                "pageid": pageid,
                "extract": page.get("extract", "")[:300],
            }
        except Exception as e:
            logger.warning(f"MediaWiki random article fallback failed: {e}")
            return None

    async def _mediawiki_lookup(self, title: str) -> dict | None:
        """Fallback: Look up article by title via MediaWiki action API."""
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "extracts|info",
            "exintro": "true",
            "explaintext": "true",
            "exsentences": "3",
            "redirects": "1",
        }
        headers = self._get_wiki_headers()

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()

            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return None

            page = next(iter(pages.values()))
            pageid = page.get("pageid")
            if not pageid or pageid == -1:
                return None

            return {
                "title": page.get("title", title),
                "pageid": pageid,
                "extract": page.get("extract", "")[:300],
            }
        except Exception as e:
            logger.warning(f"MediaWiki lookup fallback failed for '{title}': {e}")
            return None

    async def fetch_random_wikipedia_summary(self) -> dict | None:
        """Fetch a random Wikipedia article summary.

        Tries REST API first, falls back to MediaWiki action API on 403.
        """
        try:
            headers = self._get_wiki_headers()

            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(
                    "https://en.wikipedia.org/api/rest_v1/page/random/summary",
                    headers=headers,
                    follow_redirects=True,
                )

                if resp.status_code == 403:
                    logger.info("Wikipedia REST API 403 — falling back to MediaWiki action API")
                    return await self._mediawiki_random_article()

                resp.raise_for_status()

            data = resp.json()
            pageid = data.get("pageid")
            title = data.get("title", "")

            if not pageid or not title:
                logger.warning("Wikipedia summary missing pageid or title")
                return None

            return {
                "title": title,
                "pageid": pageid,
                "extract": data.get("extract", "")[:300],
            }
        except Exception as e:
            logger.warning(f"Wikipedia REST fetch failed: {e} — trying MediaWiki fallback")
            return await self._mediawiki_random_article()
