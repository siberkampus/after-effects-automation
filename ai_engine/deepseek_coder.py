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
    
    AVAILABLE TOOLS (Use these EXACT schemas):
    
    1. create_comp: {{"name": "Scene_{scene_data.get('id', '1')}", "width": 1920, "height": 1080, "fps": 30, "duration": 5.0, "bg_color": [0,0,0]}}
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
    
    response = ask_deepseek(prompt, temperature=0.2)
    response = re.sub(r"^```(?:json)?\s*", "", response.strip())
    response = re.sub(r"\s*```$", "", response.strip())
    
    try:
        return json.loads(response)
    except Exception as e:
        print(f"DeepSeek JSON Hatası: {e}")
        return []