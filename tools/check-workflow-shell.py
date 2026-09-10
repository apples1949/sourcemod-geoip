#!/usr/bin/env python3
"""对工作流里所有 `run:` 脚本做语法检查。

- `shell: bash`（或默认）：用 bash -n
- `shell: pwsh` / `powershell`：用 pwsh 的 AST 解析器

为什么需要：工作流的 `run:` 本身就是脚本，但平时不会被任何语法检查覆盖 ——
CI 跑起来才报错，反馈慢。之前把 heredoc 写进 `run:` 时弄坏过 YAML 缩进即属此类。

用法:
    python3 tools/check-workflow-shell.py [工作流文件...]

默认检查 .github/workflows/ 下的全部 *.yml；找不到对应解释器时跳过（不算失败）。
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

# Windows 上 stdout 默认是 cp1252/ANSI，打印中文会抛 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

try:
    import yaml
except ImportError:
    print("需要 PyYAML：python3 -m pip install pyyaml", file=sys.stderr)
    sys.exit(2)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_bash():
    b = shutil.which("bash")
    if b:
        return b
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files\Git\usr\bin\bash.exe"):
        if os.path.exists(cand):
            return cand
    return None


def find_pwsh():
    for name in ("pwsh", "powershell"):
        b = shutil.which(name)
        if b:
            return b
    return None


# PowerShell 语法检查：用内置 AST 解析器解析文本（不做实际执行）。
# 注意：pwsh 的 -Command 会把后面的参数**拼接进脚本文本**（不是分开传参），
# 直接多传一个路径会被拼成 "...exit 0C:\path\to.ps1" 而报错。
# 因此通过环境变量传路径，彻底绕开引号/拼接问题。
PS_PARSE = (
    "$e=$null;"
    "$t=[System.IO.File]::ReadAllText($env:WF_PS1);"
    "[void][System.Management.Automation.Language.Parser]::ParseInput($t,[ref]$null,[ref]$e);"
    "if($e -and $e.Count){$e|ForEach-Object{Write-Output $_.Message};exit 1};exit 0"
)


def main():
    args = sys.argv[1:]
    if args:
        files = args
    else:
        files = sorted(glob.glob(os.path.join(REPO, ".github", "workflows", "*.yml")))

    bash = find_bash()
    pwsh = find_pwsh()
    if bash is None:
        print("未找到 bash，跳过 shell 语法检查")
    if pwsh is None:
        print("未找到 pwsh/powershell，跳过 PowerShell 语法检查")

    tmp = tempfile.mkdtemp(prefix="wfsyntax-")
    checked = failed = skipped = 0

    for wf_path in files:
        name = os.path.basename(wf_path)
        try:
            wf = yaml.safe_load(open(wf_path, encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print("  [FAIL] %s 无法解析 YAML: %s" % (name, exc))
            failed += 1
            continue

        for job_name, job in (wf.get("jobs") or {}).items():
            for idx, step in enumerate(job.get("steps", []) or []):
                run = step.get("run")
                if not run:
                    continue
                shell = (step.get("shell") or "").lower()
                label = step.get("name") or step.get("uses") or "step%d" % idx
                # GitHub 表达式换成占位符：整行删除会打断 if/else 之类的控制流
                cleaned = re.sub(r"\$\{\{[^}]*\}\}", "PLACEHOLDER", run)

                if shell.startswith("pwsh") or shell.startswith("powershell"):
                    if pwsh is None:
                        skipped += 1
                        continue
                    p = os.path.join(tmp, "%s-%s-%d.ps1" % (name, job_name, idx))
                    with open(p, "w", encoding="utf-8", newline="\n") as fp:
                        fp.write(cleaned)
                    env = dict(os.environ, WF_PS1=p)
                    r = subprocess.run([pwsh, "-NoProfile", "-Command", PS_PARSE],
                                       capture_output=True, encoding="utf-8",
                                       errors="replace", env=env)
                else:
                    if bash is None:
                        skipped += 1
                        continue
                    p = os.path.join(tmp, "%s-%s-%d.sh" % (name, job_name, idx))
                    with open(p, "w", encoding="utf-8", newline="\n") as fp:
                        fp.write(cleaned)
                    r = subprocess.run([bash, "-n", p], capture_output=True,
                                       encoding="utf-8", errors="replace")

                checked += 1
                if r.returncode == 0:
                    print("  [ok]   %-12s %-10s %s" % (name, job_name, label))
                else:
                    failed += 1
                    err = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()
                    print("  [FAIL] %-12s %-10s %s" % (name, job_name, label))
                    print("         %s" % (err[0][:160] if err else "(no output)"))

    print()
    print("检查 %d 个脚本步骤，失败 %d 个%s" % (
        checked, failed, "，跳过 %d 个（缺解释器）" % skipped if skipped else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
