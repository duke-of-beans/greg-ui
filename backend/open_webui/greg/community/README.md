# Community plugins

Open WebUI community plugins Greg ships with, seeded by `greg_seed.py` (functions into the Function table, tools into the
Tool table). Each file is the upstream source at the commit below, read in full for secret access, outbound hosts,
shell or `eval` use and database writes before it was vendored (order wo-20261105-46fd276f, 2026-11-05).

To update one: copy the new upstream file over it, read the diff, record the new commit here, ship through the git plane.
Admin-panel toggles and valves survive updates (`keep_settings`); only the code is replaced.

| File | Upstream | Licence | Review notes |
|---|---|---|---|
| inline_visualizer.py | classic298/open-webui-plugins@917c88f `inline-visualizer-v2/tool.py` | BSD-3 | Rendered HTML loads libraries from jsdelivr, cdnjs, unpkg in the browser. No server-side network. |
| email_composer.py | classic298/open-webui-plugins@917c88f `email-composer/tool.py` | BSD-3 | No network; draft card with copy and mailto. |
| vision_bridge.py | classic298/open-webui-plugins@917c88f `vision-bridge/filter.py` | BSD-3 | **Changed:** `purge_from_history` and `delete_file_record` default to off (upstream deletes the image after describing it). |
| token_usage.py | SmetDenis/openwebui-token-usage-display@8329118 `usage_display.py` | MIT | Optional models.dev lookup; optional llama.cpp probe sends a connection's own key only to that connection's own URL. |
| smart_mind_map.py, infographic.py, deep_dive.py, export_word.py, export_excel.py | Fu-Jie/openwebui-extensions@76e9d99 `plugins/actions/...` | MIT | Browser-side CDN libraries only. Export to Word's pip deps are pinned in `backend/requirements.txt`. |
| smart_mind_map_tool.py | Fu-Jie/openwebui-extensions@76e9d99 `plugins/tools/smart-mind-map-tool` | MIT | As the action. |
| folder_memory.py, markdown_normalizer.py | Fu-Jie/openwebui-extensions@76e9d99 `plugins/filters/...` | MIT | Folder Memory writes the folder's system prompt (its purpose). |
| clean_thinking.py, doodle_paint.py | Haervwe/open-webui-tools@c1fac21 `filters/...` | MIT | No network. |
| planner_v3.py, mopidy.py | Haervwe/open-webui-tools@c1fac21 `functions/...` | MIT | Seeded off (pipes show up as models). Planner reads only `WEBUI_URL` from the environment. |
| outagedeck.py, youtube.py, weather.py, model_3d_viewer.py | Haervwe/open-webui-tools@c1fac21 `tools/...` | MIT | Talk only to their service (outagedeck.com, googleapis.com, openweathermap.org). YouTube and weather need an API key valve. |
| jellyfin.py | iChristGit/OpenWebui-Tools@af6a490 `Tools/jellyfin.py` | MIT | Talks only to the Jellyfin URL set in its valves. |
| mcp_app_bridge.py | classic298/open-webui-plugins@917c88f `mcp-app-bridge/tool.py` | BSD-3 | Talks only to the MCP server set in its valves; OAuth client info is stored encrypted in its own valves. Needs Open WebUI 0.11.4+ (added with the 0.12.5 upstream merge). |
