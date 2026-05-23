# Characterizing Suspicious Commenter Behaviors

This project contains :
- `api.py` — stores your private YouTube API key.
- `pipeline.py` — all analysis stages in one reusable module.
- `gui.py` — Tkinter user interface to run the pipeline.

## What it does
- Fetches YouTube comments.
- Flags accounts by comment frequency.
- Detects spam patterns and bursty posting behavior.
- Builds a similarity graph to identify bot-like clusters.

## Setup
1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install the YouTube API client:
   ```bash
   python3 -m pip install google-api-python-client
   ```
3. Put your API key in `api.py`:
   ```python
   API_KEY = "YOUR_API_KEY"
   ```

## Run
- GUI:
  ```bash
  python3 gui.py
  ```
- Pipeline CLI:
  ```bash
  python3 pipeline.py VIDEO_ID 1000
  ```

## Notes
- Maximum comments to fetch is `10000`.
- `api.py` is excluded from Git via `.gitignore`.
