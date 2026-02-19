# 🟢 Codeforces Solutions

Auto-synced Codeforces accepted submissions for **[Lyraen](https://codeforces.com/profile/Lyraen)** — organized, backed up, and easy to revisit.

Every accepted solution is automatically saved here using [`sync.py`](./sync.py), a local Python script that pulls submissions directly from Codeforces and commits them to this repo.

---

## 📁 Structure

```
submissions/
├── 1877_A_Goals_of_Victory.cpp
├── 1881_A_Don't_Try_to_Count.cpp
├── 2162_A_Beautiful_Average.cpp
└── ...
```

Files are named as `{contestId}_{problemIndex}_{problemName}.{ext}` — making them easy to search and browse.

---

## ⚙️ How It Works

Codeforces doesn't expose submission source code through their API — it's only accessible on their website while logged in. Cloud servers (like GitHub Actions) are also IP-blocked by Codeforces, so fully automated pipelines don't work.

The solution: run `sync.py` **locally** from your own machine.

```
your machine
    │
    ├── calls CF public API → gets list of accepted submissions
    ├── logs into codeforces.com → fetches source code from each submission page
    ├── saves files to submissions/
    └── git commits + pushes to this repo
```

---

## 🚀 Use This Yourself

Want to auto-sync your own Codeforces solutions to GitHub? Here's how.

### 1. Clone this repo (or fork it)

```bash
git clone https://github.com/GitDaksh/codeforces-solutions.git
cd codeforces-solutions
```

### 2. Install the dependency

```bash
pip install requests
```

### 3. Set your handle

Open `sync.py` and change this line at the top:

```python
CF_HANDLE = "Lyraen"   # ← replace with your CF handle
```

### 4. Run it

```bash
python sync.py
```

You'll be prompted to enter your Codeforces password — it's used only for the login request and is **never stored anywhere**.

### 5. Run it again after every contest

The script tracks which submissions it's already saved in `submission_history.json`. Re-running it will only fetch new solutions — nothing is duplicated.

---

## ✅ Features

- Fetches all accepted submissions via the Codeforces public API
- Deduplicates — saves only the latest accepted submission per problem
- Supports C++, Python, Java, Kotlin, Rust, Go, C#, JavaScript, and more
- Sanitizes filenames (no invalid characters)
- Skips already-saved submissions via a local history file
- Automatically commits and pushes to GitHub

---

## 🔒 Security Notes

- Your CF password is entered at runtime and **never written to disk**
- Your GitHub credentials use standard `git push` — no tokens are hardcoded
- `submission_history.json` contains only submission IDs, nothing sensitive

---

## 🌐 Why Not GitHub Actions?

The obvious approach is a scheduled GitHub Actions workflow. It doesn't work because:

1. **Codeforces blocks all cloud/datacenter IPs** — GitHub Actions runs on Azure, and CF returns HTTP 403 before the login page even loads
2. **The CF API has no source code endpoint** — submission source is only accessible on the website, behind authentication

Running locally sidesteps both problems cleanly.

---

## 📜 License

MIT — do whatever you want with it.
