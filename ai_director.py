"""Reliable After Effects director.

HUD scenes are built deterministically with native AE shape/text layers. DeepSeek is
not called per scene to invent MCP JSON. Claude QA is optional/advisory. A saved
project is rendered through ae-motion's asynchronous render_start/render_status API.
"""
import asyncio
import json
import os
import shutil
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ai_engine.hud_builder import HudBuilder, HudBuildError
from config.settings import PLAN_PATH, PROJECTS_DIR, EXPORTS_DIR

SERVER_SCRIPT = os.environ.get(
    "AE_MCP_SERVER_SCRIPT",
    os.path.join(os.path.expanduser("~"), "Documents", "ae-motion", "dist", "index.js"),
)
DEFAULT_RENDER_TIMEOUT = 900
QA_ENABLED = os.getenv("AE_ENABLE_CLAUDE_QA", "0").strip().lower() in {"1", "true", "yes"}
RENDER_DRAFT = os.getenv("AE_RENDER_DRAFT", "0").strip().lower() in {"1", "true", "yes"}
RENDER_DELIVER = os.getenv("AE_RENDER_DELIVER", "0").strip().lower() in {"1", "true", "yes"}


def _read_text(result):
    parts = []
    for item in getattr(result, "content", []) or []:
        value = getattr(item, "text", None)
        if value:
            parts.append(value)
    return "\\n".join(parts)


def _parse_result(result, tool_name):
    if getattr(result, "isError", False):
        raise RuntimeError(f"{tool_name}: {_read_text(result)[:1000]}")
    raw = _read_text(result)
    if not raw:
        raise RuntimeError(f"{tool_name}: MCP boş yanıt döndürdü.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"{tool_name}: JSON olmayan yanıt: {raw[:500]}")
    if isinstance(data, dict) and data.get("error"):
        error = data["error"]
        raise RuntimeError(
            f"{tool_name} [{error.get('code', 'ERROR')}]: "
            f"{error.get('message', raw)}"
        )
    if not isinstance(data, dict):
        raise RuntimeError(f"{tool_name}: Beklenmeyen yanıt: {raw[:500]}")
    return data


async def _call(session, name, args):
    return _parse_result(await session.call_tool(name, arguments=args), name)


async def _preview(session, comp_id, frame_path, seconds):
    try:
        result = await _call(session, "preview_frame", {
            "comp_id": int(comp_id), "time": min(max(0.1, seconds), 2.0), "size": 1152,
        })
        source = result.get("path")
        if source and os.path.isfile(source):
            shutil.copy2(source, frame_path)
            print(f"  [ÖNİZLEME] {frame_path}")
            return True
        print("  [UYARI] preview_frame dosya yolu döndürmedi.")
    except Exception as exc:
        print(f"  [UYARI] Önizleme alınamadı: {exc}")
    return False


async def _optional_qa(frame_path, scene):
    if not QA_ENABLED:
        print("  [QA] Claude kontrolü kapalı (varsayılan); API harcaması yapılmadı.")
        return None
    try:
        from ai_engine.claude_vision import analyze_scene_image
        result = await asyncio.to_thread(
            analyze_scene_image, frame_path, scene.get("visual_description", "")
        )
        state = "ONAY" if result.get("success") else "İYİLEŞTİRME ÖNERİSİ"
        print(f"  [CLAUDE] {state}: {result.get('reason', 'Açıklama yok')}")
        return result
    except Exception as exc:
        print(f"  [UYARI] Claude QA atlandı: {exc}")
        return None


async def _render(session, comp_id, output_path):
    # The caller already saved the AEP to Projects/scene_N.aep.
    # ae-motion's render_start now starts an asynchronous aerender job.
    render_args = {
        "comp_id": int(comp_id),
        "output_path": output_path,
        "overwrite": True,
        "draft": RENDER_DRAFT,
        "verify": True,
    }
    if RENDER_DELIVER:
        render_args["deliver"] = True

    started = await _call(session, "render_start", render_args)
    job_id = started.get("job_id")
    if not job_id:
        raise RuntimeError(f"render_start job_id döndürmedi: {started}")
    print(f"  [RENDER] İş başladı: {job_id}")

    timeout = max(60, int(os.getenv("AE_RENDER_TIMEOUT_SECONDS", DEFAULT_RENDER_TIMEOUT)))
    deadline = time.monotonic() + timeout
    last_phase = None
    while time.monotonic() < deadline:
        status = await _call(session, "render_status", {"job_id": job_id})
        state = status.get("state")
        phase = status.get("phase") or state
        percent = status.get("percent", 0)
        if phase != last_phase or state != "running":
            print(f"  [RENDER] {phase}: %{percent}")
            last_phase = phase
        if state == "done":
            actual = status.get("output_path") or output_path
            if not os.path.isfile(actual) or os.path.getsize(actual) == 0:
                raise RuntimeError(
                    f"Render tamamlandı bildirildi fakat çıktı bulunamadı: {actual}"
                )
            print(f"  [BAŞARILI] Render: {actual} ({os.path.getsize(actual):,} bytes)")
            check = status.get("check") or {}
            if check.get("issues"):
                print(f"  [RENDER QA] {check['issues']}")
            return actual
        if state in {"failed", "canceled"}:
            raise RuntimeError(
                f"Render {state}: errors={status.get('errors')} "
                f"log={status.get('log_tail')} hint={status.get('hint')}"
            )
        await asyncio.sleep(min(15, max(2, int(status.get("poll_after_s", 5)))))
    raise TimeoutError(
        f"Render {timeout} saniyede tamamlanmadı. İş kimliği {job_id}; "
        "After Effects/aerender hâlâ çalışıyor olabilir. Aynı sahneyi tekrar başlatmayın."
    )


async def _run_scene(session, scene):
    scene_id = int(scene["id"])
    print(f"\\n--- SAHNE {scene_id} / {scene.get('on_screen_text', '')} ---")
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    frame_path = os.path.join(EXPORTS_DIR, f"test_scene_{scene_id}.png")
    output_path = os.path.join(EXPORTS_DIR, f"scene_{scene_id:02d}.mp4")

    builder = HudBuilder(session, scene)
    comp_id = await builder.build()
    print(f"  [TASARIM] {builder.count} düzenlenebilir AE katmanı oluşturuldu.")

    # Preview and QA never gate the render. Save first so the project is recoverable.
    await _call(session, "save_project", {
        "path": os.path.abspath(os.path.join(PROJECTS_DIR, f"scene_{scene_id}.aep")),
        "overwrite": True,
    })
    preview_ok = await _preview(
        session, comp_id, frame_path, float(scene.get("duration_seconds", 6)) * 0.35
    )
    if preview_ok:
        await _optional_qa(frame_path, scene)
    else:
        print("  [QA] Önizleme yok; kalite kontrolü atlandı, render yine alınacak.")

    # render_start internally saves/prepares the current project. Explicit save above
    # guarantees a named .aep exists before that call.
    await _render(session, comp_id, output_path)
    return True


async def run_ai_director():
    print("=== AE HUD/FUI DIRECTOR ===")
    print("Mod: deterministik yerel tasarım + isteğe bağlı Claude QA")
    if not os.path.isfile(PLAN_PATH):
        raise FileNotFoundError(f"Sahne planı bulunamadı: {PLAN_PATH}")
    with open(PLAN_PATH, "r", encoding="utf-8") as file:
        plan = json.load(file)
    scenes = plan.get("scenes", [])
    if not scenes:
        raise ValueError("scene_plan.json içinde sahne bulunamadı.")
    if not os.path.isfile(SERVER_SCRIPT):
        raise FileNotFoundError(
            f"AE MCP sunucusu bulunamadı: {SERVER_SCRIPT}. "
            "AE_MCP_SERVER_SCRIPT ortam değişkenini kontrol edin."
        )

    params = StdioServerParameters(
        command="node",
        args=[SERVER_SCRIPT],
        env={**os.environ, "AE_MCP_ALLOW_JSX": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[MCP] Bağlantı kuruldu.")
            for scene in scenes:
                try:
                    await _run_scene(session, scene)
                except Exception as exc:
                    print(f"  [SAHNE HATASI] Sahne {scene.get('id')}: {exc}")
                    print("  [DURDURULDU] AE durumunu kontrol etmeden sonraki sahne gönderilmiyor.")
                    break
    print("\\n=== YÖNETMEN DÖNGÜSÜ TAMAMLANDI ===")


if __name__ == "__main__":
    try:
        asyncio.run(run_ai_director())
    except KeyboardInterrupt:
        print("\\n[İPTAL] Kullanıcı işlemi durdurdu.")
    except Exception as exc:
        print(f"\\n[FATAL] {exc}")
        raise
