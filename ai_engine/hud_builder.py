"""Deterministic, low-token HUD/FUI scene builder for After Effects MCP.

The builder deliberately uses only validated ae-motion tools. It creates editable
shape/text layers and predictable motion; no LLM-generated tool-call JSON is needed.
"""
from __future__ import annotations

import math
from typing import Any


W, H = 1920, 1080
BG = [0.012, 0.031, 0.071]
CYAN = [0.0, 0.78, 1.0]
BLUE = [0.0, 0.35, 0.72]
MAGENTA = [1.0, 0.12, 0.52]
RED = [1.0, 0.12, 0.16]
WHITE = [0.62, 0.84, 0.94]
MUTED = [0.08, 0.28, 0.40]


class HudBuildError(RuntimeError):
    pass


def _payload(result: Any) -> dict:
    if getattr(result, "isError", False):
        raise HudBuildError(_text(result))
    raw = _text(result)
    try:
        data = __import__("json").loads(raw)
    except Exception:
        raise HudBuildError(f"MCP returned non-JSON response: {raw[:400]}")
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        raise HudBuildError(f"{err.get('code', 'MCP_ERROR')}: {err.get('message', raw)}")
    return data if isinstance(data, dict) else {"result": data}


def _text(result: Any) -> str:
    chunks = []
    for item in getattr(result, "content", []) or []:
        if getattr(item, "text", None):
            chunks.append(item.text)
    return "\n".join(chunks) or str(result)


class HudBuilder:
    def __init__(self, session, scene: dict):
        self.session = session
        self.scene = scene
        self.duration = float(scene.get("duration_seconds", 6))
        self.comp_id = None
        self.layers: dict[str, int] = {}
        self.count = 0
        self.kind = str(scene.get("hud_animation", "radar_sweep")).lower()
        self.scene_id = int(scene.get("id", 1))

    async def call(self, name: str, args: dict) -> dict:
        return _payload(await self.session.call_tool(name, arguments=args))

    async def build(self) -> int:
        name = f"Scene_{self.scene_id}"
        comp = await self.call("create_comp", {
            "name": name, "width": W, "height": H, "fps": 30,
            "duration": self.duration, "bg_color": BG,
        })
        self.comp_id = int(comp["id"])
        try:
            await self.call("set_comp", {"comp_id": self.comp_id, "motion_blur": True})
        except HudBuildError:
            # Motion blur is an enhancement, never a reason to lose the scene.
            pass

        await self._grid_and_frame()
        if self.kind == "network_build":
            await self._network(threat=False)
        elif self.kind == "data_stream":
            await self._network(threat=True)
        elif self.kind == "shield_activation":
            await self._shield(activate=True)
        elif self.kind == "glitch_reveal":
            await self._shield(activate=False)
            await self._impact()
        else:
            await self._radar()
        await self._label()
        return self.comp_id

    async def _shape(self, name: str, typ: str, pos, size=None, *,
                     fill=None, stroke=CYAN, sw=2, opacity=100,
                     vertices=None, dashes=None, rotation=0, shape_offset=None):
        shape = {"type": typ}
        if stroke is not None:
            shape["stroke"] = stroke
            shape["stroke_width"] = sw
            shape["stroke_opacity"] = opacity
        if fill is not None:
            shape["fill"] = fill
            shape["fill_opacity"] = opacity
        if size is not None:
            shape["size"] = size
        if vertices is not None:
            shape["vertices"] = vertices
            shape["closed"] = True
        if dashes:
            shape["dashes"] = dashes
        if rotation:
            shape["rotation"] = rotation
        if shape_offset is not None:
            shape["position"] = [float(shape_offset[0]), float(shape_offset[1])]
        opts = {"name": name, "position": [float(pos[0]), float(pos[1])],
                "shape": shape}
        out = await self.call("add_layer", {
            "comp_id": self.comp_id, "kind": "shape", "options": opts,
        })
        layer_id = int(out["id"])
        self.layers[name] = layer_id
        self.count += 1
        return layer_id

    async def _rect(self, name, x, y, w, h, color=CYAN, opacity=80):
        return await self._shape(name, "rect", (x, y), (w, h),
                                 fill=color, stroke=None, sw=0.1, opacity=opacity)

    async def _animate(self, name, path, keys):
        layer_id = self.layers.get(name)
        if not layer_id:
            return
        await self.call("set_keyframes", {
            "layer_id": layer_id, "path": path,
            "keys": [{"t": float(t), "v": v, "interp": "linear"} for t, v in keys],
        })

    async def _glow(self, name):
        layer_id = self.layers.get(name)
        if not layer_id:
            return
        try:
            await self.call("apply_effect", {
                "layer_id": layer_id, "match_name": "ADBE Glo2",
            })
        except HudBuildError as exc:
            print(f"[HUD] Glow atlandı ({name}): {exc}")

    async def _text(self, name, text, x, y, size=22, color=WHITE):
        out = await self.call("add_layer", {
            "comp_id": self.comp_id, "kind": "text",
            "options": {"name": name, "text": text, "position": [x, y]},
        })
        layer_id = int(out["id"])
        self.layers[name] = layer_id
        self.count += 1
        await self.call("set_text", {
            "layer_id": layer_id, "text": text, "font": "ArialMT",
            "size": size, "color": color, "tracking": 3,
            "all_caps": True, "justification": "left",
        })
        return layer_id

    async def _grid_and_frame(self):
        # Deliberately faint: the grid is texture, never the focal point.
        for i, x in enumerate([320, 640, 960, 1280, 1600]):
            await self._rect(f"GridV{i}", x, 540, 1, 920, MUTED, 9)
        for i, y in enumerate([180, 360, 540, 720, 900]):
            await self._rect(f"GridH{i}", 960, y, 1740, 1, MUTED, 9)

        # Unequal corner marks establish a technical frame without symmetric crosses.
        for name, x, y, w, h in [
            ("FrameTLh", 105, 64, 150, 2), ("FrameTLv", 32, 135, 2, 140),
            ("FrameTRh", 1815, 64, 70, 2), ("FrameTRv", 1887, 125, 2, 95),
            ("FrameBLh", 105, 1016, 110, 2), ("FrameBLv", 32, 945, 2, 70),
            ("FrameBRh", 1815, 1016, 70, 2), ("FrameBRv", 1887, 945, 2, 70),
        ]:
            await self._rect(name, x, y, w, h, BLUE, 65)

        await self._text("TopMicroLabel", "SECURITY SYSTEM  /  LIVE FEED", 110, 105, 17, WHITE)
        await self._rect("TopAccent", 110, 128, 185, 2, CYAN, 65)

    async def _radar(self):
        cx, cy = 650, 550
        for i, diameter in enumerate([560, 420, 280, 140]):
            nm = f"RadarRing{i}"
            await self._shape(nm, "ellipse", (cx, cy), (diameter, diameter),
                              stroke=CYAN if i < 2 else BLUE, sw=2 if i < 2 else 1.5,
                              opacity=34 if i else 52, dashes=[18, 9] if i == 0 else None)
            if i == 0:
                await self._animate(nm, "rotation", [(0, 0), (self.duration, 360)])
        await self._shape("RadarSweep", "rect", (cx, cy), (245, 2),
                          fill=CYAN, stroke=None, sw=0.1, opacity=72,
                          shape_offset=(120, 0))
        await self._animate("RadarSweep", "rotation", [(0, -35), (self.duration, 325)])
        await self._glow("RadarSweep")
        await self._shape("RadarHub", "ellipse", (cx, cy), (14, 14),
                          fill=CYAN, stroke=CYAN, sw=1, opacity=95)
        for i, (dx, dy) in enumerate([(0,-300),(300,0),(0,300),(-300,0)]):
            await self._rect(f"RadialTick{i}", cx+dx, cy+dy, 34, 2, CYAN, 75)
        # Small contact pips make the radar feel active without clutter.
        for i, (x, y) in enumerate([(520,390),(760,470),(730,690),(455,610),(835,590)]):
            await self._shape(f"Contact{i}", "ellipse", (x,y), (9,9),
                              fill=MAGENTA if i == 2 else CYAN, stroke=None, sw=0.1)
            await self._animate(f"Contact{i}", "Opacity",
                                [(0, 25), (0.4 + i*0.18, 100), (self.duration, 35)])
        await self._panel("right", "SCAN ANALYSIS", ["SWEEP ACTIVE", "CONTACTS: 05", "SECTOR: 07"])

    async def _panel(self, side, title, rows):
        x = 1600 if side == "right" else 320
        y = 390 if side == "right" else 760
        await self._rect(f"{side}PanelTop", x, y, 230, 2, CYAN, 65)
        await self._rect(f"{side}PanelSide", x-115, y+48, 2, 96, BLUE, 55)
        await self._text(f"{side}PanelTitle", title, x-100, y+28, 17, CYAN)
        for i, row in enumerate(rows):
            yy = y + 65 + i*31
            await self._text(f"{side}PanelRow{i}", row, x-100, yy, 13, WHITE)
            await self._rect(f"{side}PanelBar{i}", x+45, yy+9, 55+(i*21), 3, BLUE, 55)

    async def _network(self, threat=False):
        nodes = [(390,720),(570,590),(760,690),(930,475),(1110,570),(1320,360),(1510,510),(1190,810)]
        links = [(0,1),(1,2),(1,3),(2,3),(3,4),(4,5),(4,6),(2,7),(4,7)]
        color = RED if threat else CYAN
        for i, (a,b) in enumerate(links):
            x1,y1 = nodes[a]; x2,y2 = nodes[b]
            dx,dy = x2-x1,y2-y1
            length = math.hypot(dx,dy)
            angle = math.degrees(math.atan2(dy,dx))
            nm=f"Link{i}"
            await self._shape(nm, "rect", ((x1+x2)/2,(y1+y2)/2), (length, 2.5),
                              fill=color, stroke=None, sw=0.1, opacity=60, rotation=angle)
            await self._animate(nm, "Opacity", [(0, 8), (0.5+i*0.12, 85), (self.duration, 60)])
        for i,(x,y) in enumerate(nodes):
            nm=f"Node{i}"
            await self._shape(nm, "ellipse", (x,y), (26,26), stroke=color, sw=2, opacity=95)
            await self._shape(f"NodeCore{i}", "ellipse", (x,y), (6,6), fill=color, stroke=None, sw=0.1)
            await self._animate(nm, "Scale", [(0, [35,35]), (0.35+i*0.15, [120,120]), (0.7+i*0.15, [100,100])])
        if threat:
            await self._shape("ThreatRing", "ellipse", (1320,360), (180,180), stroke=RED, sw=3, opacity=85, dashes=[12,8])
            await self._animate("ThreatRing", "Scale", [(0,[70,70]),(1.0,[110,110]),(2.0,[100,100]),(self.duration,[110,110])])
            await self._text("ThreatLabel", "CRITICAL BREACH", 1370, 245, 19, RED)
            await self._panel("right", "THREAT MONITOR", ["RISK: CRITICAL", "DATA FLOW: HIGH", "DEFENSE: PENDING"])
        else:
            await self._panel("right", "NETWORK STATUS", ["NODES: LINKED", "ROUTES: ACTIVE", "ENCRYPTION: ON"])

    async def _shield(self, activate=True):
        cx, cy = 960, 540
        for i,d in enumerate([560,470,370]):
            nm=f"ShieldRing{i}"
            await self._shape(nm,"ellipse",(cx,cy),(d,d),stroke=CYAN if i!=1 else BLUE,
                              sw=2,opacity=42 if i else 65,dashes=[20,10] if i==1 else None)
            await self._animate(nm,"rotation",[(0,0),(self.duration,360 if i%2==0 else -360)])
        # Geometric shield core: six-sided outline, not a generic filled icon.
        hexv=[(0,-190),(155,-100),(155,90),(0,190),(-155,90),(-155,-100)]
        await self._shape("ShieldOutline","polygon",(cx,cy),stroke=CYAN,sw=4,opacity=95,vertices=hexv)
        inner=[(0,-125),(100,-65),(100,60),(0,125),(-100,60),(-100,-65)]
        await self._shape("ShieldInner","polygon",(cx,cy),stroke=BLUE,sw=2,opacity=75,vertices=inner)
        await self._rect("ShieldSpine",cx,cy,2,300,BLUE,50)
        await self._rect("ShieldCross",cx,cy,260,2,BLUE,50)
        await self._shape("ShieldCore","ellipse",(cx,cy),(34,34),fill=CYAN,stroke=CYAN,sw=1)
        await self._animate("ShieldOutline","Scale",[(0,[65,65]),(1.1,[108,108]),(1.5,[100,100])])
        await self._animate("ShieldCore","Opacity",[(0,0),(0.8,100),(1.1,65),(1.5,100)])
        await self._glow("ShieldCore")
        await self._panel("left","DEFENSE MATRIX",["SHIELD: ACTIVE","CIPHER: VERIFIED","INTEGRITY: STABLE"])
        await self._text("ShieldTitle","CRYPTOGRAPHIC SHIELD",720,825,20,CYAN)

    async def _impact(self):
        # Red attack vectors terminate at the shield boundary; fragments disperse outward.
        for i in range(7):
            x=260+i*95
            nm=f"AttackVector{i}"
            await self._shape(nm,"rect",(x,520),(150,3),fill=RED,stroke=None,sw=0.1,opacity=85,rotation=-8+i*2)
            await self._animate(nm,"Position",[(0,[x-130,520]),(1.2,[x+80,520]),(2.0,[x+110,520])])
        for i in range(10):
            angle=(math.pi*2*i)/10
            x=960+math.cos(angle)*210
            y=540+math.sin(angle)*210
            nm=f"Fragment{i}"
            await self._shape(nm,"rect",(x,y),(8+(i%3)*3,8+(i%2)*4),
                              fill=RED if i%2==0 else CYAN,stroke=None,sw=0.1,opacity=90,rotation=i*17)
            await self._animate(nm,"Position",[(1.3,[x,y]),(2.5,[x+math.cos(angle)*140,y+math.sin(angle)*140])])
            await self._animate(nm,"Opacity",[(1.3,100),(3.2,0)])
        await self._text("SecureLabel","NETWORK SECURED",1370,855,22,CYAN)
        await self._animate("SecureLabel","Opacity",[(0,0),(2.5,100)])

    async def _label(self):
        title = str(self.scene.get("on_screen_text") or "").strip()
        if not title:
            return
        # The title stays in the top-left information rail, never in the hero negative space.
        await self._text("SceneTitle", title[:34], 110, 165, 25, CYAN)
