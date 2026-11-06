# ai_engine/claude_vision.py
"""Optional visual QA. This module is imported only when AE_ENABLE_CLAUDE_QA=1."""
import os
import base64
import json
import re
from dotenv import load_dotenv
from anthropic import Anthropic
from config.settings import ENV_PATH

load_dotenv(ENV_PATH)


def analyze_scene_image(image_path, expected_description):
    if not os.path.isfile(image_path):
        return {"success": False, "reason": "Görsel dosyası bulunamadı."}
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"success": False, "reason": "ANTHROPIC_API_KEY tanımlı değil; QA atlandı."}

    ext = os.path.splitext(image_path)[1].lower()
    media_type = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")

    prompt = f"""
Inspect this After Effects frame as a senior motion-graphics art director.
Expected scene: {expected_description}

Judge composition, visual hierarchy, legibility, palette, and whether the motion-graphics
elements communicate the scene. Do not reject a scene for minor stylistic preferences.
Return only JSON: {{"success": true/false, "reason": "one concise sentence"}}.
"""
    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=os.getenv("ANTHROPIC_VISION_MODEL", "claude-opus-5-5"),
            max_tokens=250,
            system="You are a concise visual QA inspector. Return valid JSON only.",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "source": {
                        "type": "base64", "media_type": media_type, "data": encoded
                    }},
                ],
            }],
        )
        result_text = "".join(
            block.text for block in response.content
            if getattr(block, "type", "") == "text"
        ).strip()
        result_text = re.sub(r"^\\x60\\x60\\x60(?:json)?\\s*", "", result_text)
        result_text = re.sub(r"\\s*\\x60\\x60\\x60$", "", result_text)
        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            match = re.search(r"\\{.*\\}", result_text, re.DOTALL)
            if not match:
                return {"success": False, "reason": "Claude geçersiz JSON döndürdü."}
            data = json.loads(match.group(0))
        return {
            "success": bool(data.get("success")),
            "reason": str(data.get("reason", "QA tamamlandı."))[:300],
        }
    except Exception as exc:
        return {"success": False, "reason": f"Claude API hatası: {exc}"}
