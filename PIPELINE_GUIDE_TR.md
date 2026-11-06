# AE HUD/FUI Pipeline (Windows)

## What changed

- `ai_director.py` builds HUD/FUI scenes with native editable After Effects shape and text layers. It no longer asks DeepSeek to invent dozens of MCP calls for every scene.
- Claude Vision is advisory and disabled by default. A rejected scene is still saved, previewed and rendered.
- Rendering uses ae-motion's asynchronous `render_start` + `render_status` job API. The script checks the real job state instead of waiting blindly for a file.
- A failed Save As / render call is reported immediately; it is never printed as a successful save.
- `main.py` reuses an existing scene plan by default, avoiding unnecessary DeepSeek calls. HUD mode skips redundant Wikimedia searches and legacy JSX generation.

## Requirements

1. Windows, Adobe After Effects, Node.js supported by your installed `ae-motion` MCP server.
2. Python dependencies already used by this project (`mcp`, `python-dotenv`, `openai`, etc.).
3. `ae-motion` installed and its `dist/index.js` built.
4. `DEEPSEEK_API_KEY` only when generating a new scene plan with `main.py`. The HUD director itself does not call DeepSeek.
5. `ANTHROPIC_API_KEY` only if optional Claude QA is enabled.

## Run

Open PowerShell in the project folder:

```powershell
# Reuse Plans/scene_plan.json; no DeepSeek planning request
python main.py

# Create a new plan (this makes one DeepSeek planning request)
$env:REGENERATE_SCENE_PLAN = "1"
python main.py
Remove-Item Env:REGENERATE_SCENE_PLAN

# Build and render the planned scenes
python ai_director.py
```

The default MCP path is:
`C:\Users\ACER\Documents\ae-motion\dist\index.js`

If yours differs:

```powershell
$env:AE_MCP_SERVER_SCRIPT = "D:\path\to\ae-motion\dist\index.js"
```

## Optional controls

```powershell
# Claude Vision quality review (additional Anthropic API usage); OFF by default
$env:AE_ENABLE_CLAUDE_QA = "1"

# Quick draft render rather than full quality
$env:AE_RENDER_DRAFT = "1"

# Render via ae-motion's ffmpeg delivery path (requires ffmpeg)
$env:AE_RENDER_DELIVER = "1"

# Maximum render wait; default 900 seconds
$env:AE_RENDER_TIMEOUT_SECONDS = "900"
```

Unset optional variables to return to defaults. Claude rejection does not block a render.

## Output

- Editable projects: `Projects/scene_N.aep`
- Preview stills: `Exports/test_scene_N.png`
- Renders: `Exports/scene_NN.mp4` (the final extension is determined by the active AE output module; ae-motion reports the actual path).

## Troubleshooting

- If `save_project` fails, check the ae-motion allowed project directories and whether After Effects has a modal dialog open.
- If `render_start` fails with "Project has never been saved", do not rerun the full pipeline repeatedly. Confirm the AEP exists and that After Effects can save to the configured project directory.
- If render status says the job is still running, leave After Effects/aerender open. The script polls the job; it does not launch duplicate renders.
- If AE is busy with another render, wait for it to finish before restarting.
