import asyncio
import logging
import os
import re
import tempfile
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

from database import Database
from gemini_helper import GeminiHelper, GeminiUnavailableError
from pdf_helper import extract_pdf_text, create_history_pdf

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger("last_ai_bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
MAX_PDF_MB = int(os.getenv("MAX_PDF_MB", "15"))
MAX_PDF_CHARS = int(os.getenv("MAX_PDF_CHARS", "50000"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "user_uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

db = Database(os.getenv("DB_PATH", "bot_history.db"))
ai = GeminiHelper()


def user_id(update: Update) -> int:
    return update.effective_user.id


async def send_long_text(message, text: str, limit: int = 3900):
    text = (text or "").strip()
    if not text:
        text = "मुझे इस बार कोई टेक्स्ट जवाब नहीं मिला।"
    for start in range(0, len(text), limit):
        await message.reply_text(text[start:start + limit])


async def ask_and_save(update: Update, prompt: str, feature: str = "chat",
                       extra_context: str = "", attachment_parts=None):
    uid = user_id(update)
    user = update.effective_user
    language = db.get_language(uid)
    history = db.get_recent_messages(uid, limit=10)
    pdf_context = db.get_active_pdf(uid)
    context_parts = []
    if extra_context:
        context_parts.append(extra_context)
    if pdf_context and feature in ("chat", "pdf"):
        context_parts.append(
            "USER'S CURRENT PDF SOURCE (use only if relevant):\n" +
            pdf_context[:MAX_PDF_CHARS]
        )
    full_prompt = prompt
    if context_parts:
        full_prompt = "\n\n".join(context_parts) + "\n\nUSER QUESTION:\n" + prompt

    await update.effective_chat.send_action(ChatAction.TYPING)
    try:
        answer = await asyncio.to_thread(
            ai.generate_text,
            full_prompt,
            history,
            language,
            attachment_parts,
        )
    except GeminiUnavailableError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except Exception:
        logger.exception("Gemini request failed")
        await update.effective_message.reply_text(
            "AI से जवाब लेते समय समस्या आई। थोड़ी देर बाद फिर कोशिश करें। "
            "अपनी API Key किसी को न भेजें।"
        )
        return

    db.add_message(uid, "user", prompt, feature)
    db.add_message(uid, "assistant", answer, feature)
    await send_long_text(update.effective_message, answer)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "नमस्ते! मैं Last-Ai Telegram Assistant हूँ।\n\n"
        "आप मुझसे कई भाषाओं में सवाल पूछ सकते हैं। PDF भेजकर उसके बारे में पूछें, "
        "YouTube लिंक से नोट्स बनवाएँ, किसी विषय के नोट्स बनाएँ और उपलब्ध "
        "Gemini image model से चित्र बनाएँ/एडिट करें।\n\n"
        "Commands:\n"
        "/notes विषय — किसी विषय के नोट्स\n"
        "/yt YouTube_URL — वीडियो से नोट्स\n"
        "/pdf सवाल — अपलोड किए PDF से सवाल\n"
        "/image prompt — चित्र बनाएँ\n"
        "/edit prompt — पहले भेजी फोटो एडिट करें\n"
        "/history — पुरानी चैट देखें\n"
        "/export_pdf — चैट/नोट्स की PDF\n"
        "/lang हिंदी — जवाब की भाषा सेट करें\n"
        "/clear_history — चैट हिस्ट्री हटाएँ\n"
        "/help — मदद\n\n"
        "PDF source के लिए पहले PDF फाइल भेजें। फोटो एडिट करने के लिए पहले फोटो भेजें, "
        "फिर /edit के साथ निर्देश लिखें।"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("उदाहरण: /notes भारत का संविधान")
        return
    prompt = (
        f"इस विषय पर साफ, व्यवस्थित और पढ़ाई के लिए उपयोगी नोट्स बनाओ: {topic}\n"
        "शीर्षक, मुख्य अवधारणाएँ, बुलेट पॉइंट, उदाहरण और अंत में छोटा सारांश दो। "
        "उपयोगकर्ता की चुनी हुई भाषा में लिखो।"
    )
    await ask_and_save(update, prompt, "notes")


async def youtube_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args).strip()
    match = re.search(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+|youtube\.com/shorts/[\w-]+)", args)
    if not match:
        await update.message.reply_text(
            "YouTube लिंक भेजें। उदाहरण:\n/yt https://www.youtube.com/watch?v=VIDEO_ID"
        )
        return
    url = match.group(0)
    extra = (
        "YouTube video source: " + url + "\n"
        "इस वीडियो की सामग्री के आधार पर विस्तृत नोट्स बनाओ। मुख्य विषय, "
        "महत्वपूर्ण बिंदु, उदाहरण, परिभाषाएँ और निष्कर्ष शामिल करो। "
        "अगर वीडियो उपलब्ध न हो या मॉडल उसे पढ़ न पाए, तो साफ बताओ; "
        "वीडियो देखे बिना तथ्य मत गढ़ो।"
    )
    await update.message.reply_text("वीडियो को समझने और नोट्स बनाने की कोशिश कर रहा हूँ…")
    try:
        answer = await asyncio.to_thread(ai.summarize_youtube, url, db.get_language(user_id(update)))
        db.add_message(user_id(update), "user", f"YouTube notes: {url}", "youtube")
        db.add_message(user_id(update), "assistant", answer, "youtube")
        await send_long_text(update.message, answer)
    except GeminiUnavailableError as exc:
        await update.message.reply_text(str(exc))
    except Exception:
        logger.exception("YouTube summarization failed")
        await update.message.reply_text(
            "YouTube वीडियो प्रोसेस नहीं हो पाया। वीडियो Public होना चाहिए और "
            "आपके Gemini मॉडल/API में YouTube URL input समर्थित होना चाहिए।"
        )


async def pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = " ".join(context.args).strip()
    source = db.get_active_pdf(user_id(update))
    if not source:
        await update.message.reply_text("पहले इस चैट में PDF फाइल भेजें, फिर /pdf के बाद अपना सवाल लिखें।")
        return
    if not question:
        question = "इस PDF का सारांश, मुख्य बिंदु और महत्वपूर्ण शब्द समझाओ।"
    await ask_and_save(update, question, "pdf")


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or (doc.mime_type != "application/pdf" and not doc.file_name.lower().endswith(".pdf")):
        await update.message.reply_text("कृपया PDF फाइल भेजें।")
        return
    if doc.file_size and doc.file_size > MAX_PDF_MB * 1024 * 1024:
        await update.message.reply_text(f"PDF बहुत बड़ी है। अधिकतम आकार {MAX_PDF_MB} MB रखें।")
        return

    await update.message.reply_text("PDF पढ़ रहा हूँ…")
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            temp_path = Path(tmp.name)
        try:
            await tg_file.download_to_drive(custom_path=temp_path)
            extracted = await asyncio.to_thread(extract_pdf_text, temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

        extracted = extracted[:MAX_PDF_CHARS]
        if not extracted.strip():
            await update.message.reply_text(
                "इस PDF से selectable text नहीं मिला। यह scanned/image PDF हो सकती है। "
                "इस संस्करण में OCR शामिल नहीं है।"
            )
            return
        db.set_active_pdf(user_id(update), doc.file_name or "uploaded.pdf", extracted)
        db.add_message(user_id(update), "user", f"PDF uploaded: {doc.file_name}", "pdf_upload")
        await update.message.reply_text(
            f"PDF पढ़ ली गई: {doc.file_name}\n"
            f"लगभग {len(extracted)} characters उपलब्ध हैं।\n\n"
            "अब पूछें, उदाहरण: /pdf इस PDF के 5 मुख्य बिंदु बताओ"
        )
    except Exception:
        logger.exception("PDF processing failed")
        await update.message.reply_text("PDF पढ़ने में समस्या आई। कृपया दूसरी PDF आज़माएँ।")


async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text("उदाहरण: /image बारिश में पहाड़ों का सुंदर illustration")
        return
    await update.message.reply_text("चित्र बनाने की कोशिश कर रहा हूँ…")
    try:
        image_bytes, caption = await asyncio.to_thread(ai.generate_image, prompt)
        db.add_message(user_id(update), "user", "/image " + prompt, "image")
        db.add_message(user_id(update), "assistant", caption or "Image generated", "image")
        bio = BytesIO(image_bytes)
        bio.name = "last_ai_image.png"
        await update.message.reply_photo(photo=bio, caption=(caption or "आपका चित्र तैयार है")[:900])
    except GeminiUnavailableError as exc:
        await update.message.reply_text(str(exc))
    except Exception:
        logger.exception("Image generation failed")
        await update.message.reply_text(
            "Image generation उपलब्ध नहीं हुई। आपके Gemini API plan/model में image output "
            "होना जरूरी है; यह सुविधा हर Free Tier key पर उपलब्ध नहीं हो सकती।"
        )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    folder = UPLOAD_DIR / str(user_id(update))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "last_photo.jpg"
    await tg_file.download_to_drive(custom_path=path)
    await update.message.reply_text(
        "फोटो मिल गई। अब निर्देश भेजें:\n/edit इस फोटो को watercolor art में बदलो\n"
        "या /edit background को समुद्र किनारे जैसा बनाओ"
    )


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args).strip()
    path = UPLOAD_DIR / str(user_id(update)) / "last_photo.jpg"
    if not path.exists():
        await update.message.reply_text("पहले वह फोटो भेजें जिसे एडिट करना है।")
        return
    if not prompt:
        await update.message.reply_text("उदाहरण: /edit इस फोटो को पेंटिंग स्टाइल में बदलो")
        return
    await update.message.reply_text("फोटो एडिट करने की कोशिश कर रहा हूँ…")
    try:
        image_bytes = path.read_bytes()
        result, caption = await asyncio.to_thread(ai.edit_image, image_bytes, "image/jpeg", prompt)
        db.add_message(user_id(update), "user", "/edit " + prompt, "image_edit")
        db.add_message(user_id(update), "assistant", caption or "Image edited", "image_edit")
        bio = BytesIO(result)
        bio.name = "last_ai_edited.png"
        await update.message.reply_photo(photo=bio, caption=(caption or "एडिट की गई फोटो")[:900])
    except GeminiUnavailableError as exc:
        await update.message.reply_text(str(exc))
    except Exception:
        logger.exception("Image edit failed")
        await update.message.reply_text(
            "फोटो एडिट नहीं हो पाई। जाँचें कि आपके Gemini API मॉडल में image editing "
            "और image output समर्थित है।"
        )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.get_recent_messages(user_id(update), limit=20)
    if not rows:
        await update.message.reply_text("अभी कोई चैट हिस्ट्री नहीं है।")
        return
    lines = ["आपकी हाल की चैट (सबसे नई पहले):"]
    for row in rows:
        role = "आप" if row["role"] == "user" else "Last-Ai"
        content = row["content"].replace("\n", " ")
        lines.append(f"\n[{row['created_at']}] {role}: {content[:220]}")
    await send_long_text(update.message, "\n".join(lines))


async def export_pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.get_all_messages(user_id(update))
    if not rows:
        await update.message.reply_text("PDF बनाने के लिए पहले कुछ चैट या नोट्स बनाएं।")
        return
    try:
        pdf_bytes = await asyncio.to_thread(create_history_pdf, rows, "Last-Ai Chat & Notes")
        bio = BytesIO(pdf_bytes)
        bio.name = "last_ai_history.pdf"
        await update.message.reply_document(document=bio, caption="आपकी चैट और नोट्स की PDF तैयार है।")
    except Exception:
        logger.exception("PDF export failed")
        await update.message.reply_text("PDF बनाने में समस्या आई।")


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = " ".join(context.args).strip()
    if not language:
        await update.message.reply_text("उदाहरण: /lang हिंदी  या  /lang English")
        return
    db.set_language(user_id(update), language)
    await update.message.reply_text(f"ठीक है। अब जवाब की पसंदीदा भाषा: {language}")


async def clear_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.clear_user(user_id(update))
    await update.message.reply_text("आपकी चैट हिस्ट्री और सेव किया हुआ PDF source हटा दिया गया है।")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return
    await ask_and_save(update, text, "chat")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled bot error: %s", context.error)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN .env में सेट करें।")
    if not os.getenv("GEMINI_API_KEY", "").strip():
        raise SystemExit("GEMINI_API_KEY .env में सेट करें।")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("yt", youtube_command))
    app.add_handler(CommandHandler("pdf", pdf_command))
    app.add_handler(CommandHandler("image", image_command))
    app.add_handler(CommandHandler("edit", edit_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("export_pdf", export_pdf_command))
    app.add_handler(CommandHandler("lang", language_command))
    app.add_handler(CommandHandler("clear_history", clear_history_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    logger.info("Last-Ai bot starting with long polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
