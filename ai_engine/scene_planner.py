# ai_engine/scene_planner.py
"""Create backward-compatible documentary or HUD/FUI scene plans.

Mode selection:
    VIDEO_MODE=auto         (default; infer from script)
    VIDEO_MODE=documentary  (force documentary planning)
    VIDEO_MODE=hud_fui      (force HUD/FUI planning)

The legacy fields consumed by image_finder.py and jsx_generator.py are kept.
HUD-specific fields are additive so the existing pipeline can continue to run.
"""

import json
import os
import re
import tempfile
from typing import Any, Dict, List

from ai_engine.deepseek import ask_deepseek
from config.settings import SCRIPT_PATH, PLANS_DIR, PLAN_PATH


LEGACY_VISUAL_TYPES = {
    "historical_map",
    "historical_photo",
    "architecture",
    "landscape",
    "artifact",
    "portrait",
    "illustration",
}

LEGACY_ANIMATION_STYLES = {
    "map_reveal",
    "documentary_zoom",
    "typewriter_text",
    "parallax_slide",
    "minimalist_title",
}

HUD_COMPONENTS = {
    "circular_scanner",
    "radar_sweep",
    "technical_frame",
    "data_panel",
    "network_nodes",
    "connecting_lines",
    "target_lock",
    "crosshair",
    "waveform",
    "bar_graph",
    "progress_ring",
    "hex_grid",
    "warning_indicator",
    "status_readout",
    "digital_glitch",
    "particle_field",
}

HUD_ANIMATIONS = {
    "radar_sweep",
    "system_boot",
    "network_build",
    "target_lock_on",
    "data_stream",
    "shield_activation",
    "glitch_reveal",
    "interface_pan",
    "pulse_scan",
}

HUD_SYSTEM_PROMPT = """
You are a senior motion-graphics art director specializing in premium cyber-security
HUD/FUI (Heads-Up Display / Fictional User Interface) sequences for Adobe After Effects.
Plan scenes as if they belong to one coherent, polished film graphics package.

VISUAL LANGUAGE:
- Use a near-black/deep-navy background, thin precise strokes, restrained neon cyan,
  electric blue and occasional magenta/red accents for meaningful alerts.
- Prefer outline-only geometry (no large solid fills), nested circular instruments,
  segmented rings, radial ticks, corner brackets, crosshairs, technical frames,
  compact data panels, network diagrams and subtle grid structures.
- Build depth with multiple independently animated layers and varied scale/opacity.
- Use asymmetry and deliberate negative space; avoid random piles of circles/rectangles.
- Every component must communicate something about the narration.
- Specify a clear focal point, hierarchy, layout and motion progression for each scene.
- Keep text concise and legible. Do not invent factual statistics, IP addresses,
  threat names or technical claims that are not in the script.
- The visual plan must be feasible with vector shape, text, solid and keyframe layers.
- Keep all JSON values in English. Return valid JSON only, without Markdown.
"""

DOCUMENTARY_SYSTEM_PROMPT = """
You are an expert documentary film director and visual researcher.
Convert the script into a detailed scene production plan for Adobe After Effects.
- Divide narration into logical cinematic scenes.
- Every scene needs a specific visual description.
- Provide exactly 3 alternative English image search queries per scene.
- Prefer historically accurate visual references and do not invent historical facts.
- Keep all JSON values in English. Return valid JSON only, without Markdown.
"""


def load_script() -> str:
    if not os.path.exists(SCRIPT_PATH):
        raise FileNotFoundError("input_script.txt bulunamadı.")
    with open(SCRIPT_PATH, "r", encoding="utf-8") as file:
        script = file.read().strip()
    if not script:
        raise ValueError("input_script.txt boş.")
    return script


def extract_json(response: str) -> Dict[str, Any]:
    """Parse the first complete JSON object, tolerating a surrounding code fence."""
    if not isinstance(response, str) or not response.strip():
        raise ValueError("DeepSeek boş yanıt döndürdü.")

    cleaned = response.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char == "{":
            try:
                parsed, _ = decoder.raw_decode(cleaned[index:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    raise ValueError("DeepSeek geçerli bir JSON nesnesi döndürmedi.")


def detect_production_mode(script: str) -> str:
    """Simple transparent heuristic; VIDEO_MODE can always override it."""
    text = script.casefold()
    hud_terms = (
        "cyber", "cybersecurity", "hacker", "hack", "malware", "ransomware",
        "firewall", "network", "data breach", "data flow", "server", "encryption",
        "cryptographic", "threat", "security system", "digital attack", "intrusion",
        "database", "scan", "scanner", "radar", "protocol",
    )
    score = sum(1 for term in hud_terms if term in text)
    return "hud_fui" if score >= 2 else "documentary"


def _default_hud_queries(scene: Dict[str, Any]) -> List[str]:
    topic = str(scene.get("narration_summary") or "cyber security system").strip()
    return [
        f"abstract dark navy technology background subtle digital grid {topic}",
        "minimal cyan blue cybersecurity network visualization dark background",
        "futuristic data center digital interface background texture no text",
    ]


def _normalise_scene(scene: Dict[str, Any], index: int, mode: str) -> Dict[str, Any]:
    if not isinstance(scene, dict):
        raise ValueError(f"{index}. sahne bir JSON nesnesi değil.")

    scene.setdefault("id", index)
    try:
        scene["id"] = int(scene["id"])
    except (TypeError, ValueError):
        raise ValueError(f"{index}. sahnenin id alanı tam sayı olmalı.")

    try:
        duration = int(float(scene.get("duration_seconds", 6)))
    except (TypeError, ValueError):
        duration = 6
    if duration < 4 or duration > 8:
        print(f"[UYARI] Sahne {scene['id']} süresi 4-8 saniye aralığına çekildi.")
        duration = max(4, min(8, duration))
    scene["duration_seconds"] = duration

    scene["narration_summary"] = str(scene.get("narration_summary", "")).strip()
    scene["visual_description"] = str(scene.get("visual_description", "")).strip()
    if not scene["visual_description"]:
        raise ValueError(f"Sahne {scene['id']} için visual_description eksik.")

    queries = scene.get("image_search_queries", [])
    if not isinstance(queries, list):
        queries = []
    queries = [str(query).strip() for query in queries if str(query).strip()]
    if mode == "hud_fui" and len(queries) < 3:
        queries.extend(_default_hud_queries(scene))
    while len(queries) < 3:
        queries.append(f"{scene['visual_description']} documentary reference image")
    scene["image_search_queries"] = queries[:3]

    visual_type = str(scene.get("visual_type", "illustration")).strip().lower()
    if visual_type not in LEGACY_VISUAL_TYPES:
        visual_type = "illustration"
    # Keep visual_type in the legacy enum: image_finder.py expects a generic fallback.
    scene["visual_type"] = visual_type

    animation_style = str(scene.get("animation_style", "documentary_zoom")).strip().lower()
    if animation_style not in LEGACY_ANIMATION_STYLES:
        animation_style = "parallax_slide" if mode == "hud_fui" else "documentary_zoom"
    scene["animation_style"] = animation_style

    scene.setdefault("on_screen_text", "")

    if mode == "hud_fui":
        scene["scene_kind"] = "hud_interface"
        scene.setdefault("design_style", "cyber_security_hud")

        components = scene.get("hud_components", [])
        if not isinstance(components, list):
            components = []
        components = [str(item).strip().lower() for item in components]
        components = [item for item in components if item in HUD_COMPONENTS]
        if not components:
            components = ["technical_frame", "circular_scanner", "data_panel"]
        scene["hud_components"] = list(dict.fromkeys(components))[:7]

        scene["hud_animation"] = str(scene.get("hud_animation", "pulse_scan")).strip().lower()
        if scene["hud_animation"] not in HUD_ANIMATIONS:
            scene["hud_animation"] = "pulse_scan"

        scene["motion_intensity"] = str(scene.get("motion_intensity", "medium")).strip().lower()
        if scene["motion_intensity"] not in {"low", "medium", "high"}:
            scene["motion_intensity"] = "medium"

        scene["design_style"] = str(scene.get("design_style", "cyber_security_hud")).strip()
        scene["layout"] = str(scene.get("layout", "asymmetric_modular")).strip()
        scene.setdefault("stroke_style", {
            "fill": "none",
            "stroke_width_px": 2,
            "glow": "subtle",
        })
        scene.setdefault("color_palette", {
            "background": [3, 8, 18],
            "primary": [0, 220, 255],
            "secondary": [0, 110, 180],
            "accent": [255, 45, 145],
            "alert": [255, 55, 70],
        })
    else:
        scene["scene_kind"] = "documentary_visual"

    return scene


def build_prompt(script: str, mode: str) -> str:
    if mode == "hud_fui":
        return f"""
Create a complete scene-by-scene HUD/FUI motion-graphics plan for this script.

SCRIPT:
{script}

Return one JSON object using this structure:
{{
  "video_title": "Title",
  "production_mode": "hud_fui",
  "visual_direction": "A concise shared art direction for the whole video",
  "scenes": [
    {{
      "id": 1,
      "duration_seconds": 6,
      "narration_summary": "What this scene communicates",
      "visual_type": "illustration",
      "scene_kind": "hud_interface",
      "design_style": "cyber_security_hud",
      "visual_description": "Detailed composition, focal point, hierarchy, negative space and visual progression",
      "image_search_queries": [
        "abstract dark navy technology background subtle digital grid",
        "minimal cyan blue cybersecurity network visualization",
        "futuristic data interface background texture"
      ],
      "hud_components": ["circular_scanner", "technical_frame", "data_panel"],
      "color_palette": {{
        "background": [3, 8, 18],
        "primary": [0, 220, 255],
        "secondary": [0, 110, 180],
        "accent": [255, 45, 145],
        "alert": [255, 55, 70]
      }},
      "stroke_style": {{"fill": "none", "stroke_width_px": 2, "glow": "subtle"}},
      "layout": "asymmetric_modular",
      "motion_intensity": "medium",
      "hud_animation": "radar_sweep",
      "animation_style": "parallax_slide",
      "on_screen_text": "SYSTEM SCANNING"
    }}
  ]
}}

STRICT REQUIREMENTS:
- Split the narration into coherent visual beats; generally 4-8 seconds each.
- Keep visual_type within this legacy-compatible set: historical_map, historical_photo,
  architecture, landscape, artifact, portrait, illustration. Use illustration for HUD scenes.
- Every scene must include exactly 3 specific English image_search_queries. These are optional
  visual references; the actual HUD should be built from vector layers, not a downloaded UI image.
- hud_components may ONLY use: {", ".join(sorted(HUD_COMPONENTS))}.
- hud_animation must be one of: {", ".join(sorted(HUD_ANIMATIONS))}.
- motion_intensity must be low, medium or high.
- Keep fill as none/transparent wherever possible. Favor thin strokes, nested rings,
  radial ticks, corner brackets, fine grids and compact information panels.
- Use asymmetrical but balanced compositions. Avoid generic centered piles of circles.
- Use cyan/blue as the base; reserve red for actual threat states and magenta for rare accents.
- Define what moves, in which direction, and how the motion develops over the scene.
- The plan must be feasible with shape, solid, text and keyframe layers.
- Do not invent technical facts, metrics or labels absent from the script.
- Return JSON only.
"""

    return f"""
Create a complete scene plan for this documentary script.

DOCUMENTARY SCRIPT:
{script}

Return JSON using exactly this structure:
{{
  "video_title": "Documentary title",
  "production_mode": "documentary",
  "scenes": [
    {{
      "id": 1,
      "duration_seconds": 5,
      "narration_summary": "Summary of the narration",
      "visual_type": "historical_map",
      "visual_description": "Detailed cinematic visual description",
      "image_search_queries": ["specific query one", "specific query two", "specific query three"],
      "on_screen_text": "Optional screen title",
      "animation_style": "map_reveal"
    }}
  ]
}}

Requirements:
- Each scene should generally last 4 to 8 seconds.
- Provide exactly 3 alternative English image_search_queries per scene.
- visual_type values: {", ".join(sorted(LEGACY_VISUAL_TYPES))}.
- animation_style values: {", ".join(sorted(LEGACY_ANIMATION_STYLES))}.
- Prefer historically accurate visual references. Do not invent historical facts.
- Return JSON only.
"""


def create_scene_plan(mode: str = None) -> Dict[str, Any]:
    script = load_script()

    requested_mode = (mode or os.getenv("VIDEO_MODE", "auto")).strip().lower()
    if requested_mode == "auto":
        production_mode = detect_production_mode(script)
    elif requested_mode in {"documentary", "hud_fui"}:
        production_mode = requested_mode
    else:
        raise ValueError("VIDEO_MODE yalnızca 'auto', 'documentary' veya 'hud_fui' olabilir.")

    system_prompt = HUD_SYSTEM_PROMPT if production_mode == "hud_fui" else DOCUMENTARY_SYSTEM_PROMPT
    prompt = build_prompt(script, production_mode)

    mode_label = "HUD/FUI" if production_mode == "hud_fui" else "belgesel"
    print(f"DeepSeek'e senaryo gönderiliyor; üretim modu: {mode_label}...")
    response = ask_deepseek(prompt, system_prompt=system_prompt, temperature=0.2)
    plan = extract_json(response)

    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Sahne planı geçerli ve boş olmayan bir scenes listesi içermiyor.")

    normalised_scenes = []
    seen_ids = set()
    for index, scene in enumerate(scenes, start=1):
        scene = _normalise_scene(scene, index, production_mode)
        if scene["id"] in seen_ids:
            raise ValueError(f"Tekrarlanan sahne ID'si: {scene['id']}")
        seen_ids.add(scene["id"])
        normalised_scenes.append(scene)

    plan["scenes"] = normalised_scenes
    plan["production_mode"] = production_mode
    plan.setdefault("video_title", "Untitled Video")
    if production_mode == "hud_fui":
        plan.setdefault("visual_direction", "Premium dark cyber-security HUD with fine cyan strokes and restrained alert accents")

    plan["total_duration_seconds"] = sum(scene["duration_seconds"] for scene in normalised_scenes)

    os.makedirs(PLANS_DIR, exist_ok=True)
    # Write atomically so a failed write cannot leave a truncated scene_plan.json.
    fd, temp_path = tempfile.mkstemp(prefix="scene_plan_", suffix=".json", dir=PLANS_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(plan, file, indent=4, ensure_ascii=False)
        os.replace(temp_path, PLAN_PATH)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    print(
        f"Başarılı! {len(normalised_scenes)} sahne oluşturuldu. "
        f"Mod: {production_mode} | Süre: {plan['total_duration_seconds']} sn"
    )
    return plan


if __name__ == "__main__":
    create_scene_plan()
