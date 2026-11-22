"""Collect the GitHub metrics behind the koi pond and the stats panel.

Only the GraphQL API is used (one paginated repository query plus one
contributions query), so a daily run costs a handful of points out of the
5,000/hour budget. Requests retry with exponential backoff and honour
``Retry-After`` / ``X-RateLimit-Reset``. Callers fall back to the last good
snapshot when collection fails, so a GitHub outage never blanks the README.

Scope of every metric is recorded next to the number so the panel can label
it precisely.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .config import GitHubConfig

API = "https://api.github.com/graphql"
USER_AGENT = "profile-readme-generator"

REPOS_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    login
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    mergedPullRequests: pullRequests(states: MERGED) { totalCount }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER,
                 privacy: PUBLIC, isFork: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        stargazerCount
        isArchived
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
  rateLimit { remaining resetAt cost }
}
"""

CONTRIB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoryContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner }
        contributions { totalCount }
      }
    }
  }
  rateLimit { remaining resetAt cost }
}
"""


class GitHubError(RuntimeError):
    pass


@dataclass
class Language:
    name: str
    color: str
    bytes: int
    share: float = 0.0


@dataclass
class Snapshot:
    login: str
    generated_at: str
    window_days: int
    window_from: str
    window_to: str
    # Contribution calendar total for the window (what the profile graph shows).
    contributions_calendar: int
    # Calendar total minus commits to excluded repositories (koi input).
    contributions: int
    excluded_commits: int
    private_contributions: int  # restricted, count-only; included in calendar
    commits: int
    pull_requests_window: int
    issues_window: int
    reviews_window: int
    public_repos: int  # owned, public, non-fork
    stars: int  # on those repos
    followers: int
    pull_requests_total: int  # all-time, authored, any repo
    pull_requests_merged: int
    languages: list[Language] = field(default_factory=list)
    language_scope: str = ""
    daily: list[int] = field(default_factory=list)  # oldest -> newest
    stale: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Snapshot":
        d = json.loads(text)
        d["languages"] = [Language(**lang) for lang in d.get("languages", [])]
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in known})


# --------------------------------------------------------------------------
# transport

Transport = Callable[[str, dict[str, Any]], dict[str, Any]]


def http_transport(token: str, retries: int = 4, sleep=time.sleep) -> Transport:
    def call(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({"query": query, "variables": variables}).encode()
        delay = 2.0
        last: Exception | None = None
        for attempt in range(retries):
            req = urllib.request.Request(
                API,
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    payload = json.loads(resp.read())
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (403, 429) or e.code >= 500:
                    wait = _retry_after(e.headers, delay)
                    if attempt < retries - 1 and wait <= 120:
                        sleep(wait)
                        delay *= 2
                        continue
                raise GitHubError(f"GitHub API HTTP {e.code}: {e.reason}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                last = e
                if attempt < retries - 1:
                    sleep(delay)
                    delay *= 2
                    continue
                raise GitHubError(f"network error: {e}") from e
            if payload.get("errors"):
                msgs = "; ".join(err.get("message", "?") for err in payload["errors"])
                raise GitHubError(f"GraphQL error: {msgs}")
            return payload["data"]
        raise GitHubError(f"giving up after {retries} attempts: {last}")

    return call


def _retry_after(headers, default: float) -> float:
    if headers is None:
        return default
    if headers.get("Retry-After"):
        try:
            return float(headers["Retry-After"])
        except ValueError:
            pass
    if headers.get("X-RateLimit-Remaining") == "0" and headers.get("X-RateLimit-Reset"):
        try:
            return max(1.0, float(headers["X-RateLimit-Reset"]) - time.time())
        except ValueError:
            pass
    return default


def token_from_env() -> str:
    for key in ("PROFILE_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key, "").strip():
            return os.environ[key].strip()
    raise GitHubError("no token: set GITHUB_TOKEN (or PROFILE_TOKEN / GH_TOKEN)")


# --------------------------------------------------------------------------
# collection


def collect(cfg: GitHubConfig, transport: Transport,
            now: datetime | None = None) -> Snapshot:
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    start = now - timedelta(days=cfg.window_days)
    excluded = {r.lower() for r in cfg.exclude_repos}
    excluded_langs = {name.lower() for name in cfg.exclude_languages}

    # Repositories (paginated).
    repos: list[dict[str, Any]] = []
    cursor = None
    user: dict[str, Any] = {}
    while True:
        data = transport(REPOS_QUERY, {"login": cfg.login, "cursor": cursor})
        user = data.get("user") or {}
        if not user:
            raise GitHubError(f"user {cfg.login!r} not found")
        page = user["repositories"]
        repos.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    counted = [r for r in repos if r["nameWithOwner"].lower() not in excluded]
    stars = sum(r["stargazerCount"] for r in repos)  # stars: all owned public repos

    lang_bytes: dict[str, Language] = {}
    for r in counted:
        for edge in r["languages"]["edges"]:
            name = edge["node"]["name"]
            if name.lower() in excluded_langs:
                continue
            lang = lang_bytes.setdefault(
                name, Language(name=name, color=edge["node"].get("color") or "#8b949e", bytes=0))
            lang.bytes += int(edge["size"])
    total_bytes = sum(lang.bytes for lang in lang_bytes.values()) or 1
    languages = sorted(lang_bytes.values(), key=lambda lang: -lang.bytes)
    for lang in languages:
        lang.share = lang.bytes / total_bytes

    # Contributions over the rolling window.
    data = transport(CONTRIB_QUERY, {
        "login": cfg.login,
        "from": start.isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
    })
    cc = data["user"]["contributionsCollection"]
    cal = cc["contributionCalendar"]
    excluded_commits = sum(
        item["contributions"]["totalCount"]
        for item in cc["commitContributionsByRepository"]
        if item["repository"]["nameWithOwner"].lower() in excluded
    )
    daily = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]

    return Snapshot(
        login=user["login"],
        generated_at=now.isoformat(),
        window_days=cfg.window_days,
        window_from=start.date().isoformat(),
        window_to=now.date().isoformat(),
        contributions_calendar=cal["totalContributions"],
        contributions=max(0, cal["totalContributions"] - excluded_commits),
        excluded_commits=excluded_commits,
        private_contributions=cc["restrictedContributionsCount"],
        commits=cc["totalCommitContributions"],
        pull_requests_window=cc["totalPullRequestContributions"],
        issues_window=cc["totalIssueContributions"],
        reviews_window=cc["totalPullRequestReviewContributions"],
        public_repos=len(repos),
        stars=stars,
        followers=user["followers"]["totalCount"],
        pull_requests_total=user["pullRequests"]["totalCount"],
        pull_requests_merged=user["mergedPullRequests"]["totalCount"],
        languages=languages,
        language_scope=(
            f"bytes of code across {len(counted)} public non-fork repos"
            + (f", excl. {', '.join(sorted(cfg.exclude_languages))}" if cfg.exclude_languages else "")
        ),
        daily=daily,
    )


def load_cached(path: Path) -> Snapshot | None:
    try:
        snap = Snapshot.from_json(path.read_text())
    except (OSError, ValueError, TypeError, KeyError):
        return None
    snap.stale = True
    return snap
