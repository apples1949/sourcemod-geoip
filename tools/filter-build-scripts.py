#!/usr/bin/env python3
"""把 SourceMod 根 AMBuildScript 的构建列表裁剪为「只编译 geoip 所需的部件」。

为什么需要：BuildScripts 会编译整棵源码树 —— loader、core、以及十几个扩展。
其中 **core 必须用真实的 HL2SDK 才能编译**（core/HalfLife2.cpp 大量使用
CUtlVector/CUtlMemory 等真正的 SDK 类型），而我们的 mock SDK 只是占位实现，
于是 MSVC 会报：

    HalfLife2.cpp(1310): error C2977: 'CUtlVector': too many template arguments
      hl2sdk-mock\\public\\tier1\\utlvector.h(8): note: see declaration of 'CUtlVector'

但 geoip 扩展**并不需要 core**：AMBuildScript 的 ConfigureForExtension() 给扩展的
include 只有 public/、public/extensions、sourcepawn/include、public/amtl —— 没有 core。
因此这里只保留 geoip 真正依赖的三项：

    public/amtl/amtl/AMBuilder   AMTL（am-string.h 等，geoip 直接 include）
    versionlib/AMBuilder         生成 sourcemod_version.h 所需
    extensions/geoip/AMBuilder   目标扩展本身

其余全部注释掉（含 loader / core / plugins / 其它扩展与打包脚本）。
本脚本只改 AMBuildScript（不是源码），调用方负责备份与还原。

用法:
    filter-build-scripts.py <AMBuildScript 路径> [--check]

退出码:
    0 有改动（或 --check 下"需要改动"）
    1 文件里找不到任何可识别的构建项（结构异常）
    2 缺少必须保留的项
"""
import argparse
import re
import sys

# 必须保留（顺序无关）；键用于报错，值是 AMBuildScript 中出现的形式
KEEP = {
    "versionlib": "versionlib/AMBuilder",
    "geoip 扩展": "extensions/geoip/AMBuilder",
}

# 只匹配 BuildScripts 列表里的**独立条目**行，形如：
#     'loader/AMBuilder',
# 不匹配语句形式（这些必须原样保留，它们不是列表条目）：
#     libamtl = builder.Build('public/amtl/amtl/AMBuilder', extra_vars)
#     builder.Build('public/safetyhook/AMBuilder', {'SafetyHook': SafetyHook })
ENTRY = re.compile(r"^(\s*)'([^']*AMBuilder[^']*)',\s*$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--check", action="store_true", help="只报告，不写入")
    args = ap.parse_args()

    with open(args.path, "r", encoding="utf-8") as fp:
        lines = fp.readlines()

    keep_vals = set(KEEP.values())
    found, kept, excluded, inline = 0, [], [], []
    out = []
    for ln in lines:
        # 语句形式（含 builder.Build(...)）一律原样保留，并把其中的 AMTL/SafetyHook
        # 视为"已保留"——它们是 geoip 的构建期前提，不能注释掉。
        if "builder.Build(" in ln and "AMBuilder" in ln:
            inline.append(ln.strip())
            out.append(ln)
            continue
        m = ENTRY.match(ln)
        if not m:
            out.append(ln)
            continue
        found += 1
        indent, entry = m.group(1), m.group(2)
        if entry in keep_vals:
            kept.append(entry)
            out.append(ln)
        else:
            excluded.append(entry)
            out.append(f"{indent}# [geoip-only] {ln.strip()}\n")

    if found == 0:
        print("error: 文件中没有可识别的 '...AMBuilder' 列表条目，结构可能已变",
              file=sys.stderr)
        return 1

    missing = keep_vals - set(kept)
    if missing:
        print(f"error: 缺少必须保留的构建项: {sorted(missing)}", file=sys.stderr)
        return 2

    # geoip 依赖 AMTL 头文件，其构建语句必须仍在
    if not any("public/amtl/amtl/AMBuilder" in s for s in inline):
        print("error: 未找到 AMTL 的构建语句（geoip 依赖其头文件）", file=sys.stderr)
        return 3

    if not args.check:
        with open(args.path, "w", encoding="utf-8") as fp:
            fp.writelines(out)

    print("keep=%d (%s) excluded=%d 保留的语句形式=%d" % (
        len(kept), " ".join(sorted(kept)), len(excluded), len(inline)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
