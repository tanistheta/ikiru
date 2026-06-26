import os
import re
import sys
import time
import fnmatch
import requests
import pandas as pd

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    sys.exit(
        "Set GITHUB_TOKEN as an environment variable before running this "
        "script (a fine-grained PAT with public repo read access is enough)."
    )

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

CODEOWNERS_PATHS = ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]


def gh_get(url, params=None):
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, params=params)
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 5)
            print(f"  rate limited, sleeping {wait:.0f}s...")
            time.sleep(wait)
            continue
        return r
    return r


def get_commit_at_or_before(repo, date_str):
    """Find the latest commit on the default branch at or before `date_str`
    (treatment_date), so we read CODEOWNERS as it existed then, not its
    current state."""
    url = f"https://api.github.com/repos/{repo}/commits"
    params = {"until": f"{date_str}T23:59:59Z", "per_page": 1}
    r = gh_get(url, params=params)
    if r.status_code != 200:
        print(f"  [{repo}] commit lookup failed: {r.status_code} {r.text[:200]}")
        return None
    commits = r.json()
    if not commits:
        return None
    return commits[0]["sha"]


def get_codeowners_content(repo, sha):
    for path in CODEOWNERS_PATHS:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        r = gh_get(url, params={"ref": sha})
        if r.status_code == 200:
            import base64
            data = r.json()
            content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
            return path, content
    return None, None


def get_file_tree(repo, sha):
    url = f"https://api.github.com/repos/{repo}/git/trees/{sha}"
    r = gh_get(url, params={"recursive": "1"})
    if r.status_code != 200:
        print(f"  [{repo}] tree fetch failed: {r.status_code} {r.text[:200]}")
        return []
    data = r.json()
    if data.get("truncated"):
        print(f"  [{repo}] WARNING: tree truncated by GitHub API (very large repo); "
              f"coverage % will be an approximation over the returned subset only.")
    return [item["path"] for item in data.get("tree", []) if item["type"] == "blob"]


def parse_codeowners_rules(content):
    rules = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if not parts:
            continue
        pattern = parts[0]
        rules.append(pattern)
    return rules


def pattern_to_glob(pattern):
    """Convert a CODEOWNERS gitignore-style pattern to an fnmatch-compatible
    glob. Handles the common cases seen in Table II of Lulla et al.:
    '*', '/dir/', '/dir/**', '*.md', '.github/', leading '/'.
    """
    p = pattern
    if p == "*":
        return "*"
    p = p.lstrip("/")
    if p.endswith("/"):
        p = p + "**"
    return p


def file_matches_rule(filepath, glob_pattern):
    if glob_pattern == "*":
        return True
    if fnmatch.fnmatch(filepath, glob_pattern):
        return True
    if fnmatch.fnmatch(filepath, "*/" + glob_pattern):
        return True
    return False


def compute_coverage(repo, files, rules):
    if not files:
        return 0.0, 0
    globs = [pattern_to_glob(r) for r in rules]
    covered = 0
    for f in files:
        if any(file_matches_rule(f, g) for g in globs):
            covered += 1
    pct = 100.0 * covered / len(files)
    return pct, covered


def main():
    treated = pd.read_csv("final_treated_repos.csv")
    results = []

    for _, row in treated.iterrows():
        repo = row["repo"]
        tdate = row["treatment_date"]
        print(f"Processing {repo} (treated {tdate})...")

        sha = get_commit_at_or_before(repo, tdate)
        if sha is None:
            print(f"  [{repo}] no commit found at/before treatment date, skipping")
            results.append({"repo": repo, "treatment_date": tdate, "error": "no_commit"})
            continue

        path, content = get_codeowners_content(repo, sha)
        if content is None:
            print(f"  [{repo}] CODEOWNERS not found at treatment commit, skipping")
            results.append({"repo": repo, "treatment_date": tdate, "error": "no_codeowners_at_commit"})
            continue

        rules = parse_codeowners_rules(content)
        files = get_file_tree(repo, sha)
        pct, covered = compute_coverage(repo, files, rules)

        bucket = "low" if pct <= 10 else ("high" if pct >= 90 else "mid")

        results.append({
            "repo": repo,
            "treatment_date": tdate,
            "codeowners_sha": sha,
            "codeowners_path": path,
            "n_files_total": len(files),
            "n_files_covered": covered,
            "coverage_pct": round(pct, 2),
            "n_rules": len(rules),
            "single_rule_only": len(rules) == 1,
            "coverage_bucket": bucket,
        })
        print(f"  [{repo}] {len(rules)} rules, {pct:.1f}% coverage ({bucket})")
        time.sleep(0.5)  # be polite to the API even with auth

    out = pd.DataFrame(results)
    out.to_csv("codeowners_coverage.csv", index=False)
    print(f"\nWrote codeowners_coverage.csv with {len(out)} rows.")
    if "coverage_bucket" in out.columns:
        print(out["coverage_bucket"].value_counts())


if __name__ == "__main__":
    main()