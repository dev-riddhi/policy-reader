# 🔍 Privacy Policy Analyzer

> Paste any website URL — Playwright fetches the privacy policy — Gemini explains the risks.

## Quick Start

```powershell
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright's Chromium browser (one-time, ~150 MB)
playwright install chromium

# 4. Set your Gemini API key in the .env file
$env:GEMINI_API_KEY = "AIza..."

# 5. Run
streamlit run app.py
```

## Project Structure

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI — input, display, error handling |
| `scraper.py` | Playwright scraper — find & extract policy text |
| `summarizer.py` | Gemini AI — structured risk analysis |
| `requirements.txt` | Python dependencies |
| `.env.example` | API key template |

## Features

- 🌐 **Auto-discovery** — give it any homepage, it finds the privacy policy link
- ⚡ **JS rendering** — Playwright handles SPAs and dynamic pages
- 🤖 **Gemini analysis** — data collection, third-party sharing, cookies, user rights, risk level
- 💾 **Disk cache** — identical policies are never re-analysed
- ✂️ **Smart truncation** — very long policies are trimmed to stay within token limits
- 📋 **Structured output** — risk badge, bullet-point cards, suspicious clause highlighting

## Get a Free Gemini API Key

👉 https://aistudio.google.com/app/apikey
