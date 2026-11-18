"""
Health check script for oil-delegate-local on the current Windows machine.
Checks Python interpreter, DeepSeek Harness CLI, Codex CLI, API keys, and account balances.
"""
import os
import sys
import json
import urllib.request
import urllib.error
import subprocess

def get_env_or_reg(var_name):
    val = os.environ.get(var_name)
    if val:
        return val
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        val, _ = winreg.QueryValueEx(key, var_name)
        winreg.CloseKey(key)
        return val
    except Exception:
        return None

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(script_dir, "local_env.json")
    cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as fp:
            cfg = json.load(fp)

    dsh_bin = cfg.get("dsh_binary", r"E:\A001-软件安装\deepseek\resources\runtime\cli\bin\dsh.cmd")
    codex_bin = cfg.get("codex_binary", r"C:\Users\fight\AppData\Local\OpenAI\Codex\bin\9e1da79431da526b\codex.exe")
    api_key = get_env_or_reg("DEEPSEEK_API_KEY")

    codex_auth_file = os.path.expanduser("~/.codex/auth.json")

    report = {
        "machine": "LOCAL-WINDOWS",
        "python_version": sys.version.split()[0],
        "deepseek": {
            "binary_exists": os.path.exists(dsh_bin),
            "binary_path": dsh_bin,
            "version": None,
            "api_key_configured": bool(api_key),
            "api_key_masked": f"{api_key[:6]}...{api_key[-4:]}" if api_key and len(api_key) > 10 else None,
            "official_api_status": "unknown",
            "balance_info": None,
            "ready": False
        },
        "codex": {
            "binary_exists": os.path.exists(codex_bin),
            "binary_path": codex_bin,
            "version": None,
            "auth_file_exists": os.path.exists(codex_auth_file),
            "ready": False
        },
        "enabled_runners": cfg.get("enabled_runners", ["dsh", "codex"]),
        "ready": False
    }

    # Check dsh version
    if os.path.exists(dsh_bin):
        try:
            res = subprocess.run([dsh_bin, "--version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                report["deepseek"]["version"] = res.stdout.strip()
        except Exception as e:
            report["deepseek"]["probe_error"] = str(e)

    # Check Codex version & auth
    if os.path.exists(codex_bin):
        try:
            res = subprocess.run([codex_bin, "--version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                report["codex"]["version"] = res.stdout.strip()
                report["codex"]["ready"] = bool(report["codex"]["auth_file_exists"])
        except Exception as e:
            report["codex"]["probe_error"] = str(e)

    # Check DeepSeek official balance
    if api_key:
        req = urllib.request.Request(
            "https://api.deepseek.com/user/balance",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                report["deepseek"]["official_api_status"] = "OK" if data.get("is_available") else "UNAVAILABLE"
                report["deepseek"]["balance_info"] = data.get("balance_infos")
                report["deepseek"]["ready"] = bool(report["deepseek"]["official_api_status"] == "OK" and report["deepseek"]["binary_exists"])
        except urllib.error.HTTPError as e:
            report["deepseek"]["official_api_status"] = f"HTTP Error {e.code}: {e.reason}"
        except Exception as e:
            report["deepseek"]["official_api_status"] = f"Network Error: {str(e)}"

    report["ready"] = bool(report["deepseek"]["ready"] or report["codex"]["ready"])

    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
