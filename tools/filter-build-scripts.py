#!/usr/bin/env python3
"""把 SourceMod 根 AMBuildScript 的构建列表裁剪为「只构建 geoip 扩展」。

为什么需要：AMBuildScript 的 BuildScripts 会编译整棵源码树的所有扩展，那些扩展各有
各的依赖（regex 需要 SourceHook 的 sh_string.h、部分需要 HL2SDK 等），与 geoip 无关
却会让构建失败。geoip 的 AMBuilder 只引用自身源码、../../public/smsdk_ext.cpp 和
public/ 头文件，不依赖任何其它扩展。

本脚本只改 AMBuildScript（不是源码），把非 geoip 的 `extensions/*/AMBuilder` 行注释掉；
调用方负责备份与还原。

用法:
    filter-build-scripts.py <AMBuildScript 路径> [--keep geoip] [--check]

退出码:
    0 有改动（或 --check 下"需要改动"）
    1 文件里找不到任何 extensions/*/AMBuilder 行（结构异常）
    2 找不到 keep 指定的扩展
"""
import argparse
import re
import sys

PATTERN = re.compile(r"^(\s*)'extensions/([A-Za-z0-9_]+)/AMBuilder',")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--keep", default="geoip", help="保留构建的扩展名（默认 geoip）")
    ap.add_argument("--check", action="store_true", help="只报告，不写入")
    args = ap.parse_args()

    with open(args.path, "r", encoding="utf-8") as fp:
        lines = fp.readlines()

    found, kept, excluded = 0, 0, []
    out = []
    for ln in lines:
        m = PATTERN.match(ln)
        if not m:
            out.append(ln)
            continue
        found += 1
        indent, name = m.group(1), m.group(2)
        if name == args.keep:
            kept += 1
            out.append(ln)
        else:
            excluded.append(name)
            out.append(f"{indent}# [geoip-only] {ln.strip()}\n")

    if found == 0:
        print("error: 文件中没有 extensions/*/AMBuilder 行，结构可能已变", file=sys.stderr)
        return 1
    if kept == 0:
        print(f"error: 没找到要保留的扩展 '{args.keep}'", file=sys.stderr)
        return 2

    if not args.check:
        with open(args.path, "w", encoding="utf-8") as fp:
            fp.writelines(out)

    print(f"keep={args.keep} kept={kept} excluded={len(excluded)} "
          f"({' '.join(sorted(excluded))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
