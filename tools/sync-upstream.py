#!/usr/bin/env python3
"""从上游 SourceMod 同步 extensions/geoip 源码，并用 git blob SHA-1 校验每个文件。

为什么需要校验：raw.githubusercontent.com 的缓存/分支解析可能给出与目标分支
不一致的内容（本项目初次抓取就混入了 master/1.13-dev 的文件），直接 curl 覆盖存在
拿到错误版本的风险。这里用 GitHub contents API 返回的 blob sha 逐个核对，确保
仓库内每一行代码都确实来自指定分支。

用法:
    python3 tools/sync-upstream.py --branch 1.12-dev --check   # 只比对，不写入
    python3 tools/sync-upstream.py --branch 1.12-dev           # 同步并校验
    python3 tools/sync-upstream.py --branch 1.11-dev           # 同步 1.11 分支
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

# Windows 上 stdout 默认是 cp1252/ANSI，打印中文会抛 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

REPO_SLUG = "alliedmodders/sourcemod"
SUBDIR = "extensions/geoip"
HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(os.path.dirname(HERE), "extensions", "geoip")

# 本仓库自己维护的文件，不参与上游同步
LOCAL_ONLY = {"README.md"}

# 行尾策略（与 .gitattributes 保持一致）：
# 上游把下面 4 个文件以 CRLF 存入库中，且 .gitattributes 对它们设了 -text，
# 所以这里必须原样写入，仓库内容才能与上游 blob 逐字节一致。
PRESERVE_EOL = {"extension.cpp", "extension.h", "smsdk_config.h", "version.rc"}


def normalize(name, data):
    """按 .gitattributes 的策略决定写入工作区的行尾。"""
    if name in PRESERVE_EOL:
        return data
    return data.replace(b"\r\n", b"\n")


def fetch(url, raw=False, tries=5, timeout=120):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "sourcemod-geoip-sync",
                "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
            })
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"下载失败 {url}: {last}")


def git_blob_sha(data):
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="1.12-dev",
                    help="SourceMod 分支/标签（如 1.11-dev / 1.12-dev）")
    ap.add_argument("--check", action="store_true",
                    help="只与上游比对，不写入文件")
    args = ap.parse_args()

    api = (f"https://api.github.com/repos/{REPO_SLUG}/contents/{SUBDIR}"
           f"?ref={args.branch}")
    listing = json.loads(fetch(api).decode("utf-8"))
    upstream = {e["name"]: e for e in listing if e["type"] == "file"}
    if not upstream:
        print(f"[error] 上游 {SUBDIR}@{args.branch} 没有任何文件", file=sys.stderr)
        return 1

    os.makedirs(DEST, exist_ok=True)
    print(f"上游: {REPO_SLUG}/{SUBDIR}@{args.branch}  ({len(upstream)} 个文件)")
    print(f"本地: {DEST}")
    print()
    print(f"{'file':<30} {'upstream':>9} {'local':>9}  {'状态':<28} crlf")
    print("-" * 90)

    changed, same, problems = [], [], []
    for name in sorted(upstream):
        entry = upstream[name]
        data = fetch(entry["download_url"], raw=True)

        # 1) 内容必须与 API 声明的 git blob 完全一致（防止拿到错误分支）
        if git_blob_sha(data) != entry["sha"]:
            problems.append(f"{name}: 下载内容与 git blob sha 不符（可能拿错分支）")
            print(f"{name:<30} {'':>9} {'':>9}  {'SHA 不符':<28}")
            continue

        want = normalize(name, data)

        path = os.path.join(DEST, name)
        old = open(path, "rb").read() if os.path.isfile(path) else None

        if old == want:
            status = "一致"
            same.append(name)
        elif args.check:
            status = "需要更新"
            changed.append(name)
        else:
            with open(path, "wb") as fp:
                fp.write(want)
            status = "已更新"
            changed.append(name)

        crlf_count = want.count(b"\r\n")
        print(f"{name:<30} {entry['size']:>9} "
              f"{(len(old) if old is not None else 0):>9}  {status:<28} "
              f"{crlf_count}")

    # 本地多出来的文件（不含本仓库自维护文件）
    extra = sorted(set(os.listdir(DEST)) - set(upstream) - LOCAL_ONLY)
    if extra:
        print()
        print(f"[warn] 本地存在上游没有的文件: {extra}")

    print()
    print(f"汇总: 一致 {len(same)} / 变更 {len(changed)} / 问题 {len(problems)}")
    if problems:
        for p in problems:
            print(f"  [error] {p}")
        return 1
    if args.check and changed:
        print("提示: 去掉 --check 即可写入上述变更")
    return 0


if __name__ == "__main__":
    sys.exit(main())
