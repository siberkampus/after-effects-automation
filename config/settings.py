# config/settings.py
import os
import glob

# Ana Proje Dizini
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Klasör Yolları
PLANS_DIR = os.path.join(PROJECT_DIR, "Plans")
ASSETS_DIR = os.path.join(PROJECT_DIR, "Assets", "Images")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "Scripts")
EXPORTS_DIR = os.path.join(PROJECT_DIR, "Exports")
PROJECTS_DIR = os.path.join(PROJECT_DIR, "Projects")

# Dosya Yolları
SCRIPT_PATH = os.path.join(PROJECT_DIR, "input_script.txt")
PLAN_PATH = os.path.join(PLANS_DIR, "scene_plan.json")
MANIFEST_PATH = os.path.join(PLANS_DIR, "image_manifest.json")
ENV_PATH = os.path.join(PROJECT_DIR, ".env")
AEP_PATH = os.path.join(PROJECTS_DIR, "documentary_project.aep")

# Video Ayarları
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

# --- AKILLI RENDER YOLU BULUCU ---
def find_aerender():
    search_pattern = r"C:\Program Files\Adobe\Adobe After Effects *\Support Files\aerender.exe"
    found_paths = glob.glob(search_pattern)
    if found_paths:
        return sorted(found_paths)[-1]
    return r"C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\aerender.exe"

AE_RENDER_PATH = find_aerender()