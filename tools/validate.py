#!/usr/bin/env python3
"""校验本仓库的完整性：文件清单、YAML 工作流、脚本关键点、编码/行尾。"""
import glob
import hashlib
import io
import os
import re
import sys
import subprocess

# Windows 控制台默认 GBK/cp1252，直接 print 中文会乱码/抛错
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

REPO = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(REPO) if os.path.basename(REPO) == "tools" else REPO

fail = []
warn = []


def ok(msg):
    print(f"  [ok]   {msg}")


def bad(msg):
    fail.append(msg)
    print(f"  [FAIL] {msg}")


def wrn(msg):
    warn.append(msg)
    print(f"  [warn] {msg}")


EXPECTED_GEOIP = [
    "AMBuilder", "data-pool.c", "data-pool.h", "extension.cpp", "extension.h",
    "geoip_util.cpp", "geoip_util.h", "maxminddb-compat-util.h", "maxminddb.c",
    "maxminddb.h", "maxminddb_config.h", "osdefs.h", "smsdk_config.h", "version.rc",
]

# 上游 1.12-dev 的 SHA256（GitHub raw 内容哈希需按 LF 计算，这里用字节长度+sha 记录）
EXPECTED_AMBUILDER_SHA = "aa3d9c64d59020bf1b625a38bf000df2e0418f7935bb241af3a99d34cc6b0e7f"

print("=" * 68)
print("1. 仓库文件清单")
print("=" * 68)
geoip_dir = os.path.join(REPO, "extensions", "geoip")
if not os.path.isdir(geoip_dir):
    bad("缺少 extensions/geoip 目录")
else:
    present = {f for f in os.listdir(geoip_dir)}
    for name in EXPECTED_GEOIP:
        if name in present:
            ok(f"extensions/geoip/{name}")
        else:
            bad(f"缺少 extensions/geoip/{name}")
    extra = present - set(EXPECTED_GEOIP) - {"README.md"}
    if extra:
        wrn(f"extensions/geoip 存在未预期文件: {sorted(extra)}")

for rel in [".github/workflows/build.yml", "tools/build-geoip.sh", "README.md",
            ".gitignore", ".gitattributes", "LICENSE",
            "tools/filter-build-scripts.py", "tools/check-workflow-shell.py",
            "patches/README.md", "patches/geoip_fix_2335.patch"]:
    if os.path.isfile(os.path.join(REPO, rel)):
        ok(rel)
    else:
        bad(f"缺少 {rel}")

print()
print("=" * 68)
print("1b. 本仓库的立身之本：PR #2335 中文语言码修复")
print("=" * 68)
# GeoIP 在中文环境下拿不到中文译名（translator 给 chi，mmdb 要 zh-CN）。
# 上游只在 master(1.13) / 1.12-dev 修了，1.11-dev 没有；本仓库就是为了
# 让 1.11 也能用上带修复的版本，所以这条必须始终成立。
LANG_FIX_MARK = 'strcmp(code, "chi")'
util_path = os.path.join(geoip_dir, "geoip_util.cpp")
util = open(util_path, "rb").read().decode("utf-8", "replace") \
    if os.path.isfile(util_path) else ""
if not util:
    bad("缺少 extensions/geoip/geoip_util.cpp，无法核验中文修复")
else:
    if LANG_FIX_MARK in util:
        ok(f"源码已含 PR #2335 修复标记（{LANG_FIX_MARK}）")
    else:
        bad(f"源码缺少 PR #2335 修复标记（{LANG_FIX_MARK}）——"
            f"1.11 平台将拿不到中文译名（构建脚本会尝试打补丁，但建议直接从 1.12-dev 同步）")
    if 'code = "zh-CN";' in util:
        ok('源码含 code = "zh-CN" 归一化赋值')
    else:
        bad('源码缺少 code = "zh-CN" 归一化赋值')

sh_path_early = os.path.join(REPO, "tools", "build-geoip.sh")
if os.path.isfile(sh_path_early):
    build_sh = open(sh_path_early, "r", encoding="utf-8").read()
    for needle, why in [
        ("geoip_fix_2335.patch", "构建脚本引用 PR #2335 补丁"),
        ("LANG_FIX_MARK", "构建脚本做修复标记查找"),
        ("apply_lang_fix", "构建脚本带补丁应用逻辑"),
    ]:
        if needle in build_sh:
            ok(why)
        else:
            bad(f"构建脚本缺少{why}（{needle}）")

patch_path = os.path.join(REPO, "patches", "geoip_fix_2335.patch")
if os.path.isfile(patch_path):
    praw = open(patch_path, "rb").read()
    ptxt = praw.decode("utf-8", "replace")
    if ptxt.startswith("--- "):
        ok("补丁文件以 --- 开头（标准 unified diff，可被 patch(1) 直接读取）")
    else:
        bad("补丁文件开头不是 --- ，patch(1) 可能无法解析")
    if ptxt.count("@@") == 0:
        bad("补丁文件不含 hunk（@@）")
    else:
        ok(f"补丁含 {ptxt.count('@@') // 2} 个 hunk 段")
    if LANG_FIX_MARK in ptxt:
        ok("补丁内容包含 chi 归一化修复")
    else:
        bad("补丁内容不含 chi 归一化修复")
    if not praw.endswith(b"\n"):
        wrn("补丁文件末尾缺少换行，部分 patch(1) 实现可能告警")
    else:
        ok("补丁文件以换行结尾（标准 unified diff 格式）")
    if b"\r\n" in praw:
        bad("补丁文件含 CRLF 行尾，patch(1) 可能匹配失败（应为 LF）")
    else:
        ok("补丁文件为 LF 行尾")
    if ptxt.lstrip().startswith("#"):
        bad("补丁文件含前导注释行，patch(1) 无法解析（说明性内容请写进 patches/README.md）")

print()
print("=" * 68)
print("2. AMBuilder 与上游一致性（决定能否在源码树中编译）")
print("=" * 68)
amb = os.path.join(geoip_dir, "AMBuilder")
if os.path.isfile(amb):
    raw = open(amb, "rb").read().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    if sha == EXPECTED_AMBUILDER_SHA:
        ok(f"AMBuilder 与上游 1.12-dev 字节一致 (sha256={sha[:16]}…)")
    else:
        bad(f"AMBuilder 与上游不一致: {sha}")
    txt = raw.decode("utf-8")
    # 关键：相对路径深度必须保持 ../../public
    if "../../public/smsdk_ext.cpp" in txt:
        ok("AMBuilder 保留相对路径 ../../public/smsdk_ext.cpp（目录深度必须为 extensions/geoip）")
    else:
        bad("AMBuilder 未使用 ../../public/smsdk_ext.cpp —— 目录位置会被破坏")
    for src in ["extension.cpp", "geoip_util.cpp", "data-pool.c", "maxminddb.c"]:
        if src in txt:
            ok(f"AMBuilder 引用 {src}")
        else:
            bad(f"AMBuilder 未引用 {src}")
    if "-fno-rtti" in txt and "/GR-" in txt:
        ok("AMBuilder 同时处理 gcc/clang 与 msvc")
else:
    bad("无法读取 AMBuilder")

print()
print("=" * 68)
print("3. 工作流 YAML 校验")
print("=" * 68)
wf_path = os.path.join(REPO, ".github", "workflows", "build.yml")
try:
    import yaml
    with open(wf_path, "r", encoding="utf-8") as fp:
        wf = yaml.safe_load(fp)
    ok("YAML 语法有效")

    # PyYAML 会把裸 on: 解析成 True，两种都要兼容
    triggers = wf.get("on", wf.get(True))
    if not isinstance(triggers, dict):
        bad(f"on: 解析异常: {triggers!r}")
        triggers = {}
    for t in ["push", "pull_request", "workflow_dispatch"]:
        if t in triggers:
            ok(f"触发条件包含 {t}")
        else:
            wrn(f"触发条件缺少 {t}")

    jobs = wf.get("jobs", {})
    if "build" not in jobs:
        bad("缺少 jobs.build")
    else:
        ok("存在 jobs.build")
        build = jobs["build"]
        matrix = (build.get("strategy", {}) or {}).get("matrix", {}) or {}
        entries = matrix.get("include", [])
        if not entries:
            bad("矩阵不是 include: 形式，无法确认平台覆盖")
        combos = {(str(e.get("os_short")), str(e.get("sm_branch"))) for e in entries}
        # 两个平台 × 两个 SourceMod 版本都要覆盖：
        # DLL 里同样编入了对应分支的版本信息与接口（同 Linux 的 .so），
        # 不能拿 1.12 的 DLL 去配 1.11 的服务端。
        for want in [("linux", "1.11-dev"), ("linux", "1.12-dev"),
                     ("windows", "1.11-dev"), ("windows", "1.12-dev")]:
            if want in combos:
                ok(f"矩阵包含 {want[0]} / SourceMod {want[1]}")
            else:
                bad(f"矩阵缺少 {want[0]} / SourceMod {want[1]}")
        if any(os_name == "windows" for os_name, _ in combos):
            ok("包含 Windows 构建")
        else:
            bad("未包含 Windows 构建")
        # Windows 条目必须用 MSVC 自动探测（不能沿用 clang-14 这类 Linux 编译器名）
        for e in entries:
            if str(e.get("os_short")) == "windows":
                if str(e.get("cxx", "")).strip():
                    wrn(f"Windows 条目指定了 CXX={e.get('cxx')}；Windows 上建议留空交由 AMBuild 探测 MSVC")
                else:
                    ok("Windows 条目不指定 CXX，交由 AMBuild 自动探测 MSVC")
                if str(e.get("ext")) != "dll":
                    bad("Windows 条目的产物扩展名应为 dll")
                else:
                    ok("Windows 产物扩展名为 dll")
        # 工具链必须显式安装：曾经照搬官方 CI 的第三方镜像，
        # 结果容器里没有 clang++（PATH 中找不到编译器）导致构建直接失败。
        runs_all = "\n".join(str(s.get("run", "")) for s in build.get("steps", []))
        if build.get("container"):
            wrn("仍在使用 container（请确认镜像内确实有可用的 C++ 编译器）")
        else:
            ok("未依赖第三方构建镜像（工具链在本工作流内显式安装）")

        if "clang-14" in runs_all:
            ok("Linux 使用 clang-14（与 SourceMod 官方 PR 检查一致）")
        else:
            bad("未固定 Linux 的 clang-14")

        # 致命陷阱：任何**无条件**的步级/任务级 env 里出现 CC/CXX 并引用 matrix 键，
        # 在缺少该键的条目（Windows）上会渲染成空字符串并被导出为环境变量。
        # AMBuild 的 detect_from_env() 优先读 CC/CXX，空值使探测命令里编译器名变空，
        # 报 "Unable to find a suitable C compiler"（MSVC 其实已装好）。
        # 这个坑踩了两次：先写在 job 级 env，再写到 Build 步骤的 env —— 都是无条件生效。
        wf_steps = build.get("steps", [])
        offenders = []
        for scope_name, scope_env in [("job 级 env", build.get("env") or {})] + \
                [("步骤 %r 的 env" % (s.get("name") or s.get("uses")),
                  s.get("env") or {}) for s in wf_steps]:
            for var in ("CC", "CXX"):
                v = str(scope_env.get(var, ""))
                if v and "matrix." in v:
                    offenders.append((scope_name, var, v))
        if offenders:
            for scope_name, var, v in offenders:
                bad(f"{scope_name} 无条件设置 {var}={v}：缺该 matrix 键的条目会得到空字符串，"
                    f"AMBuild 将找不到编译器（应改为按平台在条件步骤里设置）")
        else:
            ok("CC/CXX 未出现在无条件 env 中（不会在 Windows 上变成空字符串）")

        # 必须有一个仅在 Linux 生效的步骤来设置 CC/CXX
        linux_env_step = None
        for s in wf_steps:
            run = str(s.get("run", ""))
            if "GITHUB_ENV" in run and ("CC=" in run or "CXX=" in run):
                linux_env_step = s
                break
        if linux_env_step is None:
            wrn("未找到通过 GITHUB_ENV 设置 CC/CXX 的步骤")
        else:
            cond = str(linux_env_step.get("if", ""))
            if "Linux" in cond:
                ok(f"CC/CXX 仅在条件步骤中设置（if: {cond}）")
            else:
                bad(f"设置 CC/CXX 的步骤没有平台条件（if: {cond!r}）—— 其他平台会拿到空值")
        if "windows-2022" in str(matrix):
            ok("Windows 使用 windows-2022 runner（自带 MSVC）")
        else:
            wrn("未指定 windows-2022 runner")
        # cl.exe 默认不在 PATH，必须加载 VS 开发者环境，否则 AMBuild 报
        # "Unable to find a suitable C compiler"（探测命令里编译器名是空的）
        if "vcvarsall" in runs_all and "vswhere" in runs_all:
            ok("用 vswhere + vcvarsall 加载 MSVC 环境")
        else:
            bad("未加载 MSVC 开发者环境（vcvarsall）—— Windows 上 DetectCxx 会失败")
        if "vcvarsall.bat\" x86" in yaml.dump(build) or "vcvarsall`\" x86" in yaml.dump(build) \
           or "vcvars`\" x86" in yaml.dump(build, allow_unicode=True):
            ok("vcvarsall 使用 x86（目标架构是 32 位）")
        elif "x86" in runs_all and "vcvarsall" in runs_all:
            ok("vcvarsall 参数包含 x86（目标架构是 32 位）")
        else:
            wrn("未确认 vcvarsall 使用 x86 参数（32 位目标）")
        if "cl.exe 不在 PATH" in runs_all or "command -v cl" in runs_all:
            ok("校验 cl.exe 确实可用")
        else:
            wrn("未校验 cl.exe 是否真的进入 PATH")

        # 写 $GITHUB_ENV 不能带 BOM：Windows PowerShell 5.1 的 `Out-File -Encoding utf8`
        # 会写入 EF BB BF，污染文件第一行、导致其中一条变量失效（已实测确认）。
        # 逐行去注释：yaml.dump 会转义块标量的换行，所以不能用 dump 文本按行过滤。
        runs_lines = []
        for s in build.get("steps", []):
            r = s.get("run")
            if r:
                runs_lines.extend(r.splitlines())
        ps_code_only = "\n".join(
            ln for ln in runs_lines if not ln.lstrip().startswith("#"))
        if re.search(r"Out-File[^\n]*GITHUB_ENV", ps_code_only):
            bad("用 Out-File 写 $GITHUB_ENV：Windows PowerShell 会写入 BOM，导致首行变量失效")
        elif "GITHUB_ENV" in ps_code_only:
            ok("写 $GITHUB_ENV 未使用 Out-File（避免 BOM 污染）")

        if "matrix.cc" in str(build.get("env", {})) or "matrix.cxx" in str(build.get("env", {})):
            ok("CC/CXX 由矩阵按平台注入（Windows 留空即自动探测）")

        steps = build.get("steps", [])
        runs = runs_all

        # 关键：必须安装 i386 multilib 开发库，否则 32 位链接失败
        if "i386" in runs and "multilib" in runs:
            ok("安装了 i386 multilib 开发库（目标架构为 x86，必需）")
        else:
            bad("未安装 i386 multilib 开发库 —— 32 位（x86）链接会失败")

        # AMBuild 需要 make / ar / ranlib 等基础构建工具
        if "build-essential" in runs:
            ok("安装了 build-essential（AMBuild 需要 make/ar/ranlib）")
        else:
            bad("未安装 build-essential —— AMBuild 会因缺少 make 等工具而失败")

        if "GITHUB_PATH" in runs:
            ok("把 venv 写入 GITHUB_PATH（后续步骤才能找到 ambuild）")
        else:
            bad("未把 venv 加入 GITHUB_PATH，构建脚本会找不到 ambuild 命令")

        if "ambuild" in runs and "alliedmodders/ambuild" in runs:
            ok("安装 AMBuild（来自 alliedmodders/ambuild）")
        else:
            bad("未安装 AMBuild")

        # 新版 pip（windows-2022 上是 26.x）拒绝在同一次调用里升级自身：
        #   ERROR: To modify pip, please run the following command: ...
        if re.search(r"pip install[^\n|]*--upgrade[^\n|]*\bpip\b", runs) or \
           re.search(r"pip install[^\n|]*\bpip\b[^\n|]*setuptools", runs):
            bad("在同一次 pip 调用里升级 pip 自身：新版 pip 会直接报错（实测 Windows runner 失败）")
        else:
            ok("未在 pip 调用里升级 pip 自身")
        if "python -m venv" in runs or '"$PY" -m venv' in runs:
            ok("用 python -m venv 建虚拟环境（不依赖系统 pip 可写）")
        else:
            bad("未使用 venv 隔离 AMBuild 安装")

        if "-m32" in runs:
            ok("Linux 自检 32 位编译能力（-m32 试编译）")
        elif "runner.os == 'Linux'" in runs:
            wrn("未自检 32 位编译能力，multilib 缺失时会到链接阶段才报错")
        else:
            bad("未区分平台安装工具链（Linux 需要 multilib + clang-14，Windows 需要 MSVC）")

        # 结构化检查：第二个 checkout 必须拉取 sourcemod 且带 submodule
        sm_checkout = None
        for s in steps:
            w = s.get("with") or {}
            if s.get("uses", "").startswith("actions/checkout") and "sourcemod" in str(w.get("repository", "")):
                sm_checkout = w
                break
        if sm_checkout is None:
            bad("未找到拉取 alliedmodders/sourcemod 的 checkout 步骤")
        else:
            ok(f"拉取 SourceMod 仓库，ref={sm_checkout.get('ref')}")
            if str(sm_checkout.get("submodules", "")) == "recursive":
                ok("SourceMod checkout 拉取 submodule（AMTL / versionlib / hl2sdk-manifests）")
            else:
                bad("SourceMod checkout 未拉取 submodule（AMTL/versionlib/hl2sdk-manifests 缺失会构建失败）")
            if str(sm_checkout.get("path", "")) in ("sm", "./sm"):
                ok("SourceMod 检出到 sm/，与脚本 --sourcemod 参数一致")
            else:
                wrn(f"SourceMod 检出路径为 {sm_checkout.get('path')!r}，请确认与脚本参数一致")
        if "build-geoip.sh" in runs:
            ok("调用了 tools/build-geoip.sh")
        else:
            bad("工作流未调用 tools/build-geoip.sh")
        if "upload-artifact" in str(steps):
            ok("上传构建产物")
        else:
            bad("未上传构建产物")

        # Windows 上用 tar 打包时，归档名里的盘符冒号会被 GNU tar 当成
        # 「远程主机:路径」（tar: Cannot connect to D: resolve failed）。
        # 必须加 --force-local（或改用相对路径）。
        pkg = next((s for s in steps if s.get("name") == "Package extension"), None)
        if pkg:
            pkg_run = str(pkg.get("run", ""))
            if "tar " in pkg_run and "Windows" in pkg_run:
                if "--force-local" in pkg_run:
                    ok("Windows 打包用 tar --force-local（避免盘符冒号被当成远程主机）")
                else:
                    bad("Windows 打包用 tar 但未加 --force-local —— "
                        "归档路径含 'D:' 会报 Cannot connect to D: resolve failed")
            if "Windows" not in pkg_run and "tar" in pkg_run:
                wrn("打包步骤使用 tar 但未区分平台")

        # 产物校验必须区分 ELF / PE，且不能弱到形同虚设 ---
        if "ELF 32-bit LSB shared object" in runs:
            ok("校验 Linux 产物为 32 位 ELF 共享对象")
        else:
            bad("未校验 Linux 产物的 ELF 位数")
        if "e_lfanew" in runs and "PE\\0\\0" in runs:
            ok("校验 Windows 产物为 PE（读 e_lfanew 定位 PE 签名）")
        else:
            bad("Windows 产物的 PE 校验不充分")
        # 只针对“拿 PE 当二进制签名去 grep”的写法；注释里提到 PE（含警告说明）不算
        code_only = "\n".join(ln for ln in runs.splitlines()
                              if not ln.lstrip().startswith("#"))
        if re.search(r"grep\s+-\S*\s*['\"]PE['\"]", code_only) or \
           re.search(r"grep\s+['\"]PE['\"]", code_only):
            bad("用 grep 'PE' 判定 PE 文件：该签名过短，容易误判，应读 e_lfanew 处签名")
        else:
            ok("未使用 grep 'PE' 这类弱判定（已排除注释行）")
        if 'magic=$(od' in runs and '0b01' in runs:
            ok("校验 PE 可选头魔数为 0x10b（真 32 位，而非仅看文件后缀）")
        else:
            bad("未校验 PE 可选头魔数，无法确认是 32 位")

        # --- Release 发布 job（打 v* 标签时把成品发到 Releases）---
        rel = jobs.get("release")
        if rel is None:
            bad("缺少 jobs.release —— 产物无法发布到 Releases")
        else:
            ok("存在 jobs.release")
            if "tags/v" in str(rel.get("if", "")) or "refs/tags" in str(rel.get("if", "")):
                ok(f"release 仅在标签触发: {rel.get('if')}")
            else:
                bad(f"release 未限定标签触发（{rel.get('if')!r}），可能每次 push 都发版")
            if "build" in str(rel.get("needs", "")):
                ok("release 依赖 build job（只发布构建成功的产物）")
            else:
                bad("release 未依赖 build job")
            if str((rel.get("permissions") or {}).get("contents", "")) == "write":
                ok("release 具备 contents: write 权限")
            else:
                bad("release 缺少 contents: write 权限，无法创建 Release")
            rel_text = str(rel.get("steps", []))
            if "download-artifact" in rel_text and "gh-release" in rel_text:
                ok("release 下载全部产物并创建 GitHub Release")
            else:
                bad("release 未完整实现（缺少 download-artifact 或 gh-release）")
            if "SHA256SUMS" in str(rel):
                ok("发布包含 SHA256 校验和")
            else:
                wrn("发布未包含校验和文件")
except ImportError:
    bad("未安装 PyYAML，无法校验")
except Exception as exc:  # noqa: BLE001
    bad(f"YAML 解析失败: {exc}")

print()
print("=" * 68)
print("4. 构建脚本关键点")
print("=" * 68)
sh_path = os.path.join(REPO, "tools", "build-geoip.sh")
sh = open(sh_path, "r", encoding="utf-8").read()
checks = [
    ("set -euo pipefail", "严格模式"),
    ("--no-mysql", "不构建 MySQL 扩展"),
    ("--targets=\"$TARGET_ARCH\"", "目标架构参数"),
    ("--mms-path=", "提供 Metamod:Source 路径（detectSDKs 强制要求）"),
    ("checkout-deps.sh", "从 checkout-deps.sh 解析所需依赖版本"),
    ("mmsource-*", "按 glob 自动发现 mmsource 版本"),
    ("extensions/geoip", "同步到源码树 extensions/geoip"),
    ("ambuild", "执行编译"),
    ("geoip.ext.so", "定位产物"),
    ("--enable-optimize", "优化编译"),
]
for needle, why in checks:
    if needle in sh:
        ok(f"{why} ({needle})")
    else:
        bad(f"脚本缺少 {why} ({needle})")

# --- SDK 参数与「至少一个可构建 SDK」的前提 ---
# 1.12：SDK 改为 manifest 驱动，"none" 会被当成 SDK 名去找 hl2sdk-none 而失败；
#       统一用 --sdks=present（缺失 SDK 只警告）并提供一个 mock SDK 目录，
#       否则 1.12 报 No buildable SDKs were found、1.11 报 No applicable SDKs were found。
if re.search(r"^\s*--sdks=none\s*\\", sh, re.M) or '"--sdks=none"' in sh:
    bad("configure 里把 --sdks 写死为 none：1.12 会报 Missing hl2sdks: none，应使用 $SDK_ARG")
else:
    ok("configure 未写死 --sdks=none，改用变量 $SDK_ARG")
if 'SDK_ARG="present"' in sh:
    ok("SDK 用 present（缺失的 SDK 只警告不报错）")
else:
    bad("缺少 SDK_ARG=\"present\"")

# checkout-deps.sh 的 -s mock 是不可用的：它会按普通 SDK 去 clone
# hl2sdk 仓库的 mock 分支，而该分支不存在（mock 在独立仓库 hl2sdk-mock）
if re.search(r"checkout-deps\.sh\"\s+-s\s+mock", sh):
    bad("仍用 checkout-deps.sh -s mock：hl2sdk 仓库没有 mock 分支，必然失败")
else:
    ok("未误用 checkout-deps.sh -s mock")
if "alliedmodders/hl2sdk-mock" in sh:
    ok("直接从 alliedmodders/hl2sdk-mock 取 mock SDK")
else:
    bad("未获取 mock SDK —— configure 会因没有任何可构建 SDK 而失败")
if "public/tier1/strtools.h" in sh:
    ok("用 manifest include_paths 里的真实文件校验 mock 目录结构")
else:
    wrn("未校验 mock 目录结构，clone 不完整时难以定位")
if "--hl2sdk-root" in sh:
    ok("显式传 --hl2sdk-root，SDK 发现路径确定")
else:
    bad("未传 --hl2sdk-root，manifest 系统可能找不到 mock SDK")

# --- Metamod:Source：不能用 checkout-deps.sh 直接取 ---
# sourcemod 1.11-dev 的 checkout-deps.sh 写的是 name=mmsource-1.10 / branch=master，
# 会 clone metamod-source 的 master，而 master 已无 core/sourcehook，
# 导致 core 编译报 'sh_vector.h' file not found。必须按正确分支显式 clone。
if "metamod-source.git" in sh and "git clone" in sh:
    ok("直接按分支 clone Metamod:Source（不依赖 checkout-deps.sh 的分支选择）")
else:
    bad("未直接 clone Metamod:Source —— checkout-deps.sh 在 1.11 会取错分支（master）")
if "MMS_BRANCH" in sh and "-dev" in sh:
    ok("从 mmsource-<版本> 推导出对应的 <版本>-dev 分支")
else:
    bad("未按 mmsource 目录名推导 Metamod 分支")
if "core/sourcehook/sh_vector.h" in sh:
    ok("校验 Metamod 副本含 core/sourcehook/sh_vector.h（1.11 core 编译必需）")
else:
    bad("未校验 core/sourcehook/sh_vector.h —— 取到错误分支时无法及时发现")
if "core/sourcehook/sourcehook.h" in sh:
    ok("校验 core/sourcehook/sourcehook.h")
else:
    bad("未校验 core/sourcehook/sourcehook.h")
# --- Python 工具必须在 cp1252 控制台下也不崩 ---
# Windows 上 stdout 默认是 cp1252/ANSI；只要脚本里 print 了中文，就会抛
# UnicodeEncodeError 并以非 0 退出（CI 上实测：filter-build-scripts.py 因此失败）。
# 逐个子进程在 PYTHONIOENCODING=cp1252 下试跑，确认没有编码崩溃。
py_tools = sorted(glob.glob(os.path.join(REPO, "tools", "*.py")))
enc_env = dict(os.environ, PYTHONIOENCODING="cp1252")
enc_bad = []
for tool in py_tools:
    name = os.path.basename(tool)
    if name == "validate.py":
        continue  # 自身在跑，跳过
    try:
        p = subprocess.run([sys.executable, tool, "--help"], capture_output=True,
                           encoding="utf-8", errors="replace", env=enc_env, timeout=60)
    except Exception as exc:  # noqa: BLE001
        enc_bad.append(f"{name}(无法执行: {exc})")
        continue
    text = (p.stdout or "") + (p.stderr or "")
    if "UnicodeEncodeError" in text:
        enc_bad.append(f"{name}(cp1252 下 UnicodeEncodeError)")
if enc_bad:
    for b in enc_bad:
        bad(f"{b} —— 需要 sys.stdout.reconfigure(encoding='utf-8')")
else:
    ok(f"{len(py_tools) - 1} 个 Python 工具在 cp1252 控制台下均不崩溃")

# checkout-deps.sh 只应被用来读取版本号，不应再用来拉取依赖
if re.search(r"bash\s+\"?\$SM_TREE/tools/checkout-deps\.sh", sh):
    bad("仍在执行 checkout-deps.sh 拉取依赖（会下载 300MB MySQL 与 hl2sdk 镜像，且可能取错分支）")
else:
    ok("未执行 checkout-deps.sh（仅解析版本号），避免取错分支与多余下载")

# --- 只构建 geoip：整棵树全量构建会连带编译 regex 等扩展并因缺依赖失败 ---
if "filter-build-scripts.py" in sh and '"$AMB_FILE"' in sh:
    ok("调用 filter-build-scripts.py 裁剪构建列表")
else:
    bad("未裁剪构建列表：会全量编译源码树（core 需真实 HL2SDK，mock 下必然失败）")
if "restore_amb" in sh and "trap 'restore_amb' EXIT" in sh:
    ok("构建后（含失败/中断）还原 AMBuildScript（trap EXIT）")
else:
    bad("未在 EXIT trap 里还原 AMBuildScript，会污染源码树")

filter_py = os.path.join(REPO, "tools", "filter-build-scripts.py")
if os.path.isfile(filter_py):
    fp_src = open(filter_py, "r", encoding="utf-8").read()
    # 裁剪目标：只保留 geoip 真正依赖的部件（AMTL / versionlib / geoip 扩展）
    if "AMBuilder" in fp_src and "ENTRY" in fp_src:
        ok("filter-build-scripts.py 定位构建列表条目")
    else:
        bad("filter-build-scripts.py 未匹配构建列表条目")
    for guard, why in [("列表条目，结构可能已变", "找不到目标行时报错"),
                       ("缺少必须保留的构建项", "保留项缺失时报错"),
                       ("未找到 AMTL 的构建语句", "AMTL 构建语句缺失时报错")]:
        if guard in fp_src:
            ok(f"filter 脚本具备保护：{why}")
        else:
            bad(f"filter 脚本缺少保护：{why}")
    # core 必须排除：它需要真实 HL2SDK，mock 的占位头文件编译不过
    # （HalfLife2.cpp: 'CUtlVector': too many template arguments）
    if "builder.Build(" in fp_src and "core" not in fp_src.split("KEEP = {")[1].split("}")[0]:
        ok("filter 不保留 core（core 需真实 HL2SDK，mock 无法编译）")
    else:
        bad("filter 可能仍保留 core —— 会用 mock SDK 编译 core 而失败")
else:
    bad("缺少 tools/filter-build-scripts.py")

# 解释器选择必须按"能真正 import ambuild2"判断。
# 不能用 command -v：Windows 上 PATH 里的 WindowsApps\python3 是 Microsoft Store
# 存根（存在但不可用），而 venv 里通常没有 python3 -> 会选中存根并误报"缺少 AMBuild"。
if re.search(r"command -v python3", sh):
    bad("用 command -v python3 判断解释器：Windows 上会选中 Store 存根（存在但不可用）")
else:
    ok("未用 command -v python3 判断解释器")
if "import ambuild2" in sh and "py_ok" in sh:
    ok("按「能 import ambuild2」选择解释器")
else:
    bad("未按能否 import ambuild2 选择解释器（Windows 上会误判）")
if "Scripts/python.exe" in sh and "ambuild-venv" in sh:
    ok("能从 venv 常见位置（含 Windows 的 Scripts/）回退查找解释器")
else:
    bad("缺少 venv 回退查找：Windows 上 venv 无 python3 时会失败")

# --- public/safetyhook 是 1.12 才有的 submodule，1.11 必须豁免 ---
if '[ ! -d "$SM_TREE/$dir" ]' in sh or "! -d" in sh:
    ok("submodule 自检对分支缺失的目录有豁免（safetyhook 仅 1.12 存在）")
else:
    bad("submodule 自检未豁免分支缺失的目录 —— 1.11 会被误判为结构不符")

# bash 语法检查（有 bash 就真跑一遍 bash -n，比数括号可靠）
import shutil

bash = shutil.which("bash")
if bash is None and os.path.exists(r"C:\Program Files\Git\bin\bash.exe"):
    bash = r"C:\Program Files\Git\bin\bash.exe"
if bash:
    def run_bash(args):
        p = subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or ""), (p.stderr or "")

    rc, out, err = run_bash([bash, "-n", sh_path])
    if rc == 0:
        ok(f"bash -n 语法检查通过 ({os.path.basename(bash)})")
    else:
        bad(f"bash -n 语法检查失败: {err.strip()}")

    rc, out, err = run_bash([bash, sh_path, "--help"])
    if rc == 0 and "--sourcemod" in out:
        ok("--help 正常输出")
    else:
        bad(f"--help 异常 (exit={rc}): {(err or out).strip()[:200]}")

    # 错误路径必须给出非零退出码与可读提示
    rc, out, err = run_bash([bash, sh_path])
    if rc != 0 and "--sourcemod" in err:
        ok("缺少 --sourcemod 时正确报错退出")
    else:
        bad(f"缺少参数时未正确报错 (exit={rc}, err={err.strip()[:120]})")

    rc, out, err = run_bash([bash, sh_path, "--sourcemod", "/nonexistent-path-xyz"])
    if rc != 0 and ("不存在" in err or "不存在" in out):
        ok("源码树不存在时正确报错退出")
    else:
        bad(f"无效源码树未正确报错 (exit={rc}, err={err.strip()[:120]})")

    # 工作流里每个 run: 都是脚本（bash / pwsh），逐条做语法检查
    # （复用仓库自带工具，避免在这里重复实现一遍）
    wfs_tool = os.path.join(REPO, "tools", "check-workflow-shell.py")
    if os.path.isfile(wfs_tool):
        p = subprocess.run([sys.executable, wfs_tool], capture_output=True,
                           encoding="utf-8", errors="replace")
        lines = [l for l in (p.stdout or "").strip().splitlines() if l.strip()]
        if p.returncode == 0:
            ok(f"工作流脚本语法检查通过（{lines[-1] if lines else ''}）")
        else:
            bad("工作流脚本存在语法错误（运行 tools/check-workflow-shell.py 查看）")
            for line in lines:
                if "[FAIL]" in line:
                    print("         " + line.strip())
    else:
        wrn("缺少 tools/check-workflow-shell.py，跳过工作流脚本语法检查")
else:
    wrn("未找到 bash，跳过脚本语法检查")

if re.search(r"^\s*cd\s+[^|&;]*$", sh, re.M) and "(" not in sh:
    wrn("存在裸 cd，可能改变工作目录")
else:
    ok("cd 均在子 shell 中执行（( cd ... )），不污染工作目录")

# 子 shell 陷阱：`cmd | while ... die` 里的 while 在子 shell 中，die 不会终止主脚本
if re.search(r"\|\s*while\b", sh):
    bad("存在 `| while` 管道写法：循环体在子 shell 中，die 无法终止主脚本（应改用进程替换 < <(...)）")
else:
    ok("无 `| while` 子 shell 陷阱（die 能正常终止脚本）")

# submodule 自检路径必须正确：public/amtl 是 AMTL 的 submodule，
# 而 AMTL 仓库内还有一层 amtl/，故头文件相对 submodule 根是 amtl/am-string.h。
# 曾因写成 public/amtl/am-string.h（少一层）导致 CI 直接失败。
# 脚本里路径是 "$SM_TREE/$dir/$probe" 拼出来的，所以检查数据行本身。
SUBMODULE_EXPECT = {
    "public/amtl": "amtl/am-string.h",
    "sourcepawn": "include/sp_vm_api.h",
    "public/safetyhook": "include/safetyhook.hpp",
}
for sub_dir, rel in SUBMODULE_EXPECT.items():
    line = f"{sub_dir}:{rel}:"
    if line in sh:
        ok(f"submodule 自检项正确：{sub_dir} -> {rel}")
    else:
        bad(f"submodule 自检项缺失或路径不对：期望数据行以 {line} 开头")
if "public/amtl:amtl/am-string.h" not in sh and "public/amtl/am-string.h" in sh:
    bad("AMTL 路径少了一层：应为 public/amtl/amtl/am-string.h"
        "（public/amtl 是 submodule，其仓库内还有一层 amtl/）")

# heredoc 是纯数据，行内注释会被当成数据的一部分
for raw in re.findall(r"<<'([A-Z_]+)'\n(.*?)\n\1", sh, re.S):
    body = raw[1]
    for bline in body.splitlines():
        if "#" in bline:
            bad(f"heredoc 数据行含 '#'（会被当成数据）：{bline.strip()[:60]}")
if not any("#" in b for _, b in re.findall(r"<<'([A-Z_]+)'\n(.*?)\n\1", sh, re.S)):
    ok("heredoc 数据行不含行内注释")

# 危险操作检查
for danger, why in [("rm -rf /", "误删根目录"), ("rm -rf $SM_TREE", "误删源码树")]:
    if danger in sh:
        bad(f"危险操作: {danger} ({why})")
ok("未发现危险 rm 目标（仅删除 build/ 与 extensions/geoip 副本）")

print()
print("=" * 68)
print("5. 编码与行尾")
print("=" * 68)
# 行尾策略见 .gitattributes：上游以 CRLF 存入库的 3 个文件保持 CRLF 以做到逐字节一致
CRLF_OK = {"extensions/geoip/extension.cpp", "extensions/geoip/extension.h",
           "extensions/geoip/smsdk_config.h", "extensions/geoip/version.rc"}
for root, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in (".git", "out", "dist", "deps", "sm", "build")]
    for f in files:
        p = os.path.join(root, f)
        rel = os.path.relpath(p, REPO).replace("\\", "/")
        raw = open(p, "rb").read()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            bad(f"{rel} 不是合法 UTF-8")
            continue
        if b"\r\n" in raw and rel not in CRLF_OK:
            bad(f"{rel} 含 CRLF 行尾（应为 LF）")
        if raw.startswith(b"\xef\xbb\xbf"):
            bad(f"{rel} 含 UTF-8 BOM")
for rel in sorted(CRLF_OK):
    p = os.path.join(REPO, rel)
    if os.path.isfile(p) and b"\r\n" not in open(p, "rb").read():
        bad(f"{rel} 应为 CRLF（与上游一致），实际是 LF")
if not fail:
    ok("文本文件均为 UTF-8 无 BOM；脚本/工作流为 LF；上游的 CRLF 文件保持 CRLF")

print()
print("=" * 68)
print("6. 与上游 1.12-dev 内容一致性（逐字节校验）")
print("=" * 68)

# 行尾策略（见 .gitattributes）：上游以 CRLF 存入库的 3 个文件用 -text 保持逐字节一致，
# version.rc 工作区用 CRLF 但入库规范化为 LF，其余统一 LF。
# 注意：不能用裸 curl/raw.githubusercontent 当基准 —— 同一路径在不同分支/CDN 缓存下
# 可能返回不同版本（本项目初次抓取就混入过 master/1.13-dev 的文件），必须用
# contents API 的 blob sha 校验，这一步由 tools/sync-upstream.py 负责。
VERIFY_REMOTE = os.environ.get("VALIDATE_REMOTE", "") == "1"
if not VERIFY_REMOTE:
    print("  [skip] 需要联网，设置环境变量 VALIDATE_REMOTE=1 后重跑")
    print("         或直接运行: python3 tools/sync-upstream.py --branch 1.12-dev --check")
else:
    import json
    import urllib.request

    def _get(url, raw=False, tries=4):
        import time
        last = None
        for attempt in range(tries):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "validate.py",
                    "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
                })
                return urllib.request.urlopen(req, timeout=120).read()
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(str(last))

    api = ("https://api.github.com/repos/alliedmodders/sourcemod/contents/"
           "extensions/geoip?ref=1.12-dev")
    try:
        upstream = {e["name"]: e for e in json.loads(_get(api).decode("utf-8"))
                    if e["type"] == "file"}
        exact, eol_only, mismatch = 0, [], []
        for name, entry in sorted(upstream.items()):
            data = _get(entry["download_url"], raw=True)
            if hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() != entry["sha"]:
                mismatch.append(f"{name}(下载内容与 blob sha 不符，可能拿错分支)")
                continue
            local_path = os.path.join(geoip_dir, name)
            if not os.path.isfile(local_path):
                mismatch.append(f"{name}(本地缺失)")
                continue
            local = open(local_path, "rb").read()
            if local == data:
                exact += 1
            elif local.replace(b"\r\n", b"\n") == data.replace(b"\r\n", b"\n"):
                eol_only.append(name)
            else:
                mismatch.append(f"{name}(内容与上游不一致)")
        if mismatch:
            for m in mismatch:
                bad(m)
        else:
            ok(f"{len(upstream)} 个文件内容与上游 1.12-dev 一致"
               f"（逐字节一致 {exact}，仅行尾差异 {len(eol_only)}: {eol_only or '无'}）")
    except Exception as exc:  # noqa: BLE001
        wrn(f"联网校验失败（不影响本地结论）: {exc}")

print()
print("=" * 68)
if fail:
    print(f"结果: {len(fail)} 项失败, {len(warn)} 项警告")
    for f in fail:
        print(f"  - {f}")
    sys.exit(1)
print(f"结果: 全部通过（{len(warn)} 项警告）")
for w in warn:
    print(f"  - {w}")
sys.exit(0)
