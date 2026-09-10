# SourceMod GeoIP Extension（含 PR #2335 中文修复，面向 1.11 / 1.12）

为 **SourceMod 1.11 / 1.12** 平台，编译出**包含 [PR #2335](https://github.com/alliedmodders/sourcemod/pull/2335) 中文语言码修复**的
GeoIP 扩展 `geoip.ext.so`。

[![Build GeoIP Extension](https://github.com/OWNER/REPO/actions/workflows/build.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/build.yml)

> 把上面的 `OWNER/REPO` 换成你自己的仓库路径即可显示构建徽章。

---

## 为什么需要这个仓库

### 起因：GeoIP 拿不到中文翻译

`GeoLite2-City.mmdb` 里的国家 / 城市名称，中文用的是语言码 `zh-CN`。
但 SourceMod 的 translator 在中文环境下返回的是 `chi`，两者对不上，
于是在 `mmdb.metadata.languages` 里找不到对应语言 —— **中文译名永远返回不了**，
`GeoipCity()` / `GeoipCountryName()` 之类只能退回英文。

### 修复：PR #2335

[alliedmodders/sourcemod#2335](https://github.com/alliedmodders/sourcemod/pull/2335)
（*fix geoip chi and zho not return chinese translation*，merge commit `5c1a5e35`）
在 `getLang()` 里把 `chi` 归一化成 `zh-CN`，问题即解。

### 问题：这个修复只在 1.13 上

| 分支 | 是否含 PR #2335 |
| --- | --- |
| `master`（1.13） | ✅ 已合并 |
| `1.12-dev` | ✅ 已回移 |
| **`1.11-dev`** | ❌ **至今没有** |

也就是说，官方发布的 1.11 版 GeoIP 依然拿不到中文译名。

### 本仓库的做法

在 1.11 / 1.12 平台上编译出**带该修复**的 GeoIP：

- 扩展源码取自含修复的 `1.12-dev`，因此天然包含此修复；
- 工作流按矩阵分别对 `1.11-dev` / `1.12-dev` 的源码树编译，并同时产出
  **Linux（`geoip.ext.so`）与 Windows（`geoip.ext.dll`）** 两个平台的二进制
  —— 1.11 那份同样带着修复；
- 构建前用 `patches/geoip_fix_2335.patch` **显式核验**修复存在：
  万一将来源码被换回 `1.11-dev` 的无修复版本，会自动打上补丁；
  补丁也打不上就**直接中止构建**，绝不静默产出没有中文支持的二进制。

修复的细节与补丁维护方式见 [`patches/README.md`](patches/README.md)。

## 产物与安装

### 从 Releases 下载（推荐）

打 `v*` 标签（如 `v1.0.0`）后，Actions 会自动创建 Release，附件按 SourceMod 版本打包，
每个包内含 **Linux 与 Windows** 两个二进制：

| Release 附件 | 适用 SourceMod | 内含 |
| --- | --- | --- |
| `geoip-ext-1.11-dev.zip` | SourceMod 1.11 | `geoip.ext.so`（Linux）+ `geoip.ext.dll`（Windows） |
| `geoip-ext-1.12-dev.zip` | SourceMod 1.12 | `geoip.ext.so`（Linux）+ `geoip.ext.dll`（Windows） |
| `SHA256SUMS.txt` | — | 上面两个包的校验和 |

```bash
# 发布一个版本
git tag v1.0.0
git push origin v1.0.0
```

也可以在每次 Actions 运行页的 **Artifacts** 里拿到**分平台**的包
（`geoip-ext-<版本>-<平台>.zip`，含 `.sha256` 校验和）。

> 两套二进制**分别构建**，按服务端平台选用：Linux 服务端用 `.so`，Windows 服务端用 `.dll`。
> 都包含 PR #2335 中文语言码修复，区别只在于链接的 SourceMod 头文件 / 版本库不同。

### 安装

1. 解压到服务端根目录（包内已按 `addons/sourcemod/extensions/` 组织好目录结构）：

   ```
   <游戏服务端>/
   └── addons/sourcemod/extensions/
       ├── geoip.ext.so      # Linux 服务端用这个
       └── geoip.ext.dll     # Windows 服务端用这个
   ```

2. 下载 GeoIP 数据库（**不包含在本仓库中**），放到
   `addons/sourcemod/configs/geoip/`，文件名使用 `GeoLite2-City.mmdb`：

   ```bash
   # 需要 MaxMind 账号（免费注册后获取 license key）
   curl -fsSL "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=<YOUR_LICENSE_KEY>&suffix=tar.gz" \
     -o GeoLite2-City.tar.gz
   tar -xzf GeoLite2-City.tar.gz --strip-components=1 --wildcards '*/GeoLite2-City.mmdb' \
     -C addons/sourcemod/configs/geoip/
   ```

3. 重启服务端（或 `sm exts load geoip`），用 `sm exts list` 确认 GeoIP 已加载。

扩展启动时会检查数据库文件：若数据库缺失或过期超过 90 天，会在 SourceMod 日志中给出提示。

### 怎么确认中文修复生效

服务端语言设为中文（`sm_language` / `sm_lang`，或用 `chi` 语言包），然后：

```sourcepawn
char ip[32], city[128];
GetClientIP(client, ip, sizeof(ip));
GeoipCity(ip, city, sizeof(city));      // 数据库支持 zh-CN 时会返回中文城市名
PrintToServer("%s", city);
```

如果拿到中文（而不是 `en` 回退值），说明修复已生效。

## 背景：这个扩展本身

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

## 仓库结构

```
.
├── .github/workflows/build.yml   # 编译工作流（1.11-dev / 1.12-dev 矩阵）
├── extensions/geoip/             # 扩展源码，目录位置与上游保持一致
│   ├── AMBuilder                 #   AMBuild 构建描述
│   ├── extension.cpp/.h          #   扩展主体（注册 native）
│   ├── geoip_util.cpp/.h         #   native 实现（PR #2335 修复就在 geoip_util.cpp）
│   ├── maxminddb.c/.h            #   内嵌 libmaxminddb
│   └── ...
├── patches/
│   ├── README.md                 # PR #2335 修复说明与维护方式
│   └── geoip_fix_2335.patch      # 中文语言码修复补丁（构建时核验/回填）
├── tools/
│   ├── build-geoip.sh            # 构建脚本（CI 与本地共用）
│   ├── filter-build-scripts.py   # 裁剪 AMBuildScript：只构建 geoip 扩展
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
`1.11-dev` 与 `1.12-dev` 的 `extensions/geoip/` 差异极小 —— **全仓库只差这一处，
而且正是本仓库要补的那一处**：

| 文件 | 1.11-dev vs 1.12-dev |
| --- | --- |
| `AMBuilder`、`extension.cpp/.h`、`geoip_util.h`、`maxminddb*`、`data-pool.*`、`osdefs.h`、`smsdk_config.h`、`version.rc` | **字节完全相同（13/14）** |
| `geoip_util.cpp` | **就是 PR #2335 的 `chi` → `zh-CN` 修复**（1.12 有，1.11 没有） |

这一点很关键：两分支的扩展源码本来就几乎一样，唯一的差别恰好是中文修复，
而该修复只用 `strcmp` 与 `std::string`，**不涉及任何版本相关的 API**，
所以在 1.11 上编译运行毫无障碍。于是做法就很直接：拿带修复的源码，
分别对两棵源码树编译，1.11 那份也就带上了修复。

两个平台版本分别链接各自分支的 `public/` 头文件与 versionlib，所以产物互不混用。

## 编译细节

### 构建矩阵与环境

| 平台 | runner | 编译器 | 产物 |
| --- | --- | --- | --- |
| Linux | `ubuntu-22.04` | `clang-14` / `clang++-14` | `geoip.ext.so` |
| Windows | `windows-2022` | MSVC（AMBuild 自动探测） | `geoip.ext.dll` |
| SourceMod 版本 | `1.11-dev` 与 `1.12-dev`（Windows 目前只构建 1.12） | | |

**Linux**：工具链在 workflow 里显式安装

```yaml
env:
  CC: clang-14
  CXX: clang++-14
```

```bash
sudo dpkg --add-architecture i386
sudo apt-get install -y clang-14 build-essential gcc-multilib g++-multilib \
  libstdc++6 lib32stdc++6 libc6-dev libc6-dev-i386 \
  linux-libc-dev linux-libc-dev:i386 lib32z1-dev \
  patch zip file python3 python3-pip python3-venv
```

依赖清单与编译器版本对齐 SourceMod 官方 PR 检查
（`sourcemod/.github/workflows/pr-checks.yml` 在 `ubuntu-22.04` 上用的 `clang-14`）。

**Windows**：`windows-2022` runner 自带 MSVC，**不设** `CC`/`CXX`，
交由 AMBuild 自动探测（矩阵里 Windows 条目的 `cc`/`cxx` 留空）。
只额外需要 AMBuild 与打包工具，`patch` 若缺失会自动回退到 `git apply`。

两点说明：

- **必须有 i386 multilib 开发库**：目标是 x86，64 位宿主上缺了这些包，
  编译能过但**链接 32 位目标会失败**。工作流里还有一步 `-m32` 试编译，
  提前把这类问题暴露出来。
- **AMBuild 装在独立 venv 里**：Ubuntu 的 `python3` 受 PEP 668 保护，
  不能直接 `pip install` 到系统环境；venv 路径通过 `$GITHUB_PATH` 注入，
  构建脚本才能在 PATH 上找到 `ambuild` 命令。Windows 上 venv 的
  `Scripts/` 布局由脚本自动识别。

> 早期版本这里用的是 SourceMod 官方 CI 的镜像
> `ghcr.io/alliedmodders/build-containers/debian11-clang22`，
> 但在本仓库的 runner 上下文里该镜像拿不到 `clang++`（容器内 PATH 找不到编译器，
> 报 `clang++: command not found`）。改为显式安装后不再依赖任何第三方镜像。

### 只构建 geoip（`tools/filter-build-scripts.py`）

根 `AMBuildScript` 的 `BuildScripts` 会编译**整棵源码树的所有扩展**。这些扩展各有各的
依赖，与 geoip 完全无关却会让构建失败 —— 实测 1.11 就死在：

```
extensions/regex/extension.cpp:34:10: fatal error: 'sh_string.h' file not found
```

因此编译前会把 `AMBuildScript` 里除 geoip 外的扩展移出构建列表（只改构建脚本，
不动源码；`loader` / `core` / `core/logic` / `versionlib` / `plugins` 全部保留）：

```
[only] 已裁剪 AMBuildScript：仅构建 geoip 扩展
```

这一步是安全的，因为 geoip 的 `AMBuilder` 只引用自身源码、`../../public/smsdk_ext.cpp`
和 `public/` 头文件，**不依赖任何其它扩展**。脚本用 `trap ... EXIT` 保证构建结束
（含失败或中断）后把 `AMBuildScript` 还原，不在源码树里留痕。

### 编译参数

```bash
python3 ../configure.py \
  --enable-optimize \          # -O3 / NDEBUG
  --no-color \
  --sdks=present \             # 见下：两代构建系统的差异用同一套写法解决
  --no-mysql \                 # 不构建 MySQL 扩展，免去 MySQL 5.5 头文件依赖
  --targets=x86 \              # 服务端为 32 位
  --mms-path=<deps>/mmsource-1.12
ambuild
```

**SDK 参数是踩坑点**：老写法 `--sdks=none` 在 1.12 上不再有效 —— 1.12 把 SDK 改成
manifest 驱动（`hl2sdk-manifests/SdkHelpers.ambuild`），`none` 不再是关键字，会被当成
SDK 名去找 `hl2sdk-none`，直接报 `Missing hl2sdks: none`。

现在统一用 `--sdks=present` + 一个 **mock SDK 目录**，两代都成立：

- `present` 的语义是「有什么用什么」，缺失的 SDK 只打印警告。其它取值会走
  `shouldRequireSdk()` → 缺失即 `raise`（`none` 失败就是这个机制）。
- **必须至少有一个可构建的 SDK**，否则 1.12 报 `No buildable SDKs were found`、
  1.11 报 `No applicable SDKs were found`。所以脚本会准备一个 `hl2sdk-mock` 目录。
- 这个 mock 只用于满足上面的前置条件：**geoip 不引用任何 SDK 头文件**，
  且其它扩展已被移出构建列表，所以它不会让任何东西被多编译出来。

> **`checkout-deps.sh -s mock` 是不可用的。** 它把 `mock` 当普通 SDK 处理，会去执行
> `git clone -b mock https://github.com/alliedmodders/hl2sdk` —— 而该仓库**没有 `mock`
> 分支**（mock 在独立仓库 `alliedmodders/hl2sdk-mock`）。结果是 clone 失败、`deps/`
> 里一个 SDK 都不剩，两个分支都会卡在「没有可用 SDK」。所以脚本改为：用
> `checkout-deps.sh -s none` 只取 Metamod:Source，然后直接从 `alliedmodders/hl2sdk-mock`
> 浅克隆 mock SDK，并用 manifest `include_paths` 里的真实文件（`public/tier1/strtools.h`）
> 校验目录结构完整。configure 显式传 `--hl2sdk-root=$deps`，让 manifest 系统据此发现它。

### PR #2335 修复的核验（`tools/build-geoip.sh` 第 0 步）

编译开始前会强制核验中文修复是否在源码里，避免"来源码一换、修复静默丢失"：

```
[patch] 源码缺少 PR #2335 修复，应用 patches/geoip_fix_2335.patch
[patch] 补丁应用成功（源码此前是 1.11-dev 的无修复版本）
```

正常情况（源码取自 1.12-dev）输出的是：

```
[ok] PR #2335 中文语言码修复已存在于源码（strcmp(code, "chi")）
```

判定方式是查找标记 `strcmp(code, "chi")`；找不到才打补丁，打完再复查一次；
补丁失败或复查仍缺失就**中止构建**。详细说明见 [`patches/README.md`](patches/README.md)。

### 其他两点硬性要求

- **必须提供 Metamod:Source 源码**：`AMBuildScript` 的 `detectSDKs()` 会无条件校验
  `mms_root`（core 的 SourceHook 头文件需要它），即使不构建任何 HL2SDK 也不例外。
  各分支需要的版本不同（1.11-dev → `mmsource-1.10`，1.12-dev → `mmsource-1.12`），
  脚本从 `tools/checkout-deps.sh` 里解析出版本号，再按 `<版本>-dev` 分支**直接 clone**。

  > **不能直接用 `checkout-deps.sh` 拉 Metamod。** SourceMod 1.11-dev 的该脚本里写的是
  > `name=mmsource-1.10` 配 `branch=master` —— 它会 clone `metamod-source` 的 `master`
  > （1.13 时代），而那个版本**已经没有 `core/sourcehook` 目录**了（重新组织过），
  > 于是 core 编译时报 `fatal error: 'sh_vector.h' file not found`。
  > 所以脚本改为按正确分支（`1.10-dev` / `1.12-dev`）显式 clone，并校验
  > `core/sourcehook/{sourcehook,sh_vector,sh_string}.h` 三个文件都在。
  > 顺带也避开了该脚本固定要下载的 ~300 MB MySQL 与整个 hl2sdk 镜像仓库。

- **`public/safetyhook` 只有 1.12 有**：1.11-dev 既没有这个目录，也不在
  `AMBuildScript` 里引用它。自检因此对该目录单独豁免（存在才校验），
  否则 1.11 会被误判为"源码树结构不符"。
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

### 同步时请留住 PR #2335 修复

务必**从 `1.12-dev` 同步**（它含修复）：

```bash
python3 tools/sync-upstream.py --branch 1.12-dev
grep -n 'zh-CN' extensions/geoip/geoip_util.cpp   # 应能查到
```

如果哪天确实要从 `1.11-dev` 同步（该分支**不含**修复），同步后源码里的中文修复会消失。
这时不必手动改代码 —— 构建脚本会自动应用 `patches/geoip_fix_2335.patch` 并打印
`[patch]` 提示。也可以先本地确认：

```bash
grep -c 'strcmp(code, "chi")' extensions/geoip/geoip_util.cpp   # 期望 1；为 0 则构建时会被打补丁
python3 tools/validate.py                                       # 自检会一并核验该修复
```

## 仓库自检

```bash
python3 tools/validate.py
```

检查内容包括：文件清单完整性、`AMBuilder` 是否与上游字节一致（决定能否在源码树中编译）、
**PR #2335 中文修复是否在源码中（`patches/` 完整性）**、
工作流 YAML 结构（矩阵是否覆盖 1.11/1.12、是否拉取 submodule）、构建脚本关键参数，
以及 `bash -n` 语法检查与文本文件编码/行尾规范。

## 许可

扩展源码版权归 AlliedModders LLC 所有，遵循 **GNU GPL v3**（含 Source 引擎链接例外条款），
与上游一致，详见各源文件头部声明与 <https://www.sourcemod.net/license.php>。
