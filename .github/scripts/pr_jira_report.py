"""Generate a markdown report that maps repository PRs to Jira ticket keys."""

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set, Tuple

GITHUB_API = "https://api.github.com"
JIRA_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")


def parse_link_header(link_header: str) -> Optional[str]:
    """Return the URL for the next page from a GitHub Link header."""
    if not link_header:
        return None

    parts = [p.strip() for p in link_header.split(",")]
    for part in parts:
        if 'rel="next"' in part:
            left = part.find("<")
            right = part.find(">")
            if left != -1 and right != -1:
                return part[left + 1 : right]
    return None


def github_get(url: str, token: str) -> Tuple[List[Dict], Optional[str]]:
    """Fetch one GitHub API page and return JSON data with the next page URL."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "daily-pr-jira-report",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    request = urllib.request.Request(url=url, headers=headers, method="GET")
    with urllib.request.urlopen(request) as response:
        data = json.loads(response.read().decode("utf-8"))
        next_url = parse_link_header(response.headers.get("Link", ""))
        return data, next_url


def paginate(url: str, token: str) -> List[Dict]:
    """Follow paginated GitHub API responses and collect all items."""
    all_items: List[Dict] = []
    next_url: Optional[str] = url
    while next_url:
        items, next_url = github_get(next_url, token)
        all_items.extend(items)
    return all_items


def extract_jira_keys(text: str) -> Set[str]:
    """Extract unique Jira-style keys from free-form text."""
    if not text:
        return set()
    return set(JIRA_KEY_PATTERN.findall(text))


def build_ticket_cell(keys: Iterable[str], jira_base_url: str) -> str:
    """Build the markdown table cell content for Jira ticket references."""
    unique_sorted = sorted(set(keys))
    if not unique_sorted:
        return "-"

    clean_base = jira_base_url.strip().rstrip("/")
    if clean_base:
        return ", ".join(
            f"[{key}]({clean_base}/browse/{key})" for key in unique_sorted
        )
    return ", ".join(unique_sorted)


def with_query(url: str, params: Dict[str, str]) -> str:
    """Append URL-encoded query parameters to a base URL."""
    return f"{url}?{urllib.parse.urlencode(params)}"


def collect_pr_jira_keys(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
    pr_title: str,
    pr_body: str,
) -> Set[str]:
    """Collect Jira keys from a PR title/body and its issue and review comments."""
    keys = set()
    keys |= extract_jira_keys(pr_title)
    keys |= extract_jira_keys(pr_body)

    issue_comments_url = with_query(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments",
        {"per_page": "100"},
    )
    issue_comments = paginate(issue_comments_url, token)
    for comment in issue_comments:
        keys |= extract_jira_keys(comment.get("body", ""))

    review_comments_url = with_query(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
        {"per_page": "100"},
    )
    review_comments = paginate(review_comments_url, token)
    for comment in review_comments:
        keys |= extract_jira_keys(comment.get("body", ""))

    return keys


def main() -> None:
    """Generate the PR-to-Jira markdown report and write it to reports/."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo_full_name = os.environ.get("REPO", "").strip()
    jira_base_url = os.environ.get("JIRA_BASE_URL", "").strip()
    pr_base_branch = os.environ.get("PR_BASE_BRANCH", "").strip()

    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")
    if "/" not in repo_full_name:
        raise RuntimeError("REPO must look like owner/repository")

    owner, repo = repo_full_name.split("/", 1)

    pulls_url = with_query(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
        {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": "100",
        },
    )
    if pr_base_branch:
        pulls_url = with_query(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            {
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": "100",
                "base": pr_base_branch,
            },
        )
    pulls = paginate(pulls_url, token)

    lines: List[str] = []
    lines.append("# Daily PR to Jira Report")
    lines.append("")
    lines.append(f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("| PR | Title | State | Jira Tickets | Updated |")
    lines.append("| --- | --- | --- | --- | --- |")

    for pr in pulls:
        pr_number = pr.get("number")
        pr_title = pr.get("title") or ""
        title = pr_title.replace("|", " ").strip()
        pr_url = pr.get("html_url") or ""
        pr_body = pr.get("body") or ""

        state = pr.get("state", "unknown")
        if pr.get("merged_at"):
            state = "merged"

        updated_at = pr.get("updated_at") or "-"

        keys = collect_pr_jira_keys(owner, repo, int(pr_number), token, pr_title, pr_body)
        ticket_cell = build_ticket_cell(keys, jira_base_url)

        lines.append(
            f"| [#{pr_number}]({pr_url}) | {title} | {state} | {ticket_cell} | {updated_at} |"
        )

    os.makedirs("reports", exist_ok=True)
    output_path = os.path.join("reports", "pr-jira-report.md")
    with open(output_path, "w", encoding="utf-8") as report_file:
        report_file.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
