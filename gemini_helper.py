import os
from io import BytesIO
from typing import Optional

from google import genai
from google.genai import types


class GeminiUnavailableError(RuntimeError):
    pass


class GeminiHelper:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)
        self.text_model = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
        self.image_model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

    def _require_client(self):
        if self.client is None:
            raise GeminiUnavailableError("GEMINI_API_KEY सेट नहीं है। .env फाइल जाँचें।")

    @staticmethod
    def _language_instruction(language: str) -> str:
        if language and language.lower() not in ("auto", "automatic", "default"):
            lang = language
        else:
            lang = "उपयोगकर्ता की भाषा"
        return (
            "You are Last-Ai, a helpful, accurate, multilingual assistant. "
            "Reply in " + lang + ". If the user writes in a different language, "
            "understand it and follow their explicit language preference. "
            "Be honest about uncertainty; do not invent facts, video contents, citations, "
            "or file contents. Keep answers clear and age-appropriate."
        )

    def generate_text(self, prompt: str, history=None, language="auto", attachment_parts=None) -> str:
        self._require_client()
        contents = []
        for item in (history or [])[-10:]:
            role = "model" if item["role"] == "assistant" else "user"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=item["content"][:5000])]
            ))
        parts = [types.Part.from_text(text=prompt)]
        if attachment_parts:
            parts.extend(attachment_parts)
        contents.append(types.Content(role="user", parts=parts))
        response = self.client.models.generate_content(
            model=self.text_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=self._language_instruction(language),
                temperature=0.6,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini ने text response नहीं लौटाया।")
        return text.strip()

    def summarize_youtube(self, url: str, language="auto") -> str:
        self._require_client()
        # Gemini API supports a public YouTube URL as a video FileData part
        # on supported models/accounts. This is not the same as pasting a URL
        # into plain text, which may not cause the video to be processed.
        video_part = types.Part.from_uri(file_uri=url, mime_type="video/mp4")
        prompt = (
            "इस YouTube वीडियो को देखकर/सुनकर विस्तृत अध्ययन नोट्स बनाओ। "
            "वीडियो के वास्तविक विषय, क्रम, मुख्य विचार, उदाहरण, परिभाषाएँ और निष्कर्ष लिखो। "
            "जहाँ संभव हो timestamps भी दो। अगर वीडियो तक पहुँच नहीं है तो स्पष्ट बताओ "
            "और अनुमान से नोट्स मत बनाओ।"
        )
        response = self.client.models.generate_content(
            model=self.text_model,
            contents=[
                types.Content(role="user", parts=[
                    types.Part.from_text(text=prompt),
                    video_part,
                ])
            ],
            config=types.GenerateContentConfig(
                system_instruction=self._language_instruction(language),
                temperature=0.4,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("वीडियो से कोई टेक्स्ट जवाब नहीं मिला।")
        return text.strip()

    def generate_image(self, prompt: str):
        self._require_client()
        response = self.client.models.generate_content(
            model=self.image_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )
        image_data = None
        caption = ""
        for candidate in (response.candidates or []):
            for part in (candidate.content.parts or []):
                if getattr(part, "text", None):
                    caption += part.text + "\n"
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    image_data = inline.data
        if not image_data:
            raise GeminiUnavailableError(
                f"मॉडल {self.image_model} ने image output नहीं दिया। "
                "इस API key/plan पर image generation उपलब्ध न हो सकती है।"
            )
        return image_data, caption.strip()

    def edit_image(self, image_bytes: bytes, mime_type: str, prompt: str):
        self._require_client()
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = self.client.models.generate_content(
            model=self.image_model,
            contents=[
                types.Content(role="user", parts=[
                    image_part,
                    types.Part.from_text(text=(
                        "इस दी गई तस्वीर को उपयोगकर्ता के निर्देश के अनुसार एडिट करो। "
                        "जहाँ निर्देश न हो वहाँ मुख्य विषय की पहचान/रूप को यथासंभव बनाए रखो। "
                        + prompt
                    )),
                ])
            ],
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        image_data = None
        caption = ""
        for candidate in (response.candidates or []):
            for part in (candidate.content.parts or []):
                if getattr(part, "text", None):
                    caption += part.text + "\n"
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    image_data = inline.data
        if not image_data:
            raise GeminiUnavailableError(
                f"मॉडल {self.image_model} ने edited image नहीं लौटाई। "
                "आपके API plan/model में image editing समर्थित होना चाहिए।"
            )
        return image_data, caption.strip()
