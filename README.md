# SourceMod GeoIP Extension

[SourceMod](https://github.com/alliedmodders/sourcemod) 的 **GeoIP 扩展**独立构建仓库。
源码取自上游 `alliedmodders/sourcemod` 的 `extensions/geoip/`，通过 GitHub Actions
分别为 **SourceMod 1.11** 和 **1.12** 编译出 `geoip.ext.so`。

[![Build GeoIP Extension](https://github.com/OWNER/REPO/actions/workflows/build.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/build.yml)

> 把上面的 `OWNER/REPO` 换成你自己的仓库路径即可显示构建徽章。

---

## 这是什么

GeoIP 扩展为 SourceMod 提供按 IP 查询地理位置的能力（国家 / 洲 / 城市 / 经纬度 / 距离等），
脚本层通过 `geoip.inc` 的 native 调用，例如：

```sourcepawn
#include <geoip>

public void OnClientPostAdminCheck(int client)
{
    char ip[32];
    GetClientIP(client, ip, sizeof(ip));

    char country[46];
    GeoipCountryCode(ip, country, sizeof(country));
    PrintToServer("客户端 %N 来自 %s", client, country);
}
```

该扩展内嵌了 [libmaxminddb](https://github.com/maxmind/libmaxminddb) 的 C 源码
（`maxminddb.c` 等），因此 **没有外部库依赖**，编译产物是一个自包含的 `.so`。

## 产物与安装

每次 Actions 会产出两个 zip 压缩包：

| 产物 | 适用 SourceMod |
| --- | --- |
| `geoip-ext-1.11-dev.zip` | SourceMod 1.11（对 1.11-dev 源码树编译） |
| `geoip-ext-1.12-dev.zip` | SourceMod 1.12（对 1.12-dev 源码树编译） |

> 两个平台的二进制**分别构建**，不要混用：请根据服务端的 SourceMod 版本下载对应压缩包。

安装步骤：

1. 从 Actions 运行页的 **Artifacts** 下载对应版本的 zip；
2. 解压到服务端根目录（压缩包内已按 `addons/sourcemod/extensions/` 组织好目录结构）：

   ```
   <游戏服务端>/
   └── addons/sourcemod/extensions/geoip.ext.so
   ```

3. 下载 GeoIP 数据库（**不包含在本仓库中**），放到
   `addons/sourcemod/configs/geoip/`，文件名使用 `GeoLite2-City.mmdb`：

   ```bash
   # 需要 MaxMind 账号（免费注册后获取 license key）
   curl -fsSL "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=<YOUR_LICENSE_KEY>&suffix=tar.gz" \
     -o GeoLite2-City.tar.gz
   tar -xzf GeoLite2-City.tar.gz --strip-components=1 --wildcards '*/GeoLite2-City.mmdb' \
     -C addons/sourcemod/configs/geoip/
   ```

4. 重启服务端（或 `sm exts load geoip`），用 `sm exts list` 确认 GeoIP 已加载。

扩展启动时会检查数据库文件：若数据库缺失或过期超过 90 天，会在 SourceMod 日志中给出提示。

## 仓库结构

```
.
├── .github/workflows/build.yml   # 编译工作流（1.11-dev / 1.12-dev 矩阵）
├── extensions/geoip/             # 扩展源码，目录位置与上游保持一致
│   ├── AMBuilder                 #   AMBuild 构建描述
│   ├── extension.cpp/.h          #   扩展主体（注册 native）
│   ├── geoip_util.cpp/.h         #   native 实现
│   ├── maxminddb.c/.h            #   内嵌 libmaxminddb
│   └── ...
├── tools/
│   ├── build-geoip.sh            # 构建脚本（CI 与本地共用）
│   ├── sync-upstream.py          # 同步上游源码（带 git blob SHA 校验）
│   └── validate.py               # 仓库自检
├── .gitattributes
└── README.md
```

### 为什么不能直接在本仓库根目录编译

GeoIP 属于 SourceMod 的 **in-tree 扩展**，它硬依赖 SourceMod 源码树：

- `AMBuilder` 里以相对路径引用 `../../public/smsdk_ext.cpp`（深度必须一致）；
- `extension.h` 包含 `smsdk_ext.h`，`extension.cpp` 包含构建期生成的 `sourcemod_version.h`；
- 构建完全依赖 SourceMod 的 `configure.py` + `AMBuildScript` + AMBuild 工具链。

因此 `tools/build-geoip.sh` 的做法是：把 `extensions/geoip/` 整体同步进一份 SourceMod
源码树，再调用官方构建流程。工作流中的 `sm/` 就是按分支拉取的 SourceMod。

## 本地构建

前置条件：Linux（或 WSL）、Python 3、git、C++17 编译器（gcc 9+ / clang 5+）。

```bash
# 1. 安装 AMBuild
python3 -m pip install "git+https://github.com/alliedmodders/ambuild.git"

# 2. 拉取 SourceMod 源码树（必须带 submodule；换成 1.11-dev 即可构建 1.11 版本）
git clone --depth 1 --branch 1.12-dev --recurse-submodules \
  https://github.com/alliedmodders/sourcemod.git /tmp/sourcemod

# 3. 构建（脚本会自动用官方 checkout-deps.sh 拉取 Metamod:Source）
./tools/build-geoip.sh --sourcemod /tmp/sourcemod --out ./out

# 产物
#   out/package/addons/sourcemod/extensions/geoip.ext.so
```

常用参数：

```bash
./tools/build-geoip.sh --help
./tools/build-geoip.sh --sourcemod /tmp/sourcemod --deps /tmp/deps --skip-deps   # 复用已装好的依赖
./tools/build-geoip.sh --sourcemod /tmp/sourcemod --target-arch x86_64           # 换目标架构
```

## 源码来源与保真度

`extensions/geoip/` 下 14 个文件与上游 `1.12-dev` 分支的 git blob **逐字节一致**
（`git hash-object` 与上游 blob sha 完全相同，含上游以 CRLF 入库的 4 个文件）：

```bash
$ git hash-object extensions/geoip/maxminddb.c
5e97426cf3...        # 与 GitHub contents API 返回的 blob sha 相同
```

为此 `.gitattributes` 对 `version.rc` / `extension.cpp` / `extension.h` / `smsdk_config.h`
显式使用了 `-text`（关闭行尾转换），因为上游把这 4 个文件以 CRLF 存入库中；
其余文件统一为 LF。这样可以保证：

- 与上游比对时**没有假差异**，`tools/sync-upstream.py --check` 能真正反映版本差异；
- 任何平台 clone 下来内容一致，Linux 容器内编译不受行尾影响。

> 踩坑记录：依赖 `curl raw.githubusercontent.com` 抓取源码是不可靠的。
> 本项目初次抓取时，同一个 `extensions/geoip/` 路径下混入了 **`master`（1.13-dev）**
> 版本的 `maxminddb.c` 等 7 个文件（文件大小与 GitHub API 报告的 blob 大小不符），
> 这类问题在编译期很难定位。因此仓库自带 `tools/sync-upstream.py`，
> 用 contents API 的 blob sha 逐个校验来源分支。

## 为什么一份源码能同时支持 1.11 和 1.12

仓库内的扩展源码与 `1.12-dev` 分支逐字节一致。经 git blob SHA-1 比对，
`1.11-dev` 与 `1.12-dev` 的 `extensions/geoip/` 差异极小：

| 文件 | 1.11-dev vs 1.12-dev |
| --- | --- |
| `AMBuilder`、`extension.cpp/.h`、`geoip_util.h`、`maxminddb*`、`data-pool.*`、`osdefs.h`、`smsdk_config.h`、`version.rc` | **字节完全相同（13/14）** |
| `geoip_util.cpp` | 仅一处差异：1.12 增加了把 `chi` 映射为 `zh-CN` 的语言码修正 |

该差异只用 `strcmp` 与 `std::string`，不涉及任何版本相关的 API，因此在 1.11 上同样可编译可用
（等于把 1.12 的中文语言码修正一并带给 1.11）。两个平台版本分别链接各自分支的
`public/` 头文件与 versionlib，所以产物互不混用。

## 编译细节

工作流在 SourceMod 官方构建容器
`ghcr.io/alliedmodders/build-containers/debian11-clang22` 中执行，
使用与上游一致的编译参数：

```bash
python3 ../configure.py \
  --enable-optimize \   # -O3 / NDEBUG
  --no-color \
  --sdks=none \         # GeoIP 不依赖任何 HL2SDK，避免拉取数 GB 的 SDK 仓库
  --no-mysql \          # 不构建 MySQL 扩展，免去 MySQL 5.5 头文件依赖
  --targets=x86 \       # 服务端为 32 位
  --mms-path=<deps>/mmsource-1.12
ambuild
```

其中两点来自 SourceMod 构建系统的硬性要求：

- **必须提供 Metamod:Source 源码**：`AMBuildScript` 的 `detectSDKs()` 会无条件校验
  `mms_root`（core 的 SourceHook 头文件需要它），即使用 `--sdks=none` 也不例外。
  各分支需要的版本不同（1.11-dev → `mmsource-1.10`，1.12-dev → `mmsource-1.12`），
  脚本因此不写死版本号，而是用官方 `tools/checkout-deps.sh -s none` 拉取后按 glob 自动发现。
- **不能关闭自动版本号**：`version.rc` 与 `GetExtensionVerString()` 使用
  `SOURCEMOD_VERSION` / `SOURCEMOD_BUILD_TIME`，这些宏由构建期的 versionlib 生成。

上游编译开启 `-Werror`，因此改动源码时必须零警告通过。

## 同步上游更新

用自带的同步脚本，它会拉取指定分支并**用 git blob SHA-1 逐个校验**文件内容：

```bash
python3 tools/sync-upstream.py --branch 1.12-dev --check   # 只比对，不写入
python3 tools/sync-upstream.py --branch 1.12-dev           # 同步
git diff --stat
```

> **不要用 `curl raw.githubusercontent.com` 直接覆盖源码。**
> 本仓库初次抓取时就踩过这个坑：同一个路径在不同分支/不同 CDN 缓存下可能返回
> **不同版本**的内容（例如把 `master`（1.13-dev）的 `maxminddb.c` 当成 1.12 的），
> 且文件大小与 GitHub API 报告的 blob 大小不一致，直接编译会出现难以定位的问题。
> `sync-upstream.py` 通过 `contents` API 声明的 blob sha 核对，能确保内容确实来自目标分支。

## 仓库自检

```bash
python3 tools/validate.py
```

检查内容包括：文件清单完整性、`AMBuilder` 是否与上游字节一致（决定能否在源码树中编译）、
工作流 YAML 结构（矩阵是否覆盖 1.11/1.12、是否拉取 submodule）、构建脚本关键参数，
以及 `bash -n` 语法检查与文本文件编码/行尾规范。

## 许可

扩展源码版权归 AlliedModders LLC 所有，遵循 **GNU GPL v3**（含 Source 引擎链接例外条款），
与上游一致，详见各源文件头部声明与 <https://www.sourcemod.net/license.php>。
