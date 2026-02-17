import os
import json
import time
import requests

# ── Configuration ────────────────────────────────────────────────────────────
CF_HANDLE  = os.environ["CF_HANDLE"]   # your Codeforces handle
GH_TOKEN   = os.environ["GH_TOKEN"]    # your GitHub token
GH_REPO    = os.environ["GH_REPO"]     # e.g. "username/repo-name"

HISTORY_FILE = "submission_history.json"
SUBMISSIONS_DIR = "submissions"

# Maps Codeforces language names → file extensions
LANG_EXT = {
    "GNU G++17 7.3.0":        "cpp",
    "GNU G++17 9.2.0 (64 bit, msys 2)": "cpp",
    "GNU G++20 11.2.0 (64 bit)": "cpp",
    "GNU G++14 6.4.0":        "cpp",
    "GNU G++17 7.3.0":        "cpp",
    "Clang++17 Diagnostics":  "cpp",
    "Python 3.8.3":           "py",
    "Python 3.11 (64)":       "py",
    "PyPy 3.9.10 (64bit)":    "py",
    "Java 17 64bit":          "java",
    "Java 11 64bit":          "java",
    "Java 8 32bit":           "java",
    "Kotlin 1.7":             "kt",
    "JavaScript V8 4.8.0":   "js",
    "C# 10":                  "cs",
    "Go 1.19.5":              "go",
    "Rust 2021":              "rs",
}

def get_extension(lang: str) -> str:
    """Return file extension for the given language string."""
    for key, ext in LANG_EXT.items():
        if key.lower() in lang.lower():
            return ext
    # fallback: try to guess from language name
    lang_lower = lang.lower()
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
    """Load submission IDs we've already committed."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            data = json.load(f)
        return set(data)
    return set()

def save_history(history: set):
    """Save updated submission history."""
    with open(HISTORY_FILE, "w") as f:
        json.dump(sorted(list(history)), f, indent=2)

def fetch_accepted_submissions(handle: str) -> list:
    """Fetch the last 100 accepted submissions from Codeforces API."""
    url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count=100"
    print(f"Fetching submissions for {handle}...")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data["status"] != "OK":
            print(f"CF API error: {data.get('comment', 'unknown error')}")
            return []
        accepted = [s for s in data["result"] if s.get("verdict") == "OK"]
        print(f"Found {len(accepted)} accepted submissions")
        return accepted
    except Exception as e:
        print(f"Error fetching submissions: {e}")
        return []

def get_submission_code(handle: str, contest_id: int, submission_id: int) -> str | None:
    """Fetch the source code of a submission."""
    # Codeforces submissions are publicly viewable at this URL
    url = f"https://codeforces.com/contest/{contest_id}/submission/{submission_id}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CF-GitHub-Sync)"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        # Extract code from the <pre id="program-source-text"> tag
        content = r.text
        start_tag = '<pre id="program-source-text"'
        end_tag = '</pre>'
        start = content.find(start_tag)
        if start == -1:
            return None
        start = content.find('>', start) + 1
        end = content.find(end_tag, start)
        if end == -1:
            return None
        code = content[start:end]
        # Unescape HTML entities
        code = code.replace("&lt;",  "<")
        code = code.replace("&gt;",  ">")
        code = code.replace("&amp;", "&")
        code = code.replace("&quot;","\"")
        code = code.replace("&#39;", "'")
        return code
    except Exception as e:
        print(f"  Error fetching code for submission {submission_id}: {e}")
        return None

def save_file(filepath: str, content: str):
    """Write content to a local file, creating dirs if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    history = load_history()
    submissions = fetch_accepted_submissions(CF_HANDLE)

    new_count = 0
    for sub in submissions:
        sub_id = str(sub["id"])
        if sub_id in history:
            continue  # already saved

        contest_id   = sub.get("contestId", "gym")
        problem      = sub.get("problem", {})
        problem_index = problem.get("index", "X")
        problem_name  = problem.get("name", "Unknown").replace("/", "-").replace("\\", "-")
        lang         = sub.get("programmingLanguage", "cpp")
        ext          = get_extension(lang)

        # filename like: 1700_A_Beautiful_Array.cpp
        safe_name    = problem_name.replace(" ", "_")[:40]  # limit length
        filename     = f"{contest_id}_{problem_index}_{safe_name}.{ext}"
        filepath     = os.path.join(SUBMISSIONS_DIR, filename)

        print(f"  Fetching code for submission {sub_id} ({contest_id}{problem_index})...")
        code = get_submission_code(CF_HANDLE, contest_id, sub_id)

        if code:
            save_file(filepath, code)
            history.add(sub_id)
            new_count += 1
            print(f"  ✅ Saved: {filename}")
        else:
            print(f"  ⚠️  Could not fetch code for {sub_id}, skipping")

        time.sleep(1)  # be polite to Codeforces servers

    save_history(history)
    print(f"\nDone! Added {new_count} new submission(s).")

if __name__ == "__main__":
    main()
