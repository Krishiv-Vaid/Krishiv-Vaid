import json
from datetime import datetime, timezone

import pytest

from profilegen.config import GitHubConfig
from profilegen.github_data import CONTRIB_QUERY, REPOS_QUERY, GitHubError, Snapshot, _retry_after, collect, load_cached


def repo(name, stars, langs):
    return {"nameWithOwner": name, "stargazerCount": stars, "isArchived": False,
            "languages": {"edges": [{"size": s, "node": {"name": n, "color": c}} for n, c, s in langs]}}


def fake_transport(pages, contrib):
    calls = []

    def call(query, variables):
        calls.append((query, variables))
        if query is REPOS_QUERY:
            idx = 0 if variables["cursor"] is None else int(variables["cursor"])
            return {"user": pages[idx], "rateLimit": {"remaining": 4999}}
        assert query is CONTRIB_QUERY
        assert variables["from"].endswith("Z") and variables["to"].endswith("Z")
        return {"user": {"contributionsCollection": contrib}}

    call.calls = calls
    return call


def page(nodes, has_next=False, cursor=None):
    return {"login": "octo", "createdAt": "2020-01-01T00:00:00Z",
            "followers": {"totalCount": 12}, "pullRequests": {"totalCount": 30},
            "mergedPullRequests": {"totalCount": 25},
            "repositories": {"totalCount": 3, "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                             "nodes": nodes}}


CONTRIB = {
    "totalCommitContributions": 90, "totalIssueContributions": 3,
    "totalPullRequestContributions": 7, "totalPullRequestReviewContributions": 2,
    "totalRepositoryContributions": 1, "restrictedContributionsCount": 5,
    "contributionCalendar": {"totalContributions": 120, "weeks": [
        {"contributionDays": [{"date": "2026-01-01", "contributionCount": 3},
                              {"date": "2026-01-02", "contributionCount": 0}]}]},
    "commitContributionsByRepository": [
        {"repository": {"nameWithOwner": "octo/octo"}, "contributions": {"totalCount": 20}},
        {"repository": {"nameWithOwner": "octo/engine"}, "contributions": {"totalCount": 70}},
    ],
}


def test_collect_paginates_excludes_and_labels():
    pages = [
        page([repo("octo/engine", 5, [("C++", "#f34b7d", 600), ("CMake", "#DA3434", 50)]),
              repo("octo/site", 1, [("HTML", "#e34c26", 9000), ("JavaScript", "#f1e05a", 350)])],
             has_next=True, cursor="1"),
        page([repo("octo/octo", 2, [("Python", "#3572A5", 10**6)])]),
    ]
    t = fake_transport(pages, CONTRIB)
    cfg = GitHubConfig(login="octo", exclude_repos=("octo/octo",), exclude_languages=("HTML",))
    snap = collect(cfg, t, now=datetime(2026, 11, 22, tzinfo=timezone.utc))

    assert len([c for c in t.calls if c[0] is REPOS_QUERY]) == 2
    assert snap.public_repos == 3
    assert snap.stars == 8  # stars count every owned public repo
    assert snap.contributions_calendar == 120
    assert snap.excluded_commits == 20
    assert snap.contributions == 100  # calendar minus commits to the excluded repo
    assert snap.private_contributions == 5
    names = [lang.name for lang in snap.languages]
    assert "HTML" not in names and "Python" not in names  # excluded language / excluded repo
    assert names[0] == "C++"
    assert abs(sum(lang.share for lang in snap.languages) - 1) < 1e-9
    assert snap.window_from == "2025-11-22" and snap.window_to == "2026-11-22"
    assert snap.daily == [3, 0]


def test_missing_user_raises():
    def t(q, v):
        return {"user": None}
    with pytest.raises(GitHubError):
        collect(GitHubConfig(login="nobody"), t)


def test_snapshot_roundtrip_and_stale_cache(tmp_path):
    pages = [page([repo("octo/engine", 5, [("C++", "#f34b7d", 600)])])]
    snap = collect(GitHubConfig(login="octo"), fake_transport(pages, CONTRIB))
    path = tmp_path / "snap.json"
    path.write_text(snap.to_json())
    again = Snapshot.from_json(path.read_text())
    assert again == snap
    cached = load_cached(path)
    assert cached.stale is True
    assert load_cached(tmp_path / "missing.json") is None
    (tmp_path / "bad.json").write_text("{not json")
    assert load_cached(tmp_path / "bad.json") is None


def test_retry_after_headers():
    assert _retry_after({"Retry-After": "7"}, 2.0) == 7.0
    assert _retry_after({}, 3.0) == 3.0
    assert _retry_after(None, 4.0) == 4.0
    assert _retry_after({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"}, 2.0) >= 1.0


def test_http_transport_retries_then_succeeds(monkeypatch):
    import io
    import urllib.error

    from profilegen import github_data

    attempts = {"n": 0}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise urllib.error.HTTPError(req.full_url, 502, "bad gateway", {}, None)
        return Resp(json.dumps({"data": {"ok": True}}).encode())

    monkeypatch.setattr(github_data.urllib.request, "urlopen", fake_urlopen)
    slept = []
    call = github_data.http_transport("t", retries=4, sleep=slept.append)
    assert call("q", {}) == {"ok": True}
    assert attempts["n"] == 3 and slept == [2.0, 4.0]


def test_http_transport_surfaces_graphql_errors(monkeypatch):
    import io

    from profilegen import github_data

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(github_data.urllib.request, "urlopen",
                        lambda req, timeout: Resp(json.dumps({"errors": [{"message": "boom"}]}).encode()))
    with pytest.raises(GitHubError, match="boom"):
        github_data.http_transport("t")("q", {})
