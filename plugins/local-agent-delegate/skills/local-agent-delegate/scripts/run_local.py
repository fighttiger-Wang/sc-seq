"""
Local runner wrapper for E06 · 红蓝对抗闭环.
Automatically loads environment, dynamically discovers the latest Codex binary,
and calls delegate.py using the validated local Python environment.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


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


def discover_codex_binary(cfg):
    env_bin = os.environ.get("OIL_DELEGATE_CODEX_BIN")
    if env_bin and os.path.exists(env_bin):
        return env_bin

    if os.name == "nt":
        local_app = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        bin_root = local_app / "OpenAI" / "Codex" / "bin"
        if bin_root.is_dir():
            candidates = sorted(
                bin_root.glob("*/codex.exe"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for cand in candidates:
                if cand.is_file():
                    return str(cand.resolve())

    which_bin = shutil.which("codex")
    if which_bin and os.path.exists(which_bin):
        return which_bin

    cfg_bin = cfg.get("codex_binary")
    if cfg_bin and cfg_bin != "auto" and os.path.exists(cfg_bin):
        return cfg_bin
    return None


def print_help_menu():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cm_script = os.path.join(script_dir, "critic_manager.py")
    if os.path.exists(cm_script):
        subprocess.run([sys.executable, cm_script, "table"])
    else:
        print("E06 红蓝对抗闭环速查菜单已就绪。输入 '.?' 查看详情。")


def main():
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] in (".?", "?", "？", "help", "-h", "--help")):
        print_help_menu()
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1].lower() in ("lineup", "roster", "阵容"):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cm_script = os.path.join(script_dir, "critic_manager.py")
        cmd = [sys.executable, cm_script, "lineup"] + sys.argv[2:]
        sys.exit(subprocess.run(cmd).returncode)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(script_dir, "local_env.json")
    delegate_py = os.path.join(script_dir, "delegate.py")

    cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as fp:
            cfg = json.load(fp)

    env = os.environ.copy()

    COMMON_KEYS = [
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
        "XAI_API_KEY",
        "OPENCODE_API_KEY",
    ]
    for key_name in COMMON_KEYS:
        val = get_env_or_reg(key_name)
        if val:
            env[key_name] = val

    dsh_bin = cfg.get("dsh_binary", r"E:\A001-软件安装\deepseek\resources\runtime\cli\bin\dsh.cmd")
    if os.path.exists(dsh_bin):
        env["OIL_DELEGATE_DSH_BIN"] = dsh_bin

    codex_bin = discover_codex_binary(cfg)
    if codex_bin:
        env["OIL_DELEGATE_CODEX_BIN"] = codex_bin

    cmd = [sys.executable, delegate_py] + sys.argv[1:]
    res = subprocess.run(cmd, env=env)
    sys.exit(res.returncode)


if __name__ == "__main__":
    main()
