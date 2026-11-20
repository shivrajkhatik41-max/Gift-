
# Last-Ai Telegram Bot

A starter Telegram assistant bot using the Telegram Bot API and Google Gemini API.

## Included features

- Multilingual chat (the model's language capability and API limits apply)
- `/notes TOPIC` — study notes on a topic
- `/yt YOUTUBE_URL` — notes from a public YouTube video, if the selected Gemini model/API supports YouTube URL input
- Upload a text-based PDF, then ask questions with `/pdf QUESTION`
- `/image PROMPT` — image generation (requires an image-capable Gemini model/API access)
- Send a photo, then `/edit PROMPT` — image editing (requires image input/output support)
- `/history` — recent messages
- `/export_pdf` — export saved chat/notes as a PDF
- `/lang LANGUAGE` — set preferred reply language
- `/clear_history` — clear chat history and current PDF source
- SQLite history stored locally in `bot_history.db`

## Important: free usage is limited

This project code is free/open-source style starter code, but external API usage is controlled by Google and Telegram. Gemini Free Tier limits, model access, regional availability and billing rules can change. Image generation/editing may not be included in every free API account. YouTube URL input also depends on model/API support and public video availability. The bot cannot promise unlimited or permanently free AI usage.

Do not enable paid billing if your budget is strictly ₹0. Check your Google AI Studio API usage and limits before using the bot heavily.

## Requirements

- Python 3.10 or newer (Python 3.11 recommended)
- A Telegram bot token from Telegram's official BotFather
- A Gemini API key from Google AI Studio
- Internet connection

Never paste your Telegram token or Gemini key into a chat, source code, screenshot, or public GitHub repository.

## 1. Configure the keys

1. Extract the ZIP.
2. Copy `.env.example` to a new file named `.env`.
3. Open `.env` in a text editor.
4. Set:
   - `TELEGRAM_BOT_TOKEN` to your bot token
   - `GEMINI_API_KEY` to your Gemini API key
5. Save `.env`.

Do not rename `.env.example` instead of making a private `.env` copy if you want to keep the template.

## 2. Run on a computer

Open a terminal in the project folder:

```bash
python -m venv .venv
```

Activate it:

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Install packages and start:

```bash
pip install -r requirements.txt
python bot.py
```

Keep the terminal and computer running while you use the bot. Press Ctrl+C to stop it.

## 3. Run on Android

You can run it in a Python environment on Android, but Android may stop background processes to save battery. Keep the app/session active while testing. Exact setup steps depend on the Python terminal app and Android version.

Inside the project directory:

```bash
python -m pip install -r requirements.txt
python bot.py
```

If package installation fails on Android, test first on a computer or supported Python host.

## 4. Upload to GitHub

1. Sign in to GitHub and create a **Private** repository, for example `last-ai-telegram-bot`.
2. Upload the extracted project files and folders.
3. Do NOT upload `.env`, `bot_history.db`, personal PDFs or `user_uploads`.
4. `.gitignore` is included to help prevent accidental uploads.
5. GitHub Actions will run a syntax/dependency validation workflow.

### GitHub Actions note

`.github/workflows/run_bot.yml` validates the project when code is pushed or manually triggered. It does **not** keep the bot online. GitHub Actions jobs are temporary; they are not a permanent free server for Telegram polling. Do not treat a successful workflow run as a running bot.

For a bot that stays online, you need a host that permits a long-running process. Free hosting often sleeps, has usage caps, or changes its free plan. Check the host's current terms before deploying. Never add API keys to a public repository.

## Commands

| Command | Purpose |
|---|---|
| `/start` | Welcome and help |
| `/help` | Show help |
| `/notes TOPIC` | Create topic notes |
| `/yt URL` | Create notes from a YouTube video |
| `/pdf QUESTION` | Ask about the last uploaded PDF |
| `/image PROMPT` | Generate an image |
| `/edit PROMPT` | Edit the last photo you sent |
| `/history` | Show recent chat history |
| `/export_pdf` | Export all saved chat/notes to PDF |
| `/lang हिंदी` | Set preferred answer language |
| `/clear_history` | Delete saved history and active PDF source |

## PDF source notes

- The bot extracts selectable text from PDFs.
- Scanned PDFs that contain only page images need OCR; OCR is not included in this starter project.
- Up to 150 pages are read, and extracted context is clipped to the configured character limit.
- PDF Q&A uses the last uploaded PDF for that Telegram user.

## YouTube notes

Use:

```text
/yt https://www.youtube.com/watch?v=VIDEO_ID
```

The bot passes the YouTube URL as a video input part to Gemini. The video must be public or otherwise accessible to the API, and your selected model/account must support YouTube video input. If it cannot access the video, the bot should report that rather than inventing notes.

## Image generation and editing

- `/image a watercolor landscape with mountains`
- Send a photo, then `/edit make the background look like a watercolor garden`

Image output requires a Gemini image-capable model and account access. The default in `.env.example` is `gemini-2.5-flash-image`; Google lists this model as deprecated with a planned retirement date, so check current model availability and change `GEMINI_IMAGE_MODEL` if needed. A newer model may not be available on your free API tier.

## PDF export and Hindi font

ReportLab's built-in fonts do not cover all Indian scripts. For proper Hindi/Devanagari rendering, place a licensed Unicode font file such as `NotoSansDevanagari-Regular.ttf` in `assets/` and set `PDF_FONT_PATH` in `.env`. The project can still export PDFs without it, but Hindi glyphs may not render correctly.

## Privacy and security

- Chat history and PDF text are stored in a local SQLite database on the machine/host running the bot.
- Anyone with access to that machine/database can read this data.
- `/clear_history` removes the user's saved chat messages and current PDF source from the local database.
- Do not upload personal or sensitive documents unless you understand the privacy implications of sending their contents to an external AI service.
- Keep `.env` private. If a token is exposed, revoke/rotate it through the relevant provider.
- This is a starter project. Add authentication, backups, abuse protection and stronger file validation before public deployment.

## Troubleshooting

- `TELEGRAM_BOT_TOKEN ...`: check `.env` name and token value.
- `GEMINI_API_KEY ...`: check the key and API access.
- `model not found` or `permission denied`: check the model name and your account's model access.
- `429` / quota errors: wait for quota reset or reduce usage; do not enable paid billing if staying at ₹0.
- YouTube URL not processed: check public access and model support.
- Image not returned: your model/API tier may not allow image output.
- Bot stops when terminal closes: long polling requires the Python process to remain running.
