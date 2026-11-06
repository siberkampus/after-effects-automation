"""Prepare a scene plan, then run the After Effects pipeline.

Cost controls:
- Existing scene_plan.json is reused by default. Set REGENERATE_SCENE_PLAN=1 to call DeepSeek.
- HUD/FUI scenes use native vector layers; Wikimedia image search and legacy JSX generation are skipped.
- Documentary mode retains the image-search + JSX workflow.
"""
import json
import os
import sys

from ai_engine.scene_planner import create_scene_plan
from ai_engine.image_finder import find_images
from ai_engine.jsx_generator import generate_jsx_files
from config.settings import PLAN_PATH, PLANS_DIR


def main():
    print("=" * 58)
    print("AFTER EFFECTS AUTOMATION - PREPARATION")
    print("=" * 58)
    os.makedirs(PLANS_DIR, exist_ok=True)

    regenerate = os.getenv("REGENERATE_SCENE_PLAN", "0").lower() in {"1", "true", "yes"}
    if not os.path.isfile(PLAN_PATH) or regenerate:
        print("\\n[1/3] DeepSeek ile sahne planı oluşturuluyor...")
        create_scene_plan()
    else:
        print("\\n[1/3] Mevcut scene_plan.json kullanılıyor (DeepSeek çağrısı yok).")

    with open(PLAN_PATH, "r", encoding="utf-8") as file:
        plan = json.load(file)
    mode = str(plan.get("production_mode", "documentary")).lower()

    if mode == "hud_fui":
        print("[2/3] HUD/FUI modu: dış görsel araması atlandı; tasarım AE vektör katmanlarıyla üretilecek.")
        print("[3/3] HUD/FUI modu: eski JSX şablon üreticisi atlandı.")
        print("\\nHazır. Şimdi 'python ai_director.py' çalıştırın.")
        print("Not: ai_director.py sahne başına DeepSeek/Claude çağırmaz; Claude QA isteğe bağlıdır.")
        return

    print("\\n[2/3] Belgesel sahneleri için görseller aranıyor...")
    find_images()
    print("\\n[3/3] Legacy JSX şablonları oluşturuluyor...")
    generate_jsx_files()
    print("\\nHazır. Sonraki adım: 'python ai_director.py'.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\\n[HATA] Hazırlık başarısız: {exc}")
        sys.exit(1)
