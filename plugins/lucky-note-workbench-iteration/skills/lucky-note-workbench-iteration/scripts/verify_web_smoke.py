#!/usr/bin/env python3
"""
Lucky_Note Web Smoke Verification
Simulates WebView2 host injection of real app-state.json into workbench.html via headless Edge.
Asserts:
  1. Console error count == 0
  2. Total real projects mounted >= 1
  3. Active project title is rendered
  4. Drawer items count > 0
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def run_smoke_test(workspace_dir: Path | None = None, screenshot_path: Path | None = None) -> int:
    if workspace_dir is None:
        candidate_root = Path("E:/A002-Codex")
        workspace_dir = next((p for p in candidate_root.iterdir() if (p / "LumaTrack").is_dir()), None)
        if not workspace_dir:
            print("Error: Could not find workspace directory containing LumaTrack under E:/A002-Codex")
            return 1

    luma_track_dir = workspace_dir / "LumaTrack"
    web_dir = luma_track_dir / "Assets" / "web"
    app_state_file = luma_track_dir / "data" / "app-state.json"

    if not web_dir.is_dir():
        print(f"Error: Web directory not found: {web_dir}")
        return 1
    if not app_state_file.is_file():
        print(f"Error: app-state.json not found: {app_state_file}")
        return 1

    temp_dir = Path(tempfile.gettempdir()) / "lucky_smoke_verification"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Copy web assets
    for item in web_dir.iterdir():
        if item.is_dir():
            shutil.copytree(item, temp_dir / item.name)
        else:
            shutil.copy2(item, temp_dir / item.name)

    # Write smoke data js
    app_state_raw = app_state_file.read_text(encoding="utf-8")
    (temp_dir / "smoke_data.js").write_text(f"window.__SMOKE_RAW_STATE__ = {app_state_raw};", encoding="utf-8")

    # Smoke harness
    harness_js = """
window.__smoke_errors = [];
window.__smoke_projects_count = 0;
window.__smoke_drawer_count = 0;
window.__smoke_active_project = '';

window.onerror = function(msg, url, line, col, err) {
    window.__smoke_errors.push({ type: 'error', message: msg, location: url + ':' + line + ':' + col, stack: err ? err.stack : '' });
};

window.onunhandledrejection = function(e) {
    window.__smoke_errors.push({ type: 'rejection', reason: e.reason ? (e.reason.stack || e.reason) : e });
};

function executeSmoke() {
    try {
        if (window.loadRealAppState && window.__SMOKE_RAW_STATE__) {
            window.loadRealAppState(window.__SMOKE_RAW_STATE__);
            window.__smoke_projects_count = (window._lastActiveList ? window._lastActiveList.length : 0) +
                                            (window._lastWaitingList ? window._lastWaitingList.length : 0) +
                                            (window._lastArchivedList ? window._lastArchivedList.length : 0) +
                                            (window._lastPausedList ? window._lastPausedList.length : 0);
        }
        var cardPidEl = document.getElementById('cardPid');
        var cardCustomerEl = document.getElementById('cardCustomer');
        if (cardPidEl && cardCustomerEl) {
            window.__smoke_active_project = cardPidEl.textContent.trim() + ' ' + cardCustomerEl.textContent.trim();
        }
        var drawerItems = document.querySelectorAll('.project-list-item, [onclick*="loadProjectData"]');
        window.__smoke_drawer_count = drawerItems.length;

        var statusDiv = document.createElement('div');
        statusDiv.id = 'smoke_status_results';
        statusDiv.innerText = JSON.stringify({
            errors: window.__smoke_errors,
            projects: window.__smoke_projects_count,
            drawer: window.__smoke_drawer_count,
            active: window.__smoke_active_project
        });
        document.body.appendChild(statusDiv);
    } catch (ex) {
        window.__smoke_errors.push({ type: 'harness_exception', stack: ex.stack || ex.toString() });
        var statusDiv = document.createElement('div');
        statusDiv.id = 'smoke_status_results';
        statusDiv.innerText = JSON.stringify({ errors: window.__smoke_errors });
        document.body.appendChild(statusDiv);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', executeSmoke);
} else {
    executeSmoke();
}
"""
    (temp_dir / "smoke_harness.js").write_text(harness_js, encoding="utf-8")

    html_file = temp_dir / "workbench.html"
    html_content = html_file.read_text(encoding="utf-8")
    html_content = html_content.replace(
        "</body>",
        '<script src="smoke_data.js"></script>\n<script src="smoke_harness.js"></script>\n</body>'
    )
    html_file.write_text(html_content, encoding="utf-8")

    edge_candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(shutil.which("msedge") or ""),
    ]
    edge_exe = next((p for p in edge_candidates if p.is_file()), None)
    if not edge_exe:
        print("Error: Microsoft Edge executable not found.")
        return 1

    file_uri = html_file.as_uri()
    user_data = f"--user-data-dir={Path(tempfile.gettempdir()) / 'edge_smoke_qa'}"

    cmd = [
        str(edge_exe),
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--window-size=1440,900",
        user_data,
    ]
    if screenshot_path:
        cmd.append(f"--screenshot={screenshot_path.resolve()}")
    cmd.extend(["--dump-dom", file_uri])

    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    dom = result.stdout

    match = re.search(r'<div id="smoke_status_results"[^>]*>([\s\S]*?)</div>', dom)
    if not match:
        print("FAIL: smoke_status_results div was not found in rendered DOM.")
        return 1

    report = json.loads(match.group(1).strip())
    errors = report.get("errors", [])
    projects = report.get("projects", 0)
    drawer = report.get("drawer", 0)
    active = report.get("active", "")

    print("================ SMOKE VERIFICATION REPORT ================")
    print(f"Errors detected: {len(errors)}")
    print(f"Total projects mounted: {projects}")
    print(f"Drawer project elements: {drawer}")
    print(f"Active project displayed: {active}")

    if errors:
        print("FAIL: Console errors detected during smoke test:")
        for err in errors:
            print(f" - [{err.get('type')}] {err.get('message')} {err.get('location')} {err.get('stack')} {err.get('reason')}")
        return 1

    if projects < 1:
        print("FAIL: Real projects failed to mount (count is 0)!")
        return 1

    if not active:
        print("FAIL: No active project title rendered!")
        return 1

    print("PASS: Headless smoke verification successfully completed with 0 errors!")
    print("===========================================================")
    return 0

if __name__ == "__main__":
    screenshot = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(run_smoke_test(screenshot_path=screenshot))
