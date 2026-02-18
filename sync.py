import os
import re
import json
import time
import requests
from urllib.parse import urlencode

# ── Configuration ────────────────────────────────────────────────────────────
CF_HANDLE   = os.environ["CF_HANDLE"]    # your Codeforces handle
CF_PASSWORD = os.environ["CF_PASSWORD"]  # your Codeforces password  ← NEW
GH_TOKEN    = os.environ["GH_TOKEN"]     # your GitHub token
GH_REPO     = os.environ["GH_REPO"]     # e.g. "username/repo-name"

HISTORY_FILE    = "submission_history.json"
SUBMISSIONS_DIR = "submissions"

# Maps Codeforces language names → file extensions
LANG_EXT = {
    "gnu g++20 11.2.0 (64 bit)": "cpp",
    "gnu g++17 7.3.0":           "cpp",
    "gnu g++17 9.2.0 (64 bit, msys 2)": "cpp",
    "gnu g++14 6.4.0":           "cpp",
    "clang++17 diagnostics":     "cpp",
    "python 3.8.3":              "py",
    "python 3.11 (64)":          "py",
    "pypy 3.9.10 (64bit)":       "py",
    "java 17 64bit":             "java",
    "java 11 64bit":             "java",
    "java 8 32bit":              "java",
    "kotlin 1.7":                "kt",
    "javascript v8 4.8.0":       "js",
    "c# 10":                     "cs",
    "go 1.19.5":                 "go",
    "rust 2021":                 "rs",
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
            data = json.load(f)
        return set(str(x) for x in data)
    return set()

def save_history(history: set):
    with open(HISTORY_FILE, "w") as f:
        json.dump(sorted(list(history)), f, indent=2)

def cf_login(session: requests.Session, handle: str, password: str) -> bool:
    """Log into Codeforces using handle + password. Returns True on success."""
    login_url = "https://codeforces.com/enter"
    print("Logging into Codeforces...")

    # Step 1: GET the login page to grab the CSRF token
    r = session.get(login_url, timeout=15)
    if r.status_code != 200:
        print(f"  Failed to load login page: HTTP {r.status_code}")
        return False

    # Extract CSRF token from the page
    csrf_match = re.search(r'csrf_token" value="([^"]+)"', r.text)
    if not csrf_match:
        # Try alternative pattern
        csrf_match = re.search(r"'X-Csrf-Token'\s*:\s*'([^']+)'", r.text)
    if not csrf_match:
        print("  Could not find CSRF token on login page.")
        return False
    csrf_token = csrf_match.group(1)

    # Step 2: POST credentials
    payload = {
        "csrf_token":  csrf_token,
        "action":      "enter",
        "ftaa":        "",
        "bfaa":        "",
        "handleOrEmail": handle,
        "password":    password,
        "remember":    "on",
        "_tta":        "176",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CF-GitHub-Sync/2.0)",
        "Referer":    login_url,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    r2 = session.post(login_url, data=payload, headers=headers, timeout=15)

    # If we're no longer on /enter, login succeeded
    if "enter" not in r2.url and r2.status_code == 200:
        print("  ✅ Logged in successfully.")
        return True

    # Double-check by looking for the handle in the page
    if handle.lower() in r2.text.lower() and "logout" in r2.text.lower():
        print("  ✅ Logged in successfully.")
        return True

    print("  ❌ Login failed. Check CF_HANDLE and CF_PASSWORD secrets.")
    return False

def fetch_accepted_submissions(handle: str, count: int = 10000) -> list:
    """Fetch all accepted submissions from Codeforces API (up to `count`)."""
    url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count={count}"
    print(f"Fetching submissions for {handle}...")
    try:
        r = requests.get(url, timeout=30)
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

def get_submission_code(session: requests.Session, contest_id, submission_id: int) -> str | None:
    """Fetch source code of a submission using an authenticated session."""
    url = f"https://codeforces.com/contest/{contest_id}/submission/{submission_id}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CF-GitHub-Sync/2.0)"}
    try:
        r = session.get(url, headers=headers, timeout=15)
        content = r.text

        # Primary: <pre id="program-source-text" ...>CODE</pre>
        start_tag = '<pre id="program-source-text"'
        start = content.find(start_tag)
        if start != -1:
            start = content.find('>', start) + 1
            end   = content.find('</pre>', start)
            if end != -1:
                code = content[start:end]
                code = unescape(code)
                return code

        # Fallback: some contest types use a different class
        alt_match = re.search(
            r'<pre[^>]+class="[^"]*prettyprint[^"]*"[^>]*>(.*?)</pre>',
            content, re.DOTALL
        )
        if alt_match:
            return unescape(alt_match.group(1))

        print(f"    Could not find source code in page (possibly not logged in?)")
        return None
    except Exception as e:
        print(f"    Error fetching code for submission {submission_id}: {e}")
        return None

def unescape(html: str) -> str:
    return (html
        .replace("&lt;",   "<")
        .replace("&gt;",   ">")
        .replace("&amp;",  "&")
        .replace("&quot;", '"')
        .replace("&#39;",  "'")
        .replace("&#x27;", "'")
        .replace("&#x2F;", "/")
    )

def save_file(filepath: str, content: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    history     = load_history()
    submissions = fetch_accepted_submissions(CF_HANDLE)

    # Authenticate with Codeforces so we can read submission source code
    session = requests.Session()
    logged_in = cf_login(session, CF_HANDLE, CF_PASSWORD)
    if not logged_in:
        print("Aborting: cannot fetch source code without login.")
        raise SystemExit(1)

    new_count = 0
    for sub in submissions:
        sub_id = str(sub["id"])
        if sub_id in history:
            continue  # already saved

        contest_id    = sub.get("contestId", "gym")
        problem       = sub.get("problem", {})
        problem_index = problem.get("index", "X")
        problem_name  = (problem.get("name", "Unknown")
                         .replace("/", "-")
                         .replace("\\", "-")
                         .replace(":", "-")
                         .replace("*", "-")
                         .replace("?", "")
                         .replace('"', "")
                         .replace("<", "")
                         .replace(">", "")
                         .replace("|", "-"))
        lang          = sub.get("programmingLanguage", "cpp")
        ext           = get_extension(lang)

        safe_name = problem_name.replace(" ", "_")[:40]
        filename  = f"{contest_id}_{problem_index}_{safe_name}.{ext}"
        filepath  = os.path.join(SUBMISSIONS_DIR, filename)

        # Skip if file already exists on disk (e.g. history file was lost)
        if os.path.exists(filepath):
            history.add(sub_id)
            continue

        print(f"  Fetching code for submission {sub_id} ({contest_id}{problem_index} - {problem_name})...")
        code = get_submission_code(session, contest_id, sub_id)

        if code:
            save_file(filepath, code)
            history.add(sub_id)
            new_count += 1
            print(f"    ✅ Saved: {filename}")
        else:
            print(f"    ⚠️  Could not fetch code for {sub_id}, skipping")

        time.sleep(1.5)  # be polite to Codeforces servers

    save_history(history)
    print(f"\nDone! Added {new_count} new submission(s).")

if __name__ == "__main__":
    main()
