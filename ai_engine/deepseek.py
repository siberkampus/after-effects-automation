# ai_engine/deepseek.py
import os
from dotenv import load_dotenv
from openai import OpenAI
from config.settings import ENV_PATH

load_dotenv(ENV_PATH)

API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not API_KEY:
    raise RuntimeError("DeepSeek API key bulunamadı. Lütfen .env dosyanızı kontrol edin.")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.deepseek.com"
)

def ask_deepseek(prompt, system_prompt=None, temperature=0.2):
    if system_prompt is None:
        system_prompt = """
        You are an expert documentary production AI.
        You specialize in documentary storytelling, historical research, scene planning, and Adobe After Effects automation.
        Always produce accurate and structured results. Never invent historical facts.
        """

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature
    )

    return response.choices[0].message.content