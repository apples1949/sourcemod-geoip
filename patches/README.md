# GeoIP 中文语言码修复补丁说明

对应：**SourceMod PR #2335** —— <https://github.com/alliedmodders/sourcemod/pull/2335>
merge commit：`5c1a5e35b9852c7949c1a65e2afee9a5b2dd33fd`

## 问题

`GeoLite2-City.mmdb` 里的国家 / 城市名称，中文用的是语言码 `zh-CN`。
但 SourceMod 的 translator 在中文环境下返回的是 `chi`，两者匹配不上，
于 `mmdb.metadata.languages` 中找不到对应语言 —— **中文译名永远返回不了**，
只能回退成 `en`。

## 修复

在 `getLang()` 中把 `chi` 归一化为 `zh-CN`：

```c
if (translator->GetLanguageInfo(langid, &code, NULL))
{
    if (strcmp(code, "chi") == 0)
    {
        code = "zh-CN";
    }
    for (size_t i = 0; i < mmdb.metadata.languages.count; i++)
    ...
```

上游 diff 一共两处改动：上述语言码归一化（+4 行），以及文件末尾补上换行
（原文件缺少行尾换行）。本目录的 `geoip_fix_2335.patch` 完整对应这两点。

## 为什么放在这个仓库里

| 分支 | 是否含该修复 |
| --- | --- |
| `master`（1.13） | ✅ 已合并 |
| `1.12-dev` | ✅ 已回移 |
| `1.11-dev` | ❌ 至今没有 |

本仓库的扩展源码取自 `1.12-dev`，所以**天然包含**该修复 —— 这正是本仓库存在的原因：
让 1.11 平台也能用上带此修复的 GeoIP。

## 这个补丁文件的作用

`tools/build-geoip.sh` 在编译前会核验修复是否存在：

1. 在 `extensions/geoip/geoip_util.cpp` 里查找标记 `strcmp(code, "chi")`；
2. 找到 → 打印 `[ok]` 并跳过（当前仓库的正常路径）；
3. 找不到 → 在临时目录用 `patch -p1` 应用本补丁，再复查标记，打印 `[patch]`；
4. 应用失败或复查仍找不到 → **中止构建**（宁可失败，也不产出缺少中文支持的二进制）。

这样即使将来有人把 `extensions/geoip/` 换回 `1.11-dev` 的版本，
产物也不会静默地丢掉中文修复。

## 关于 "zho"

PR 标题写的是「chi and zho」，但实际 diff 只处理了 `chi`——
SourceMod 的 translator 给出的是 `chi`，不会给出 `zho`。
本补丁与上游 `master` 保持一致，同样只处理 `chi`。

## 维护提示

- 若上游把该修复改写成别的形式（例如直接改 translator 的语言码），
  标记字符串会变，`grep` 将找不到 → 会尝试应用补丁。
  此时若补丁无法应用，构建会明确报错，按提示更新本补丁或调整标记即可。
- 若 `1.11-dev` 将来也合入了该修复，本补丁会自然走"已存在"分支，无需改动。
