"""
Local runner wrapper for oil-delegate-local.
Automatically loads environment, ensures API keys for supported runners are active,
and calls delegate.py using the validated local Python environment.
"""
import os
import sys
import json
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

def print_help_menu():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cm_script = os.path.join(script_dir, "critic_manager.py")
    if os.path.exists(cm_script):
        subprocess.run([sys.executable, cm_script, "table"])
    else:
        print("E06 本机智能体委托速查菜单已就绪。输入 '?' 查看详情。")

def main():
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] in ("?", "？", "help", "-h", "--help")):
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

    # Auto-detect and inject API keys for supported runners from Env or Windows Registry
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

    codex_bin = cfg.get("codex_binary", r"C:\Users\fight\AppData\Local\OpenAI\Codex\bin\9e1da79431da526b\codex.exe")
    if os.path.exists(codex_bin):
        env["OIL_DELEGATE_CODEX_BIN"] = codex_bin

    # Forward all command line arguments to delegate.py
    cmd = [sys.executable, delegate_py] + sys.argv[1:]
    res = subprocess.run(cmd, env=env)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
