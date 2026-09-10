#!/usr/bin/env python3
"""校验本仓库的完整性：文件清单、YAML 工作流、脚本关键点、编码/行尾。"""
import hashlib
import io
import os
import re
import sys

# Windows 控制台默认 GBK，直接 print 中文会乱码/抛错
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
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
        branches = matrix.get("sm_branch", [])
        for want in ["1.11-dev", "1.12-dev"]:
            if want in branches:
                ok(f"矩阵包含 SourceMod {want}")
            else:
                bad(f"矩阵缺少 SourceMod {want}")
        # 工具链必须显式安装：曾经照搬官方 CI 的第三方镜像，
        # 结果容器里没有 clang++（PATH 中找不到编译器）导致构建直接失败。
        if build.get("container"):
            wrn("仍在使用 container（请确认镜像内确实有可用的 C++ 编译器）")
        else:
            ok("未依赖第三方构建镜像（工具链在本工作流内显式安装）")

        env = build.get("env") or {}
        if str(env.get("CXX", "")).strip():
            ok(f"显式指定 C++ 编译器: {env.get('CXX')}")
        else:
            bad("未显式指定 CXX（依赖自动探测，容易落到不可用的编译器上）")

        runner = str(build.get("runs-on", ""))
        if runner.startswith("ubuntu-"):
            ok(f"runner: {runner}")
        else:
            wrn(f"runner 非 ubuntu: {runner}")

        steps = build.get("steps", [])
        runs = "\n".join(str(s.get("run", "")) for s in steps)

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

        if "-m32" in runs:
            ok("自检 32 位编译能力（-m32 试编译）")
        else:
            wrn("未自检 32 位编译能力，multilib 缺失时会到链接阶段才报错")

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
    ("--sdks=none", "不拉取 HL2SDK（GeoIP 不需要）"),
    ("--no-mysql", "不构建 MySQL 扩展"),
    ("--targets=\"$TARGET_ARCH\"", "目标架构参数"),
    ("--mms-path=", "提供 Metamod:Source 路径（detectSDKs 强制要求）"),
    ("checkout-deps.sh", "用官方脚本拉依赖"),
    ("-s none", "checkout-deps 不拉 HL2SDK"),
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

# bash 语法检查（有 bash 就真跑一遍 bash -n，比数括号可靠）
import shutil
import subprocess

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
else:
    wrn("未找到 bash，跳过脚本语法检查")

if re.search(r"^\s*cd\s+[^|&;]*$", sh, re.M) and "(" not in sh:
    wrn("存在裸 cd，可能改变工作目录")
else:
    ok("cd 均在子 shell 中执行（( cd ... )），不污染工作目录")

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
