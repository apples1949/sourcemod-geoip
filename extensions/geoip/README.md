# extensions/geoip

SourceMod 的 GeoIP 扩展源码，**保持与上游 `alliedmodders/sourcemod` 完全一致的目录位置**
(`extensions/geoip/`)。

这样做的原因是该扩展属于 **源码树内扩展 (in-tree extension)**，它直接引用 SourceMod
自身的构建系统与公共头文件：

```
AMBuilder  ->  ../../public/smsdk_ext.cpp        (相对路径，深度必须一致)
extension.h -> #include "smsdk_ext.h"            (来自 public/)
extension.cpp -> #include <sourcemod_version.h>  (构建时由 versionlib 生成到 build/includes)
```

因此这些文件**不能被复制到别的位置编译**：`tools/build-geoip.sh` 会把这个目录整体
拷进 SourceMod 源码树的 `extensions/geoip/`，再调用 SourceMod 自己的 AMBuild 构建。

## 文件说明

| 文件 | 来源 | 说明 |
| --- | --- | --- |
| `AMBuilder` | 上游 | AMBuild 构建描述（1.11 / 1.12 / master 三个分支字节级一致） |
| `extension.cpp` / `extension.h` | 上游 | 扩展主体，注册 `GeoIP_Extension` 与 native |
| `geoip_util.cpp` / `geoip_util.h` | 上游 | native 实现（`GeoipCode2` / `GeoipCode3` / `GeoipCity` / `GeoipContinentCode` / `GeoipCountryCode` / `GeoipRegionCode` / `GeoipDistance` 等） |
| `maxminddb.c` / `maxminddb.h` | 上游内嵌 | MaxMind DB (libmaxminddb) C 库，随扩展一起编译，无外部依赖 |
| `maxminddb-compat-util.h` / `maxminddb_config.h` / `osdefs.h` | 上游内嵌 | libmaxminddb 的平台兼容层 |
| `data-pool.c` / `data-pool.h` | 上游内嵌 | libmaxminddb 内部数据结构 |
| `smsdk_config.h` | 上游 | 扩展元信息（名称 `GeoIP`、日志标签 `GEOIP`、启用 LibSys/Translator/PlayerHelpers） |
| `version.rc` | 上游 | Windows 版本资源文件 |

## 修改源码时的注意点

- **不要**把 `AMBuilder` 里的相对路径 `../../public/smsdk_ext.cpp` 改成绝对路径或其它深度，
  否则 `tools/build-geoip.sh` 的目录映射会失效。
- 构建开启 `-Werror`（官方 CI 亦同），新增代码必须零警告通过 gcc/clang 与 msvc。
- 运行时数据库路径为 `addons/sourcemod/configs/geoip/GeoLite2-City.mmdb`
  （或同目录下的 `GeoIPCity.dat`），需另行下载，不含在本仓库内。

## 与上游同步

```bash
# 逐个文件比对（示例）
BASE=https://raw.githubusercontent.com/alliedmodders/sourcemod/1.12-dev/extensions/geoip
curl -fsSL "$BASE/extension.cpp" -o /tmp/extension.cpp
diff -u extensions/geoip/extension.cpp /tmp/extension.cpp
```
