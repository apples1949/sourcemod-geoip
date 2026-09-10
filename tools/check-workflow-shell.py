#!/usr/bin/env python3
"""对工作流里所有 `run:` 的 shell 脚本做语法检查（bash -n）。

为什么需要：工作流的 `run:` 本身就是 shell 脚本，但平时不会被任何语法检查覆盖 ——
CI 跑起来才报错，反馈慢。之前把 heredoc 写进 `run:` 时弄坏过 YAML 缩进即属此类。

用法:
    python3 tools/check-workflow-shell.py [工作流文件...]

默认检查 .github/workflows/ 下的全部 *.yml；找不到 bash 时跳过（不算失败）。
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

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


def main():
    args = sys.argv[1:]
    if args:
        files = args
    else:
        files = sorted(glob.glob(os.path.join(REPO, ".github", "workflows", "*.yml")))

    bash = find_bash()
    if bash is None:
        print("未找到 bash，跳过工作流 shell 语法检查")
        return 0

    tmp = tempfile.mkdtemp(prefix="wfsyntax-")
    checked = failed = 0

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
                shell = step.get("shell")
                if not run or (shell is not None and shell != "bash"):
                    continue
                label = step.get("name") or step.get("uses") or "step%d" % idx
                # GitHub 表达式换成占位符：整行删除会打断 if/else 之类的控制流
                cleaned = re.sub(r"\$\{\{[^}]*\}\}", "PLACEHOLDER", run)
                p = os.path.join(tmp, "%s-%s-%d.sh" % (name, job_name, idx))
                with open(p, "w", encoding="utf-8", newline="\n") as fp:
                    fp.write(cleaned)

                r = subprocess.run([bash, "-n", p], capture_output=True,
                                   encoding="utf-8", errors="replace")
                checked += 1
                if r.returncode == 0:
                    print("  [ok]   %-22s %-10s %s" % (name, job_name, label))
                else:
                    failed += 1
                    err = (r.stderr or "").strip().splitlines()
                    print("  [FAIL] %-22s %-10s %s" % (name, job_name, label))
                    print("         %s" % (err[0][:160] if err else "(no output)"))

    print()
    print("检查 %d 个 shell 步骤，失败 %d 个" % (checked, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
