import os
import sys
import json
from ai_engine.scene_planner import create_scene_plan
from ai_engine.image_finder import find_images
from ai_engine.jsx_generator import generate_jsx_files
from config.settings import PLAN_PATH, PLANS_DIR

def main():
    print("="*50)
    print("BELGESEL OTOMASYON SİSTEMİ BAŞLIYOR")
    print("="*50)

    try:
        # 1. Aşama: Senaryoyu Sahnelere Böl (scene_plan.json oluşur)
        print("\n[1/3] Senaryo analiz ediliyor ve sahne planı oluşturuluyor...")
        create_scene_plan()

        # 2. Aşama: Görselleri Bul ve İndir (image_manifest.json oluşur)
        print("\n[2/3] Sahneler için görseller aranıyor ve indiriliyor...")
        find_images()

        # 3. Aşama: After Effects (JSX) komut dosyalarını üret (Şablonlar oluşur)
        print("\n[3/3] After Effects (JSX) komut dosyaları üretiliyor...")
        generate_jsx_files()

        print("\n" + "="*50)
        print("İLK AŞAMA TAMAMLANDI!")
        print(f"Sahne planı hazır: {PLAN_PATH}")
        print("Şimdi 'python ai_director.py' komutunu çalıştırabilirsiniz.")
        print("="*50)

    except Exception as e:
        print(f"\n[HATA] Sistem çalışırken bir sorun oluştu: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()