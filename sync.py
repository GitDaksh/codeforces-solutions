import os
import re
import json
import time
import hashlib
import random
import string
import requests

# ── Configuration ────────────────────────────────────────────────────────────
CF_HANDLE     = os.environ["CF_HANDLE"]
CF_API_KEY    = os.environ["CF_API_KEY"]      # from codeforces.com/settings/api
CF_API_SECRET = os.environ["CF_API_SECRET"]   # from codeforces.com/settings/api
GH_TOKEN      = os.environ["GH_TOKEN"]
GH_REPO       = os.environ["GH_REPO"]

HISTORY_FILE    = "submission_history.json"
SUBMISSIONS_DIR = "submissions"

LANG_EXT = {
    "gnu g++20 11.2.0 (64 bit)":         "cpp",
    "gnu g++17 7.3.0":                   "cpp",
    "gnu g++17 9.2.0 (64 bit, msys 2)": "cpp",
    "gnu g++14 6.4.0":                   "cpp",
    "clang++17 diagnostics":             "cpp",
    "python 3.8.3":                      "py",
    "python 3.11 (64)":                  "py",
    "pypy 3.9.10 (64bit)":              "py",
    "java 17 64bit":                     "java",
    "java 11 64bit":                     "java",
    "java 8 32bit":                      "java",
    "kotlin 1.7":                        "kt",
    "javascript v8 4.8.0":              "js",
    "c# 10":                             "cs",
    "go 1.19.5":                         "go",
    "rust 2021":                         "rs",
}

def get_extension(lang: str) -> str:
    lang_lower = lang.lower()
    for key, ext in LANG_EXT.items():
        if key in lang_lower:
            return ext
    if "c++" in lang_lower or "cpp" in lang_lower: return "cpp"
    if "python" in lang_lower or "pypy" in lang_lower: return "py"
    if "java" in lang_lower: return "java"
    if "kotlin" in lang_lower: return "kt"
    if "rust" in lang_lower: return "rs"
    if "go" in lang_lower: return "go"
    if "c#" in lang_lower: return "cs"
    if "javascript" in lang_lower: return "js"
    return "txt"

def load_history() -> set:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return set(str(x) for x in json.load(f))
    return set()

def save_history(history: set):
    with open(HISTORY_FILE, "w") as f:
        json.dump(sorted(list(history)), f, indent=2)

def signed_url(method: str, params: dict) -> str:
    """Build a signed Codeforces API URL."""
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    p = dict(params)
    p["apiKey"] = CF_API_KEY
    p["time"]   = str(int(time.time()))
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(p.items()))
    sig_str  = f"{rand}/{method}?{sorted_params}#{CF_API_SECRET}"
    p["apiSig"] = rand + hashlib.sha512(sig_str.encode()).hexdigest()
    return f"https://codeforces.com/api/{method}", p

def cf_api(method: str, params: dict):
    url, p = signed_url(method, params)
    try:
        r = requests.get(url, params=p, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data["status"] == "OK":
            return data["result"]
        print(f"  CF API error [{method}]: {data.get('comment')}")
    except Exception as e:
        print(f"  Request failed [{method}]: {e}")
    return None

def fetch_accepted_submissions() -> list:
    print(f"Fetching submissions for {CF_HANDLE}...")
    result = cf_api("user.status", {"handle": CF_HANDLE, "from": "1", "count": "10000"})
    if not result:
        return []
    accepted = [s for s in result if s.get("verdict") == "OK"]
    print(f"Found {len(accepted)} accepted submissions")
    return accepted

def fetch_source(contest_id, submission_id: int) -> str | None:
    """
    Fetch submission source code via the authenticated CF API.
    Endpoint: https://codeforces.com/api/contest.submission
    This is the official way to get your own submission source.
    """
    result = cf_api("contest.submission", {
        "contestId":    str(contest_id),
        "submissionId": str(submission_id),
    })
    if result and isinstance(result, dict):
        src = result.get("source")
        if src:
            return src
    # result might be a list
    if result and isinstance(result, list) and result[0].get("source"):
        return result[0]["source"]
    return None

def sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '-', name)

def save_file(filepath: str, content: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    history     = load_history()
    submissions = fetch_accepted_submissions()

    # Keep only the most recent accepted sub per problem (avoid duplicates)
    seen = {}
    for sub in submissions:
        key = (sub.get("contestId"), sub.get("problem", {}).get("index"))
        if key not in seen:
            seen[key] = sub
    unique = list(seen.values())
    print(f"Unique problems solved: {len(unique)}")

    new_count  = 0
    fail_count = 0

    for sub in unique:
        sub_id        = str(sub["id"])
        contest_id    = sub.get("contestId", "gym")
        problem       = sub.get("problem", {})
        problem_index = problem.get("index", "X")
        problem_name  = sanitize(problem.get("name", "Unknown"))
        lang          = sub.get("programmingLanguage", "cpp")
        ext           = get_extension(lang)

        safe_name = problem_name.replace(" ", "_")[:40]
        filename  = f"{contest_id}_{problem_index}_{safe_name}.{ext}"
        filepath  = os.path.join(SUBMISSIONS_DIR, filename)

        # Already saved
        if sub_id in history or os.path.exists(filepath):
            history.add(sub_id)
            continue

        print(f"  [{contest_id}{problem_index}] {problem_name}  (sub {sub_id})")
        code = fetch_source(contest_id, sub_id)

        if code:
            save_file(filepath, code)
            history.add(sub_id)
            new_count += 1
            print(f"    ✅ {filename}")
        else:
            fail_count += 1
            print(f"    ⚠️  No source returned for submission {sub_id}")

        time.sleep(0.5)

    save_history(history)
    print(f"\nDone! Saved {new_count} new submission(s). Failed: {fail_count}.")

if __name__ == "__main__":
    main()
