# ai_engine/claude_vision.py
import os
import base64
import json
import re
from anthropic import Anthropic
from dotenv import load_dotenv
from config.settings import ENV_PATH

load_dotenv(ENV_PATH)
API_KEY = os.getenv("ANTHROPIC_API_KEY")

client = Anthropic(api_key=API_KEY)

def analyze_scene_image(image_path, expected_description):
    if not os.path.exists(image_path):
        return {"success": False, "reason": "Görsel dosyası bulunamadı."}

    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

    prompt = f"""
    You are a cinematic quality inspector. 
    I have generated an After Effects scene. The expected visual description was:
    "{expected_description}"

    Look at the provided image. Does it look professional and match the description?
    
    CRITICAL: Return ONLY a valid JSON object. 
    If false, explain the main problem in ONE SHORT SENTENCE. Do not write long paragraphs.
    
    {{
        "success": true/false,
        "reason": "Short reason here"
    }}
    """

    try:
        response = client.messages.create(
            model="claude-opus-5-5",
            max_tokens=1000, # Token limitini artırdık
            system="You are an expert After Effects inspector. Return ONLY valid JSON.",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": encoded_string}}
                    ]
                }
            ]
        )
        
        result_text = ""
        for block in response.content:
            if getattr(block, "type", "") == "text":
                result_text += block.text
        
        result_text = re.sub(r"^```(?:json)?\s*", "", result_text.strip())
        result_text = re.sub(r"\s*```$", "", result_text)
        
        # Eğer JSON hala bozuksa, basit bir Regex ile kurtarmayı dene
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"success": False, "reason": "Claude geçersiz JSON döndürdü."}
        
    except Exception as e:
        return {"success": False, "reason": f"Claude API Hatası: {str(e)}"}