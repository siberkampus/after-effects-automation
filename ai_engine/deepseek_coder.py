# ai_engine/deepseek_coder.py
from ai_engine.deepseek import ask_deepseek
import re
import json

def generate_mcp_commands(scene_data, feedback=None):
    prompt = f"""
    You are an expert Adobe After Effects director controlling an MCP server.
    Write a sequence of MCP tool calls to create the following scene.
    
    SCENE ID: {scene_data.get('id', '1')}
    TITLE: {scene_data.get('on_screen_text', '')}
    VISUAL DESCRIPTION: {scene_data.get('visual_description', '')}
    HUD COMPONENTS: {json.dumps(scene_data.get('hud_components', []))}
    HUD ANIMATION: {scene_data.get('hud_animation', '')}
    HUD LAYOUT: {scene_data.get('layout', '')}
    COLOR PALETTE: {json.dumps(scene_data.get('color_palette', {}))}
    DURATION: {scene_data.get('duration_seconds', 5)} seconds
    IMAGE PATH: "{scene_data.get('local_image_path', '')}"
    HUD/FUI DESIGN REQUIREMENTS (when HUD COMPONENTS is non-empty):
    - Treat this as a premium sci-fi interface shot, not generic cyber illustration.
    - Build separate editable native shape/text layers; target 24-30 purposeful layers so the response remains complete and executable.
    - Use deep navy, subtle grid, thin cyan/blue strokes, asymmetric technical frames,
      corner brackets, radial ticks, compact data panels and deliberate negative space.
    - Radar: 3+ concentric outline ellipses, separated ring segments, 12-20 radial ticks,
      center hub, crosshair and a rotating sweep element.
    - Target lock: four independent L-shaped brackets, center reticle and tracking markers;
      animate brackets converging before settling.
    - Data panels: fine outline borders, header dividers, short labels and micro-bars.
    - Animate at least 4 distinct elements with set_keyframes within scene duration; use no more than 6 keyframe calls and 2 effect calls.
    - Use Opacity, Scale or Position only; reference exact existing layer names.
    - Apply glow sparingly to 2-4 hero elements. Never import UI screenshots in HUD mode.
    - Avoid oversized filled circles, random rectangles, invented metrics and unreadable text.
    - Use 1920x1080 coordinates with 70px safe margins.
    
    AVAILABLE TOOLS (Use these EXACT schemas):
    
    1. create_comp: {{"name": "Scene_{scene_data.get('id', '1')}", "width": 1920, "height": 1080, "fps": 30, "duration": {scene_data.get('duration_seconds', 5)}, "bg_color": [0.012,0.031,0.071]}}
       (CRITICAL: The name MUST be exactly "Scene_{scene_data.get('id', '1')}")
    
    2. import_footage: {{"path": "string"}} 
    
    3. add_layer: {{"comp_id": "AUTO_COMP", "kind": "footage" | "text" | "solid" | "shape", "options": {{...}}}}
       -> For footage: "kind": "footage", "options": {{"item_id": "AUTO_ID", "name": "Bg"}}
       -> For text: "kind": "text", "options": {{"text": "Hello", "name": "TitleText"}}
       -> For solid: "kind": "solid", "options": {{"color": [0.0, 0.0, 0.0], "name": "BlackBg"}}
       -> For shape: "kind": "shape", "options": {{
            "name": "Node1",
            "shape": {{"type": "ellipse" | "rect" | "star" | "polygon", "size": [50, 50], "fill": [0.0, 0.8, 1.0], "stroke": [0.0, 1.0, 1.0], "stroke_width": 2}},
            "position": [x, y]
          }}
          * CRITICAL SHAPE RULES:
            - NEVER use "type": "line". To draw lines, use "type": "rect" with a very thin height, e.g., "size": [200, 4].
            - "stroke_width" MUST be greater than 0 (e.g., 2 or 4).
       
    4. set_keyframes: {{"comp_id": "AUTO_COMP", "layer": "LayerName", "path": "Opacity" | "Scale" | "Position", "keys": [{{"t": 0, "v": 0}}, {{"t": 1, "v": 100}}]}}
    
    5. apply_effect: {{"comp_id": "AUTO_COMP", "layer": "LayerName", "match_name": "ADBE Glo2"}}

    CRITICAL RULES:
    1. Return ONLY a valid JSON array of tool calls. No Markdown.
    2. ALWAYS add a black solid layer first if there is no image path:
       {{"tool": "add_layer", "arguments": {{"comp_id": "AUTO_COMP", "kind": "solid", "options": {{"color": [0.0, 0.0, 0.0], "name": "BlackBg"}}}}}}
    3. If IMAGE PATH is EMPTY or the scene is about cybersecurity:
       - DO NOT use import_footage.
       - Use kind="shape" to draw abstract cyber graphics (network nodes, lines, shields).
       - Draw "lines" using thin rectangles: "type": "rect", "size": [300, 4].
    4. ALWAYS use the EXACT parameter names above.
    
    Example (Cyber Graphic):
    [
        {{"tool": "create_comp", "arguments": {{"name": "Scene_{scene_data.get('id', '1')}", "width": 1920, "height": 1080, "fps": 30, "duration": 5.0, "bg_color": [0,0,0]}}}},
        {{"tool": "add_layer", "arguments": {{"comp_id": "AUTO_COMP", "kind": "solid", "options": {{"color": [0.0, 0.0, 0.0], "name": "BlackBg"}}}}}},
        {{"tool": "add_layer", "arguments": {{"comp_id": "AUTO_COMP", "kind": "shape", "options": {{"name": "Node1", "shape": {{"type": "ellipse", "size": [60, 60], "fill": [0.0, 0.8, 1.0]}}, "position": [500, 500]}}}}}},
        {{"tool": "add_layer", "arguments": {{"comp_id": "AUTO_COMP", "kind": "shape", "options": {{"name": "Node2", "shape": {{"type": "ellipse", "size": [60, 60], "fill": [0.0, 0.8, 1.0]}}, "position": [1200, 700]}}}}}},
        {{"tool": "add_layer", "arguments": {{"comp_id": "AUTO_COMP", "kind": "shape", "options": {{"name": "Line1", "shape": {{"type": "rect", "size": [700, 4], "fill": [0.0, 0.5, 1.0]}}, "position": [850, 600]}}}}}}
    ]
    """
    
    if feedback:
        prompt += f"\n\nCRITICAL FIX REQUIRED FROM PREVIOUS ATTEMPT:\n{feedback}\n"
    
    response = ask_deepseek(prompt, temperature=0.1, max_tokens=8192)
    response = re.sub(r"^```(?:json)?\s*", "", response.strip())
    response = re.sub(r"\s*```$", "", response.strip())
    
    # Parse the first complete JSON array, tolerating prose/fences around it.
    decoder = json.JSONDecoder()
    for index, char in enumerate(response):
        if char == "[":
            try:
                parsed, _ = decoder.raw_decode(response[index:])
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                continue
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict) and isinstance(parsed.get("commands"), list):
            return parsed["commands"]
    except json.JSONDecodeError as error:
        print(f"DeepSeek JSON Hatası: {error}")
    print("DeepSeek JSON Hatası: Tam bir komut dizisi bulunamadı (yanıt kesilmiş olabilir).")
    return []