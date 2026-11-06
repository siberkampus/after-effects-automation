# ai_engine/jsx_generator.py
import json
import os
import re
from config.settings import (
    PLAN_PATH, MANIFEST_PATH, SCRIPTS_DIR, PROJECTS_DIR, AEP_PATH,
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
)

def load_json(path):
    if not os.path.exists(path): return []
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)

def jsx_string(value):
    value = str(value)
    value = value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", " ").replace("\n", " ")
    return '"' + value + '"'

def safe_name(value):
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value))
    return value[:60] or "Scene"

# ORTAK KOMUTLAR (Her sahnede olacaklar)
COMMON_JSX_TOP = r'''
(function () {
    app.beginUndoGroup("AI Documentary Scene");
    var SCENE_NAME = __SCENE_NAME__;
    var SCENE_TITLE = __SCENE_TITLE__;
    var IMAGE_PATH = __IMAGE_PATH__;
    var DURATION = __DURATION__;
    var W = __WIDTH__;
    var H = __HEIGHT__;
    var FPS = __FPS__;
    var PROJECT_PATH = __AEP_PATH__;
    var STYLE = __ANIMATION_STYLE__;

    try {
        var comp = app.project.items.addComp(SCENE_NAME, W, H, 1, DURATION, FPS);
        comp.bgColor = [0.02, 0.02, 0.02];
        comp.layers.addSolid([0.02, 0.02, 0.02], "Background", W, H, 1, DURATION);

        var imageLayer = null;
        if (IMAGE_PATH !== "") {
            var imageFile = new File(IMAGE_PATH);
            if (imageFile.exists) {
                var footage = app.project.importFile(new ImportOptions(imageFile));
                imageLayer = comp.layers.add(footage);
                imageLayer.startTime = 0; imageLayer.inPoint = 0; imageLayer.outPoint = DURATION;
                var scaleX = W / footage.width * 100;
                var scaleY = H / footage.height * 100;
                var scale = Math.max(scaleX, scaleY);
                imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValue([scale, scale]);
            }
        }

        // Sinematik Siyah Bantlar
        var topBar = comp.layers.addSolid([0, 0, 0], "Top Bar", W, 120, 1, DURATION);
        topBar.property("ADBE Transform Group").property("ADBE Position").setValue([W / 2, 60]);
        var bottomBar = comp.layers.addSolid([0, 0, 0], "Bottom Bar", W, 120, 1, DURATION);
        bottomBar.property("ADBE Transform Group").property("ADBE Position").setValue([W / 2, H - 60]);
'''

# STİL 1: Harita Reveal
STYLE_MAP = r'''
        if (STYLE === "map_reveal" && imageLayer) {
            imageLayer.property("ADBE Transform Group").property("ADBE Opacity").setValue(60);
            var overlay = comp.layers.addSolid([0,0,0], "Dark", W, H, 1, DURATION);
            overlay.property("ADBE Transform Group").property("ADBE Opacity").setValue(40);
            
            var lineShape = comp.layers.addShape();
            var lineGroup = lineShape.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
            var linePath = lineGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Rect");
            linePath.property("ADBE Vector Rect Size").setValue([W, 4]);
            var lineFill = lineGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
            lineFill.property("ADBE Vector Fill Color").setValue([1, 0.7, 0.2]);
            
            var trim = lineGroup.property("ADBE Vectors Group").addProperty("ADBE Vector Filter - Trim");
            trim.property("ADBE Vector Trim Start").setValue(0);
            trim.property("ADBE Vector Trim End").setValueAtTime(0.2, 0);
            trim.property("ADBE Vector Trim End").setValueAtTime(DURATION - 0.5, 100);
            
            lineShape.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2]);
            lineShape.property("ADBE Transform Group").property("ADBE Scale").setValue([1, 20]);
            
            var title = comp.layers.addText(SCENE_TITLE);
            var td = title.property("ADBE Text Properties").property("ADBE Text Document").value;
            td.fontSize = 60; td.font = "Georgia-Bold"; td.fillColor = [1,1,1];
            title.property("ADBE Text Properties").property("ADBE Text Document").setValue(td);
            title.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H*0.85]);
        }
'''

# STİL 2: Parallax Slide
STYLE_PARALLAX = r'''
        else if (STYLE === "parallax_slide" && imageLayer) {
            imageLayer.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(0, [W*0.6, H/2]);
            imageLayer.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(1.2, [W/2, H/2]);
            imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(0, [120, 120]);
            imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(DURATION, [100, 100]);
            
            var title = comp.layers.addText(SCENE_TITLE);
            var td = title.property("ADBE Text Properties").property("ADBE Text Document").value;
            td.fontSize = 90; td.font = "Arial-BoldMT"; td.fillColor = [0.9, 0.8, 0.3];
            title.property("ADBE Text Properties").property("ADBE Text Document").setValue(td);
            title.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(0.5, [W/2, H*0.75]);
            title.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(0, [-W/2, H*0.75]);
        }
'''

# STİL 3: Typewriter
STYLE_TYPEWRITER = r'''
        else if (STYLE === "typewriter_text" && imageLayer) {
            imageLayer.property("ADBE Transform Group").property("ADBE Opacity").setValue(30);
            imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(0, [110, 110]);
            imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(DURATION, [100, 100]);
            
            var title = comp.layers.addText(SCENE_TITLE);
            var td = title.property("ADBE Text Properties").property("ADBE Text Document").value;
            td.fontSize = 70; td.font = "CourierNewPS-BoldMT"; td.fillColor = [0.8, 0.8, 0.8];
            td.justification = ParagraphJustification.CENTER_JUSTIFY;
            title.property("ADBE Text Properties").property("ADBE Text Document").setValue(td);
            title.property("ADBE Transform Group").property("ADBE Position").setValue([W/2, H/2]);
            
            var sourceText = title.property("ADBE Text Properties").property("ADBE Text Document");
            var typeExpression = "var txt = '" + SCENE_TITLE + "'; var speed = 15; txt.substr(0, Math.floor(time * speed));";
            sourceText.expression = typeExpression;
        }
'''

# STİL 4: Default (Documentary Zoom)
STYLE_DEFAULT = r'''
        else {
            if (imageLayer) {
                imageLayer.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(0, [W*0.45, H/2]);
                imageLayer.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(DURATION, [W*0.55, H/2]);
                imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(0, [100, 100]);
                imageLayer.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(DURATION, [115, 115]);
            }
            var overlay = comp.layers.addSolid([0,0,0], "Dark", W, H, 1, DURATION);
            overlay.property("ADBE Transform Group").property("ADBE Opacity").setValue(20);

            var title = comp.layers.addText(SCENE_TITLE);
            var td = title.property("ADBE Text Properties").property("ADBE Text Document").value;
            td.fontSize = 75; td.font = "Georgia-Bold"; td.fillColor = [1, 0.8, 0.4];
            title.property("ADBE Text Properties").property("ADBE Text Document").setValue(td);
            title.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(1, [W/2, H*0.82]);
            title.property("ADBE Transform Group").property("ADBE Position").setValueAtTime(0, [W/2, H*0.85]);
            title.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(0.5, 0);
            title.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime(1.5, 100);
        }
'''

# ORTAK KOMUTLAR SONU
COMMON_JSX_BOTTOM = r'''
        if (PROJECT_PATH !== "") { app.project.save(new File(PROJECT_PATH)); }
        app.endUndoGroup();
    } catch (e) {
        app.endUndoGroup(); alert("Hata: " + e.toString());
    }
})();
'''

def generate_jsx_files():
    plan = load_json(PLAN_PATH)
    manifest = load_json(MANIFEST_PATH)

    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    os.makedirs(PROJECTS_DIR, exist_ok=True)

    image_lookup = {str(item["scene_id"]): item["local_path"] for item in manifest}

    for scene in plan.get("scenes", []):
        scene_id = str(scene["id"])
        style = scene.get("animation_style", "documentary_zoom")
        
        scene_name = safe_name(f"Scene_{scene_id}_{style}")
        image_path = image_lookup.get(scene_id, "")

        if style == "map_reveal":
            specific_jsx = STYLE_MAP
        elif style == "parallax_slide":
            specific_jsx = STYLE_PARALLAX
        elif style == "typewriter_text":
            specific_jsx = STYLE_TYPEWRITER
        else:
            specific_jsx = STYLE_DEFAULT

        full_jsx = COMMON_JSX_TOP + specific_jsx + COMMON_JSX_BOTTOM

        replacements = {
            "__SCENE_NAME__": jsx_string(scene_name),
            "__SCENE_TITLE__": jsx_string(scene.get("on_screen_text", scene.get("narration_summary", ""))),
            "__IMAGE_PATH__": jsx_string(image_path),
            "__AEP_PATH__": jsx_string(AEP_PATH),
            "__ANIMATION_STYLE__": jsx_string(style),
            "__DURATION__": str(float(scene["duration_seconds"])),
            "__WIDTH__": str(VIDEO_WIDTH),
            "__HEIGHT__": str(VIDEO_HEIGHT),
            "__FPS__": str(VIDEO_FPS)
        }

        for key, value in replacements.items():
            full_jsx = full_jsx.replace(key, value)

        output_path = os.path.join(SCRIPTS_DIR, f"scene_{scene_id}.jsx")
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(full_jsx)

    print(f"Toplam {len(plan.get('scenes', []))} adet JSX dosyası başarıyla oluşturuldu.")