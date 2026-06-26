import requests
import sys
import os

TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

CODEOWNERS_PATHS = ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]

def find_first_commit_for_path(owner, repo, path):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"path": path, "per_page": 100}

    last_page_data = None
    page_count = 0
    while url:
        resp = requests.get(url, headers=HEADERS, params=params if page_count == 0 else None)
        if resp.status_code == 404:
            print(f"  [{path}] repo or path not found (404)")
            return None
        if resp.status_code == 409:
            print(f"  [{path}] repo is empty (409)")
            return None
        if resp.status_code != 200:
            print(f"  [{path}] unexpected status {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        if data:
            last_page_data = data

        link_header = resp.headers.get("Link", "")
        next_url = None
        if link_header:
            parts = link_header.split(",")
            for part in parts:
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
        url = next_url
        page_count += 1

        if page_count > 50:
            print(f"  [{path}] stopped after 50 pages (safety limit)")
            break

    if not last_page_data:
        return None

    oldest_commit = last_page_data[-1]
    sha = oldest_commit["sha"]
    date = oldest_commit["commit"]["committer"]["date"]
    return {"sha": sha, "date": date, "path": path}


def find_codeowners_introduction(owner, repo):
    print(f"Checking {owner}/{repo}...")
    for path in CODEOWNERS_PATHS:
        result = find_first_commit_for_path(owner, repo, path)
        if result:
            print(f"  FOUND: {result['path']} first appears {result['date']} (sha {result['sha'][:8]})")
            return result
        else:
            print(f"  [{path}] no history found")
    print("  No CODEOWNERS file found in any standard location.")
    return None


REPOS = [
    ("python", "cpython"),
    ("django", "django"),
    ("pallets", "flask"),
    ("facebook", "react"),
    ("microsoft", "vscode"),
    ("numpy", "numpy"),
    ("scikit-learn", "scikit-learn"),
    ("rails", "rails"),
    ("rust-lang", "rust"),
]

if __name__ == "__main__":
    if not TOKEN:
        print("WARNING: No GITHUB_TOKEN env var set. You will hit rate limits fast (60 req/hr unauthenticated).")
        print()

    results = []
    for owner, repo in REPOS:
        result = find_codeowners_introduction(owner, repo)
        results.append({
            "repo": f"{owner}/{repo}",
            "codeowners_path": result["path"] if result else None,
            "first_date": result["date"] if result else None,
            "sha": result["sha"] if result else None,
        })
        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'repo':<25} {'date':<22} {'path'}")
    print("-" * 70)
    for r in results:
        date_str = r["first_date"] if r["first_date"] else "NEVER ADOPTED"
        path_str = r["codeowners_path"] if r["codeowners_path"] else "-"
        print(f"{r['repo']:<25} {date_str:<22} {path_str}")

    import csv
    with open("codeowners_treatment_dates.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["repo", "codeowners_path", "first_date", "sha"])
        writer.writeheader()
        writer.writerows(results)
    print()
    print("Saved to codeowners_treatment_dates.csv")