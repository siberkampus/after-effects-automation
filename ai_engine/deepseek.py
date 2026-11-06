# ai_engine/deepseek.py
"""Lazy DeepSeek client: importing the pipeline must not require or spend an API key."""
import os
from dotenv import load_dotenv
from openai import OpenAI
from config.settings import ENV_PATH

load_dotenv(ENV_PATH)
_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY bulunamadı. Var olan scene_plan.json kullanılabilir; "
            "yeni plan üretmek için .env dosyasına anahtar ekleyin."
        )
    _client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    return _client


def ask_deepseek(prompt, system_prompt=None, temperature=0.2, max_tokens=None):
    if system_prompt is None:
        system_prompt = (
            "You are an expert documentary production AI. "
            "Create accurate, structured outputs and never invent historical facts."
        )
    request = {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    if max_tokens is not None:
        request["max_tokens"] = int(max_tokens)
    response = _get_client().chat.completions.create(**request)
    return response.choices[0].message.content or ""
