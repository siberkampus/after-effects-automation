# ai_director.py
import asyncio
import json
import os
import re
import shutil

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ai_engine.deepseek_coder import generate_mcp_commands
from ai_engine.claude_vision import analyze_scene_image
from config.settings import PLAN_PATH, PROJECTS_DIR, EXPORTS_DIR


# İstersen bu yolu Windows ortam değişkeniyle değiştirebilirsin:
# PowerShell:
# $env:AE_MCP_SERVER_SCRIPT = "C:\tam\yol\ae-motion\dist\index.js"
SERVER_SCRIPT = os.environ.get(
    "AE_MCP_SERVER_SCRIPT",
    r"C:\Users\ACER\Documents\ae-motion\dist\index.js",
)

MAX_RETRIES = 2
PREVIEW_TIME_SECONDS = 1.0


def _read_tool_text(result):
    """MCP yanıtından metni güvenli şekilde al."""
    if not getattr(result, "content", None):
        return ""
    first = result.content[0]
    return getattr(first, "text", str(first))


def _extract_id(raw_text):
    """MCP JSON yanıtındaki id alanını bul."""
    try:
        payload = json.loads(raw_text)
        if isinstance(payload, dict) and payload.get("id") is not None:
            return int(payload["id"])
        # Bazı MCP sunucuları sonucu sarmalanmış döndürebilir.
        for value in payload.values() if isinstance(payload, dict) else []:
            if isinstance(value, dict) and value.get("id") is not None:
                return int(value["id"])
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    match = re.search(r'"id"\s*:\s*(\d+)', raw_text)
    return int(match.group(1)) if match else None


def _normalize_color(color):
    if isinstance(color, list) and len(color) == 3:
        try:
            values = [float(component) for component in color]
            if any(component > 1.0 for component in values):
                values = [component / 255.0 for component in values]
            return values
        except (TypeError, ValueError):
            return color
    return color


def _normalize_layer_options(options):
    options = dict(options or {})

    if "color" in options:
        options["color"] = _normalize_color(options["color"])

    shape = options.get("shape")
    if isinstance(shape, dict):
        shape = dict(shape)
        if "fill" in shape:
            shape["fill"] = _normalize_color(shape["fill"])
        if "stroke" in shape:
            shape["stroke"] = _normalize_color(shape["stroke"])
        options["shape"] = shape

    return options


def _prepare_keyframes_args(args, layer_map, last_layer_id):
    new_args = {}
    layer_name = args.get("layer") or args.get("layer_name")

    if layer_name and layer_name in layer_map:
        new_args["layer_id"] = int(layer_map[layer_name])
    elif last_layer_id is not None:
        new_args["layer_id"] = int(last_layer_id)
    else:
        return None

    path = args.get("property") or args.get("path")
    new_args["path"] = path

    old_keys = args.get("keyframes") or args.get("keys") or []
    new_keys = []

    for key in old_keys:
        key_time = key.get("time")
        if key_time is None:
            key_time = key.get("t", 0.0)

        value = key.get("value")
        if value is None:
            value = key.get("v", [0])

        if path == "Opacity":
            if isinstance(value, list) and value:
                value = value[0]
            value = float(value)
        elif path in ("Scale", "Position"):
            if not isinstance(value, list):
                value = [float(value), float(value)]
            else:
                value = [float(component) for component in value]

        new_keys.append({"t": float(key_time), "v": value})

    new_args["keys"] = new_keys
    return new_args


def _prepare_command(
    command,
    comp_id,
    layer_map,
    last_layer_id,
    footage_id,
    image_available,
    forced_comp_name,
):
    """DeepSeek komutlarını AE MCP araçlarının beklediği argümanlara çevir."""
    tool_name = command.get("tool")
    args = dict(command.get("arguments") or {})

    if not tool_name:
        return None, None

    if tool_name == "create_comp":
        args["name"] = forced_comp_name
        return tool_name, args

    # Görsel yoksa dosya içe aktarma komutlarını çalıştırma.
    if not image_available and tool_name == "import_footage":
        print("       [ATLANDI] Görsel bulunmadığı için import_footage atlandı.")
        return None, None

    if tool_name == "add_layer":
        options = dict(args.get("options") or {})

        # Eski prompt sürümlerinin üst seviye alanlarını da destekle.
        for field in (
            "text", "color", "item_id", "name",
            "text_style", "shape", "position",
        ):
            if field in args:
                options[field] = args[field]

        kind = args.get("kind") or args.get("type")

        if not image_available and kind == "footage":
            print("       [ATLANDI] Görsel bulunmadığı için footage katmanı atlandı.")
            return None, None

        if "name" not in options:
            options["name"] = f"Layer_{len(layer_map) + 1}"

        options = _normalize_layer_options(options)
        return "add_layer", {
            "comp_id": comp_id,
            "kind": kind,
            "options": options,
        }

    if tool_name == "set_keyframes":
        prepared = _prepare_keyframes_args(args, layer_map, last_layer_id)
        return (tool_name, prepared) if prepared else (None, None)

    if tool_name == "apply_effect":
        if args.get("layer") in layer_map:
            layer_id = int(layer_map[args["layer"]])
        elif args.get("layer_name") in layer_map:
            layer_id = int(layer_map[args["layer_name"]])
        elif last_layer_id is not None:
            layer_id = int(last_layer_id)
        else:
            return None, None

        return tool_name, {
            "layer_id": layer_id,
            "match_name": args.get("effect") or args.get("match_name"),
        }

    # Bilinmeyen araçları değiştirmeden ilet.
    if comp_id is not None:
        args_str = json.dumps(args)
        args_str = (
            args_str.replace('"AUTO_COMP"', str(comp_id))
            .replace('"comp_name"', str(comp_id))
        )
        if footage_id is not None:
            args_str = args_str.replace('"AUTO_ID"', str(footage_id))
        args = json.loads(args_str)

    return tool_name, args


async def _run_scene(session, scene, manifest):
    scene_id = scene["id"]
    print(f"\n--- SAHNE {scene_id} İŞLENİYOR ---")

    os.makedirs(PROJECTS_DIR, exist_ok=True)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    scene_aep_path = os.path.join(PROJECTS_DIR, f"scene_{scene_id}.aep")
    video_output_path = os.path.join(EXPORTS_DIR, f"scene_{int(scene_id):02d}.mp4")
    frame_path = os.path.join(EXPORTS_DIR, f"test_scene_{scene_id}.jpg")

    image_path = next(
        (
            item.get("local_path", "")
            for item in manifest
            if str(item.get("scene_id")) == str(scene_id)
        ),
        "",
    )
    image_available = bool(image_path and os.path.isfile(image_path))

    if image_available:
        scene["local_image_path"] = image_path
        scene["visual_assets_available"] = True
        scene["asset_mode"] = "image_plus_generated_hud"
        print(f"  [GÖRSEL] Kullanılacak: {image_path}")
    else:
        scene["local_image_path"] = ""
        scene["visual_assets_available"] = False
        scene["asset_mode"] = "generated_hud_only"
        scene["image_fallback_instruction"] = (
            "No external image is available. Do not import footage or create "
            "footage layers. Build the entire scene using native After Effects "
            "shape, text, solid and animation layers. Use a polished HUD/FUI "
            "visual language: restrained grid, technical frames, data panels, "
            "radar/scanner elements, network nodes, connecting lines and "
            "coherent cyan/red accents where appropriate. Avoid generic "
            "placeholder circles and rectangles; compose purposeful interface "
            "elements with hierarchy and motion."
        )
        print(
            "  [GÖRSEL YOK] Sahne görsel olmadan üretilecek; "
            "HUD/FUI öğeleri AE katmanlarıyla oluşturulacak."
        )

    feedback = None
    success = False
    forced_comp_name = f"Scene_{scene_id}"
    last_comp_id = None

    for attempt in range(MAX_RETRIES):
        print(
            f"  [Deneme {attempt + 1}/{MAX_RETRIES}] "
            "DeepSeek MCP komutları üretiyor..."
        )

        commands = generate_mcp_commands(scene, feedback)
        if not commands:
            print("  [HATA] DeepSeek komut üretmedi.")
            break

        comp_id = None
        footage_id = None
        layer_map = {}
        last_layer_id = None
        command_failed = False

        for command in commands:
            tool_name, args = _prepare_command(
                command=command,
                comp_id=comp_id,
                layer_map=layer_map,
                last_layer_id=last_layer_id,
                footage_id=footage_id,
                image_available=image_available,
                forced_comp_name=forced_comp_name,
            )

            if not tool_name:
                continue

            try:
                print(f"    -> Çalıştırılıyor: {tool_name}")
                result = await session.call_tool(tool_name, arguments=args)
                raw_text = _read_tool_text(result)
                print(f"       [DEBUG] {tool_name}: {raw_text[:160]}")

                # JSON yanıtlarında error alanını kontrol et; sıradan metindeki
                # "error" kelimesi tek başına başarısızlık sayılmasın.
                tool_error = False
                try:
                    parsed = json.loads(raw_text)
                    tool_error = isinstance(parsed, dict) and bool(parsed.get("error"))
                except json.JSONDecodeError:
                    tool_error = raw_text.lstrip().lower().startswith("error:")

                if tool_error:
                    feedback = f"{tool_name} başarısız oldu: {raw_text}"
                    print(f"       [HATA] {feedback}")
                    command_failed = True
                    break

                if tool_name == "create_comp":
                    comp_id = _extract_id(raw_text)
                    if comp_id is not None:
                        last_comp_id = comp_id

                elif tool_name == "import_footage":
                    footage_id = _extract_id(raw_text)

                elif tool_name == "add_layer":
                    new_layer_id = _extract_id(raw_text)
                    if new_layer_id is not None:
                        last_layer_id = new_layer_id
                        layer_name = (
                            args.get("options", {}).get("name", "Unknown")
                        )
                        layer_map[layer_name] = new_layer_id

            except Exception as error:
                feedback = f"MCP Tool Error ({tool_name}): {error}"
                print(f"  [HATA] {feedback}")
                command_failed = True
                break

        if command_failed:
            continue

        if comp_id is None:
            feedback = "Komut listesi geçerli bir kompozisyon oluşturmadı."
            print(f"  [HATA] {feedback}")
            continue

        last_comp_id = comp_id

        # Önizleme karesi al.
        print("  MCP: Ekran görüntüsü alınıyor...")
        preview_available = False

        try:
            preview_result = await session.call_tool(
                "preview_frame",
                arguments={
                    "comp_id": int(comp_id),
                    "time": PREVIEW_TIME_SECONDS,
                },
            )
            preview_json = json.loads(_read_tool_text(preview_result))
            preview_source = preview_json.get("path")

            if preview_source and os.path.isfile(preview_source):
                shutil.copy2(preview_source, frame_path)
                preview_available = os.path.isfile(frame_path)
        except Exception as error:
            print(f"  [UYARI] Önizleme alınamadı: {error}")

        # Claude Vision, önizleme mevcutsa çalışır. Görselin bulunmaması
        # Claude kontrolünü atlamak için tek başına gerekçe değildir.
        if preview_available:
            print("  Claude: Sahne analiz ediliyor...")
            try:
                analysis = analyze_scene_image(
                    frame_path,
                    scene.get("visual_description", ""),
                )

                if analysis.get("success"):
                    print(
                        f"  [BAŞARILI] Claude onayladı: "
                        f"{analysis.get('reason', 'Görsel uygun.')}"
                    )
                    success = True
                    break

                reason = analysis.get("reason", "Tasarım iyileştirilmeli.")
                print(f"  [REDDEDİLDİ] Claude: {reason}")
                feedback = (
                    "Revise the scene based on this visual review: "
                    f"{reason}. Preserve the requested HUD/FUI style, "
                    "visual hierarchy, readable typography and purposeful "
                    "motion. Do not impose a black background unless the "
                    "scene design specifically calls for it."
                )
            except Exception as error:
                print(f"  [UYARI] Claude Vision analizi başarısız: {error}")
                # Görsel analiz servisinin hatası sahnenin üretimini engellemesin.
                success = True
                break
        else:
            print(
                "  [UYARI] Önizleme alınamadı; Claude Vision kontrolü "
                "bu denemede atlandı."
            )
            # Kompozisyon oluşturulduysa render alabilmek için devam et.
            success = True
            break

    # Claude reddetse bile mevcut davranışı koruyarak oluşturulmuş
    # kompozisyonu kaydet ve render etmeyi dene.
    if last_comp_id is not None:
        status = "ONAYLANDI" if success else "KONTROL TAMAMLANAMADI"
        print(f"\n  MCP RENDER: Sahne {scene_id} render alınıyor [{status}]")

        if os.path.exists(video_output_path):
            os.remove(video_output_path)

        try:
            await session.call_tool(
                "save_project",
                arguments={"path": scene_aep_path},
            )
            print(f"       [BİLGİ] Proje kaydedildi: {scene_aep_path}")
        except Exception as error:
            print(f"       [UYARI] Proje kaydedilemedi: {error}")

        await asyncio.sleep(2)

        try:
            print("       [BİLGİ] MCP render_start çağrılıyor...")
            render_result = await session.call_tool(
                "render_start",
                arguments={
                    "comp_id": int(last_comp_id),
                    "output_path": video_output_path,
                },
            )
            render_text = _read_tool_text(render_result)
            print(f"       [DEBUG] render_start: {render_text[:200]}")

            max_wait = 120
            waited = 0
            while not os.path.exists(video_output_path) and waited < max_wait:
                await asyncio.sleep(2)
                waited += 2
                if waited % 10 == 0:
                    print(f"       [BEKLENİYOR] {waited} saniye geçti...")

            if os.path.isfile(video_output_path) and os.path.getsize(video_output_path) > 0:
                print(f"       [BAŞARILI] Video oluşturuldu: {video_output_path}")
            else:
                print(f"       [HATA] Video {max_wait} saniye içinde oluşmadı.")
        except Exception as error:
            print(f"       [HATA] Render başlatılamadı: {error}")
    else:
        print(f"  [!] Sahne {scene_id} için kompozisyon oluşturulamadı.")


async def run_ai_director():
    print("=== AI YÖNETMEN DÖNGÜSÜ BAŞLIYOR ===")

    if not os.path.isfile(PLAN_PATH):
        print(f"[HATA] Sahne planı bulunamadı: {PLAN_PATH}")
        return

    with open(PLAN_PATH, "r", encoding="utf-8") as file:
        plan = json.load(file)

    scenes = plan.get("scenes", [])
    if not scenes:
        print("[HATA] Plan dosyasında sahne bulunamadı.")
        return

    manifest_path = os.path.normpath(
        os.path.join(PROJECTS_DIR, "..", "Plans", "image_manifest.json")
    )
    manifest = []

    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as file:
                manifest = json.load(file)
        except (json.JSONDecodeError, OSError) as error:
            print(f"[UYARI] Görsel manifest'i okunamadı: {error}")
            manifest = []
    else:
        print("[BİLGİ] Görsel manifest'i yok; tüm sahneler HUD-only üretilecek.")

    if not os.path.isfile(SERVER_SCRIPT):
        print(f"[HATA] AE MCP sunucu dosyası bulunamadı: {SERVER_SCRIPT}")
        print(
            "AE_MCP_SERVER_SCRIPT ortam değişkeniyle doğru index.js yolunu "
            "tanımlayabilirsin."
        )
        return

    server_params = StdioServerParameters(
        command="node",
        args=[SERVER_SCRIPT],
        env={**os.environ, "AE_MCP_ALLOW_JSX": "1"},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("MCP Bağlantısı Kuruldu.\n")

            for scene in scenes:
                await _run_scene(session, scene, manifest)


if __name__ == "__main__":
    asyncio.run(run_ai_director())
