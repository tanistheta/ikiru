import requests
import sys
import os
import time
import csv

TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

CODEOWNERS_PATHS = ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]

LANGUAGES = ["Python", "JavaScript", "Go", "Java", "C++", "TypeScript", "Rust", "C#", "PHP", "Ruby", "Kotlin", "Swift"]
PER_LANGUAGE = 15

ALREADY_CHECKED = {
    "public-apis/public-apis", "EbookFoundation/free-programming-books",
    "donnemartin/system-design-primer", "vinta/awesome-python", "TheAlgorithms/Python",
    "NousResearch/hermes-agent", "Significant-Gravitas/AutoGPT", "yt-dlp/yt-dlp",
    "AUTOMATIC1111/stable-diffusion-webui", "521xueweihan/HelloGitHub",
    "react/react", "affaan-m/ECC", "trekhleb/javascript-algorithms",
    "Snailclimb/JavaGuide", "airbnb/javascript", "vercel/next.js",
    "Chalarangelo/30-seconds-of-code", "nodejs/node", "mrdoob/three.js", "axios/axios",
    "avelino/awesome-go", "ollama/ollama", "golang/go", "kubernetes/kubernetes",
    "fatedier/frp", "gin-gonic/gin", "gohugoio/hugo", "syncthing/syncthing",
    "infiniflow/ragflow", "junegunn/fzf", "krahets/hello-algo",
    "GrowingGit/GitHub-Chinese-Top-Charts", "iluwatar/java-design-patterns",
    "Stirling-Tools/Stirling-PDF", "macrozheng/mall", "spring-projects/spring-boot",
    "doocs/advanced-java", "elastic/elasticsearch", "MisterBooo/LeetCodeAnimation",
    "NationalSecurityAgency/ghidra", "tensorflow/tensorflow", "react/react-native",
    "electron/electron", "ggml-org/llama.cpp", "godotengine/godot",
    "microsoft/terminal", "bitcoin/bitcoin", "opencv/opencv", "nomic-ai/gpt4all",
    "tesseract-ocr/tesseract", "python/cpython", "django/django", "pallets/flask",
}

MIN_PUSHED_AFTER = "2024-01-01"


def fetch_top_repos(language, count=10):
    url = "https://api.github.com/search/repositories"
    query = f"language:{language} pushed:>{MIN_PUSHED_AFTER}"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": count}

    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        print(f"  ERROR fetching {language} repos: {resp.status_code} {resp.text[:200]}")
        return []

    items = resp.json().get("items", [])
    return [(item["owner"]["login"], item["name"], item["stargazers_count"]) for item in items]


def find_first_commit_for_path(owner, repo, path):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"path": path, "per_page": 100}

    last_page_data = None
    page_count = 0
    while url:
        resp = requests.get(url, headers=HEADERS, params=params if page_count == 0 else None)
        if resp.status_code in (404, 409):
            return None
        if resp.status_code == 403:
            print("  RATE LIMITED - stopping early. Re-run later or check token.")
            raise SystemExit(1)
        if resp.status_code != 200:
            print(f"  [{path}] unexpected status {resp.status_code}")
            return None

        data = resp.json()
        if data:
            last_page_data = data

        link_header = resp.headers.get("Link", "")
        next_url = None
        if link_header:
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
        url = next_url
        page_count += 1
        if page_count > 50:
            break

    if not last_page_data:
        return None

    oldest_commit = last_page_data[-1]
    return {
        "sha": oldest_commit["sha"],
        "date": oldest_commit["commit"]["committer"]["date"],
        "path": path,
    }


def find_codeowners_introduction(owner, repo):
    for path in CODEOWNERS_PATHS:
        result = find_first_commit_for_path(owner, repo, path)
        if result:
            return result
    return None


if __name__ == "__main__":
    if not TOKEN:
        print("WARNING: No GITHUB_TOKEN set. You will hit rate limits almost immediately.")
        print('Set it with: $env:GITHUB_TOKEN = "your_token"')
        print()

    all_repos = []
    seen = set()
    print("Fetching top-starred repos per language...")
    for lang in LANGUAGES:
        repos = fetch_top_repos(lang, PER_LANGUAGE)
        new_count = 0
        for owner, name, stars in repos:
            full_name = f"{owner}/{name}"
            if full_name in ALREADY_CHECKED or full_name in seen:
                continue
            seen.add(full_name)
            all_repos.append((owner, name, lang, stars))
            new_count += 1
        print(f"  {lang}: {len(repos)} fetched, {new_count} new (not already checked)")
        time.sleep(1)

    print(f"\nTotal NEW candidates to check: {len(all_repos)}\n")
    print("=" * 70)
    print("Checking CODEOWNERS introduction dates...")
    print("=" * 70)

    results = []
    for owner, repo, lang, stars in all_repos:
        print(f"Checking {owner}/{repo} ({lang}, {stars} stars)...")
        result = find_codeowners_introduction(owner, repo)
        date_str = result["date"] if result else None
        is_usable = bool(date_str and "2021-01-01" <= date_str[:10] <= "2026-03-31")
        results.append({
            "repo": f"{owner}/{repo}",
            "language": lang,
            "stars": stars,
            "codeowners_path": result["path"] if result else None,
            "first_date": date_str,
            "sha": result["sha"] if result else None,
            "usable_for_did": "YES" if is_usable else "",
        })
        status = date_str if date_str else "never adopted"
        flag = "  <-- USABLE TREATMENT EVENT" if is_usable else ""
        print(f"  -> {status}{flag}")
        time.sleep(0.3)

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"{'repo':<30} {'language':<12} {'stars':<8} {'date':<22} {'usable':<8} {'path'}")
    print("-" * 100)
    for r in sorted(results, key=lambda x: x["first_date"] or "9999"):
        date_str = r["first_date"] if r["first_date"] else "NEVER ADOPTED"
        path_str = r["codeowners_path"] if r["codeowners_path"] else "-"
        print(f"{r['repo']:<30} {r['language']:<12} {r['stars']:<8} {date_str:<22} {r['usable_for_did']:<8} {path_str}")

    treated = [r for r in results if r["first_date"]]
    usable = [r for r in results if r["usable_for_did"] == "YES"]
    print(f"\nTreated (any date): {len(treated)} / {len(results)}")
    print(f"USABLE for DiD (treatment date 2021-01-01 to 2026-03-31): {len(usable)}")

    with open("expanded_codeowners_dates_round2.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["repo", "language", "stars", "codeowners_path", "first_date", "sha", "usable_for_did"])
        writer.writeheader()
        writer.writerows(results)
    print("\nSaved to expanded_codeowners_dates_round2.csv")