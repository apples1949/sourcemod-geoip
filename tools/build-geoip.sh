#!/usr/bin/env bash
#
# 在 SourceMod 源码树中构建 GeoIP 扩展。
#
# GeoIP 是 SourceMod 的 in-tree 扩展：它引用 SourceMod 自身的构建系统
# (AMBuildScript / configure.py)、公共头文件 (public/smsdk_ext.h) 以及构建期生成的
# sourcemod_version.h，并内嵌 libmaxminddb 源码 (maxminddb.c)，因此没有外部库依赖。
# 本脚本把它放进 SourceMod 源码树后调用官方构建流程。
#
# 用法:
#   tools/build-geoip.sh --sourcemod <SourceMod源码树> [选项]
#
# 选项:
#   --sourcemod PATH   已 clone 好的 SourceMod 源码树（必需；需含 submodule）
#   --deps PATH        依赖目录，用于存放 Metamod:Source（默认 <源码树>/../deps）
#   --target-arch A    目标架构，默认 x86（SourceMod 服务端为 32 位）
#   --out PATH         产物输出目录（默认 <当前目录>/out）
#   --skip-deps        跳过 Metamod:Source 拉取（依赖目录里已有 mmsource-*）
#   -h | --help        显示帮助
#
set -euo pipefail

# 记录调用时的目录：后面会 cd 进构建目录，相对路径必须以此为基准
INVOKE_DIR="$PWD"

TARGET_ARCH="x86"
SM_TREE=""
DEPS_DIR=""
OUT_DIR=""
SKIP_DEPS=0

die() {
  printf '\n[error] %s\n' "$*" >&2
  exit 1
}

info() { printf '\n[info] %s\n' "$*"; }

usage() { sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --sourcemod)   SM_TREE="${2:-}"; shift 2 ;;
    --deps)        DEPS_DIR="${2:-}"; shift 2 ;;
    --target-arch) TARGET_ARCH="${2:-}"; shift 2 ;;
    --out)         OUT_DIR="${2:-}"; shift 2 ;;
    --skip-deps)   SKIP_DEPS=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    *)             die "未知参数: $1（用 --help 查看用法）" ;;
  esac
done

[ -n "$SM_TREE" ]  || die "缺少 --sourcemod 参数"
[ -d "$SM_TREE" ]  || die "SourceMod 源码树不存在: $SM_TREE"
[ -f "$SM_TREE/configure.py" ] || die "不是有效的 SourceMod 源码树（缺少 configure.py）: $SM_TREE"
[ -f "$SM_TREE/AMBuildScript" ] || die "不是有效的 SourceMod 源码树（缺少 AMBuildScript）: $SM_TREE"

SM_TREE="$(cd "$SM_TREE" && pwd)"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$REPO_ROOT/extensions/geoip"
BUILD_DIR="$SM_TREE/build"

# 把 --out / --deps 统一转成绝对路径，避免后续 cd 导致相对路径解析到别处
abs_dir() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    '~') printf '%s\n' "$HOME" ;;
    '~/'*) printf '%s\n' "$HOME/${1#\~/}" ;;
    *) printf '%s\n' "$INVOKE_DIR/$1" ;;
  esac
}
OUT_DIR="$(abs_dir "${OUT_DIR:-$INVOKE_DIR/out}")"
DEPS_DIR="$(abs_dir "${DEPS_DIR:-$(dirname "$SM_TREE")/deps}")"

[ -d "$SRC_DIR" ] || die "找不到扩展源码目录: $SRC_DIR"

# --- 构建期自检 ----------------------------------------------------------------
# 尽早失败：这些文件缺失会导致难以定位的构建错误，甚至产出信息错误的扩展。

# 1) SourceMod 自身的关键文件
[ -f "$SM_TREE/product.version" ] || die "SourceMod 源码树缺少 product.version: $SM_TREE"
# version.rc / GetExtensionVerString() 依赖构建期生成的 sourcemod_version.h，
# 而该文件（位于 public/）由 versionlib 在构建时改写，源码树里带的是模板。
[ -f "$SM_TREE/public/smsdk_ext.cpp" ] || die "SourceMod 源码树缺少 public/smsdk_ext.cpp（submodule 未拉取？）"

# 2) submodule 是否真的检出内容
#    .gitmodules 里声明的 path -> 一处用于确认的关键文件
#    注意两点：
#    a) public/amtl 是指向 alliedmodders/amtl 的 submodule，而 AMTL 仓库里还有一层
#       amtl/ 目录，头文件实际在 public/amtl/amtl/ —— AMBuildScript 的 include 路径同样如此
#    b) public/safetyhook 是 **1.12 才有的** submodule（1.11 既没有该目录也不引用它），
#       所以只有目录存在时才校验，否则 1.11 会被误判为"结构不符"
#    用进程替换而非管道：管道里的 while 在子 shell 中运行，die 只会退出子 shell。
#    下面 heredoc 是纯数据（引号形式不做展开），因此不能写行内注释。
while IFS=: read -r dir probe label; do
  [ -n "$dir" ] || continue
  if [ -f "$SM_TREE/$dir/$probe" ]; then
    echo "[ok] $label 已就绪"
  elif [ -d "$SM_TREE/$dir" ] && [ "$(find "$SM_TREE/$dir" -type f 2>/dev/null | wc -l)" -eq 0 ]; then
    die "$label 为空：submodule 未拉取。请用 --recurse-submodules 克隆，或执行 git -C \"$SM_TREE\" submodule update --init --recursive"
  elif [ "$dir" = "public/safetyhook" ] && [ ! -d "$SM_TREE/$dir" ]; then
    # 该分支根本没有这个 submodule（1.11 及更早），属正常
    echo "[ok] $label 在该分支不存在，跳过"
  else
    die "$label 缺少 $dir/$probe —— 源码树结构不符合预期（submodule 版本不对？）"
  fi
done < <(cat <<'SUBMODULES'
public/amtl:amtl/am-string.h:AMTL（public/amtl）
sourcepawn:include/sp_vm_api.h:SourcePawn（sourcepawn）
public/safetyhook:include/safetyhook.hpp:SafetyHook（public/safetyhook）
SUBMODULES
)

# 3) SDK 参数：geoip 不依赖任何 HL2SDK，也不需要真正可用的 SDK 内容，
#    但 configure 的 detectSDKs() 要求"至少有一个可构建的 SDK"，写法两代不同：
#    1.11：--sdks=none 是关键字，跳过所有 SDK；但该分支仍有
#          len(self.sdks) < 1 and not use_none 的校验，none 可满足
#    1.12：SDK 改为 manifest 驱动（根 AMBuildScript 用 builder.Eval 加载
#          hl2sdk-manifests/SdkHelpers.ambuild），"none" 不再是关键字，
#          会被当成 SDK 名去找 hl2sdk-none，报 "Missing hl2sdks: none"
#    统一采用 --sdks=present + 一个 mock SDK 目录（见第 2 步）：
#      - present 语义是"有什么用什么"：缺失的 SDK 只警告不报错
#        （非 present 时会走 shouldRequireSdk -> 缺失即 raise，这正是 none 失败的机制）
#      - 有 mock 目录在场即可满足"至少一个可构建 SDK"，避免
#        1.12 的 'No buildable SDKs were found' 与 1.11 的 'No applicable SDKs were found'
#      - mock 仅用于满足前置条件：geoip 不引用任何 SDK 头文件，
#        且其它扩展已被移出构建列表
SDK_ARG="present"
echo "[sdk] --sdks=$SDK_ARG（仅构建 geoip，不需要真正的 HL2SDK）"

if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
command -v "$PY" >/dev/null 2>&1 || die "找不到 python3"
"$PY" -c 'import ambuild2' 2>/dev/null \
  || die "缺少 AMBuild: python3 -m pip install 'git+https://github.com/alliedmodders/ambuild.git'"
command -v ambuild >/dev/null 2>&1 || die "找不到 ambuild 命令（AMBuild 未安装完整）"

# --- 0. 核验本仓库存在的目的：必须带上 SourceMod PR #2335 的中文语言码修复 ---------
# 上游只在 master（1.13）有该修复（其后回移到 1.12-dev），1.11-dev 至今没有。
# 本仓库源码取自 1.12-dev，天然包含；这里做一次显式核验，避免将来源码回退成
# 1.11-dev 版本时"静默地少掉中文修复"。
PATCH_FILE="$REPO_ROOT/patches/geoip_fix_2335.patch"
LANG_FIX_MARK='strcmp(code, "chi")'

apply_lang_fix() {
  # 在独立临时目录里打补丁（patch -p1 可去掉 a/ b/ 前缀），避免 git apply
  # 在"源码树位于仓库之外"时的仓库上下文限制。
  local tmp rc
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/extensions/geoip"
  cp -a "$SRC_DIR/geoip_util.cpp" "$tmp/extensions/geoip/geoip_util.cpp"
  if command -v patch >/dev/null 2>&1; then
    ( cd "$tmp" && patch -p1 --batch --forward --silent < "$PATCH_FILE" )
    rc=$?
  elif command -v git >/dev/null 2>&1; then
    ( cd "$tmp" && git apply -p1 "$PATCH_FILE" )
    rc=$?
  else
    rm -rf "$tmp"
    die "缺少 patch/git 工具，无法应用 PR #2335 补丁"
  fi
  if [ "$rc" -ne 0 ]; then
    rm -rf "$tmp"
    return 1
  fi
  cp -a "$tmp/extensions/geoip/geoip_util.cpp" "$SRC_DIR/geoip_util.cpp"
  rm -rf "$tmp"
  return 0
}

if [ ! -f "$PATCH_FILE" ]; then
  echo "[patch] 警告: 未找到 $PATCH_FILE，跳过核验（产物将不含 PR #2335 中文修复）"
elif grep -qF "$LANG_FIX_MARK" "$SRC_DIR/geoip_util.cpp"; then
  echo "[ok] PR #2335 中文语言码修复已存在于源码（$LANG_FIX_MARK）"
else
  echo "[patch] 源码缺少 PR #2335 修复，应用 patches/geoip_fix_2335.patch"
  apply_lang_fix || die "应用 PR #2335 补丁失败：请检查 extensions/geoip/geoip_util.cpp 是否与上游发生冲突性改动"
  grep -qF "$LANG_FIX_MARK" "$SRC_DIR/geoip_util.cpp" \
    || die "补丁已执行但未检测到修复标记，产物会缺少中文支持，已中止"
  echo "[patch] 补丁应用成功（源码此前是 1.11-dev 的无修复版本）"
fi

info "SourceMod 源码树 : $SM_TREE"
info "扩展源码         : $SRC_DIR"
info "依赖目录         : $DEPS_DIR"
info "目标架构         : $TARGET_ARCH"
info "SDK 参数         : --sdks=$SDK_ARG"
info "产物目录         : $OUT_DIR"

# --- 1. 把扩展源码同步进 SourceMod 源码树 --------------------------------------
mkdir -p "$SM_TREE/extensions"
rm -rf "$SM_TREE/extensions/geoip"
cp -a "$SRC_DIR" "$SM_TREE/extensions/geoip"
echo "[ok] 已同步扩展源码 -> $SM_TREE/extensions/geoip"

# --- 1b. 只构建 geoip：把 AMBuildScript 里其它扩展移出构建列表 ------------------
# 根 AMBuildScript 的 BuildScripts 会编译**整棵源码树**的所有扩展，那些扩展各有各的
# 依赖（regex 需要 SourceHook 的 sh_string.h、部分需要 HL2SDK 等），与 geoip 无关却会
# 让构建失败。geoip 的 AMBuilder 只引用自身源码、../../public/smsdk_ext.cpp 和 public/
# 头文件，不依赖任何其它扩展，因此把非 geoip 的扩展从列表中剔除。
# 只改 AMBuildScript（非源码），且构建结束/中断都会还原。
AMB_FILE="$SM_TREE/AMBuildScript"
AMB_BAK="$AMB_FILE.geoip-bak"
[ -f "$AMB_FILE" ] || die "缺少 $SM_TREE/AMBuildScript"
cp -f "$AMB_FILE" "$AMB_BAK"
restore_amb() {
  if [ -f "$AMB_BAK" ]; then
    cp -f "$AMB_BAK" "$AMB_FILE"
    rm -f "$AMB_BAK"
  fi
}
trap 'restore_amb' EXIT

if ! "$PY" "$REPO_ROOT/tools/filter-build-scripts.py" "$AMB_FILE" --keep geoip; then
  die "裁剪构建列表失败，已中止（不会产出只含 geoip 的构建）"
fi
echo "[only] 已裁剪 AMBuildScript：仅构建 geoip 扩展"

# --- 2. 依赖：Metamod:Source + 一个可用的 SDK 目录 ------------------------------
# 两个硬性前提（只构建 geoip 也不可省）：
#   a) AMBuildScript 的 detectSDKs() 无条件校验 mms_root（core 的 SourceHook 头文件）
#   b) 必须至少有一个"可构建的 SDK"，否则 1.11 报 'No applicable SDKs were found'，
#      1.12 报 'No buildable SDKs were found'
#
# 注意 checkout-deps.sh 的 -s mock 是**不可用**的：它按普通 SDK 处理，会去
#   git clone -b mock https://github.com/alliedmodders/hl2sdk
# 而该仓库根本没有 mock 分支（mock 在独立仓库 alliedmodders/hl2sdk-mock），
# 结果 clone 失败、deps 里一个 SDK 都不剩，两个分支都因此失败过。
if [ "$SKIP_DEPS" -eq 0 ]; then
  mkdir -p "$DEPS_DIR"
  [ -f "$SM_TREE/tools/checkout-deps.sh" ] \
    || die "SourceMod 源码树缺少 tools/checkout-deps.sh，无法判断所需依赖版本（可加 --skip-deps 自行准备）"

  # Metamod:Source 的目录名与 git 分支**不总是一致**：
  #   sourcemod 1.11-dev 的 checkout-deps.sh 里写的是 name=mmsource-1.10 / branch=master
  #   -> 它会去 clone metamod-source 的 master，而 master（1.13 时代）已经没有
  #      core/sourcehook 目录了（重新组织过），于是 core 编译时报
  #      fatal error: 'sh_vector.h' file not found
  # 因此不能依赖该脚本取 Metamod，必须按正确分支显式 clone 并校验 sourcehook 头文件。
  MMS_DIR_NAME=""
  for v in 1.12 1.11 1.10; do
    if grep -q "mmsource-$v" "$SM_TREE/tools/checkout-deps.sh" 2>/dev/null; then
      MMS_DIR_NAME="mmsource-$v"
      break
    fi
  done
  [ -n "$MMS_DIR_NAME" ] || die "无法从 tools/checkout-deps.sh 判断需要的 Metamod:Source 版本"
  # mmsource-1.12 -> 分支 1.12-dev
  MMS_BRANCH="${MMS_DIR_NAME#mmsource-}-dev"
  MMS_PATH="$DEPS_DIR/$MMS_DIR_NAME"

  mmsource_ok() {
    [ -f "$1/core/sourcehook/sourcehook.h" ] && \
    [ -f "$1/core/sourcehook/sh_vector.h" ] && \
    [ -f "$1/core/sourcehook/sh_string.h" ]
  }

  if [ -d "$MMS_PATH/.git" ] && mmsource_ok "$MMS_PATH"; then
    echo "[mms] Metamod:Source 已就绪 -> $MMS_PATH"
  else
    if [ -d "$MMS_PATH" ]; then
      echo "[mms] $MMS_PATH 不完整（缺 core/sourcehook 头文件），重新克隆"
      rm -rf "$MMS_PATH"
    fi
    info "克隆 Metamod:Source（分支 $MMS_BRANCH -> $MMS_DIR_NAME）"
    # 1.10-dev 没有 submodule，1.12-dev 有（third_party/amtl、hl2sdk-manifests）。
    # 先带 submodule 克隆；失败则清掉半成品再退回普通克隆（1.10-dev 无 submodule，
    # 普通克隆即完整）。
    clone_mms() {
      if git clone --depth 1 --branch "$MMS_BRANCH" \
           --recurse-submodules --shallow-submodules \
           https://github.com/alliedmodders/metamod-source.git "$MMS_PATH"; then
        return 0
      fi
      [ -e "$MMS_PATH" ] && rm -rf "$MMS_PATH"
      git clone --depth 1 --branch "$MMS_BRANCH" \
        https://github.com/alliedmodders/metamod-source.git "$MMS_PATH"
    }
    clone_mms || die "无法克隆 Metamod:Source 分支 $MMS_BRANCH"
    mmsource_ok "$MMS_PATH" \
      || die "Metamod:Source 副本缺少 core/sourcehook 头文件（分支 $MMS_BRANCH 是否正确？）"
    echo "[mms] Metamod:Source 就绪 -> $MMS_PATH"
  fi

  # SDK 目录：用 mock 满足"至少一个可构建 SDK"。直接取 alliedmodders/hl2sdk-mock
  # （浅克隆即可，只会被当作 SDK 根目录使用，geoip 并不引用其中任何头文件）。
  # 注意不能走 checkout-deps.sh 的 -s mock：它按普通 SDK 去 clone hl2sdk 的 mock 分支，
  # 而该分支不存在（mock 在独立仓库 hl2sdk-mock），会失败且一个 SDK 都不剩。
  fetch_mock_sdk() {
    if [ -f "$DEPS_DIR/hl2sdk-mock/public/tier1/strtools.h" ]; then
      echo "[sdk] hl2sdk-mock 已存在"
      return 0
    fi
    rm -rf "$DEPS_DIR/hl2sdk-mock"
    echo "[sdk] 克隆 hl2sdk-mock（mock SDK，约数 MB）"
    git clone --depth 1 https://github.com/alliedmodders/hl2sdk-mock.git \
      "$DEPS_DIR/hl2sdk-mock" || return 1
    # 用 manifest include_paths 里的真实文件确认目录结构可用
    [ -f "$DEPS_DIR/hl2sdk-mock/public/tier1/strtools.h" ] || return 1
    return 0
  }

  if fetch_mock_sdk; then
    echo "[sdk] mock SDK 就绪 -> $DEPS_DIR/hl2sdk-mock"
  else
    # 退化方案：mock 不可用时改用真实 SDK。
    echo "[sdk] mock 不可用，回退到真实 SDK: tf2"
    name=hl2sdk-tf2
    if [ ! -d "$DEPS_DIR/$name" ]; then
      git clone --depth 1 -b tf2 https://github.com/alliedmodders/hl2sdk.git "$DEPS_DIR/$name" \
        || die "无法获取任何可用的 SDK（mock 与 tf2 均失败）"
    fi
  fi
else
  info "按 --skip-deps 跳过依赖拉取"
fi

# --- 3. 定位 Metamod:Source ----------------------------------------------------
if [ "$SKIP_DEPS" -eq 1 ]; then
  shopt -s nullglob
  mms_candidates=("$DEPS_DIR"/mmsource-*)
  shopt -u nullglob
  [ "${#mms_candidates[@]}" -eq 1 ] \
    || die "在 $DEPS_DIR 找不到唯一的 mmsource-*（--skip-deps 时需自行准备好）"
  MMS_PATH="$(cd "${mms_candidates[0]}" && pwd)"
fi
MMS_PATH="$(cd "$MMS_PATH" && pwd)"
[ -d "$MMS_PATH/core" ] || die "Metamod:Source 副本不完整（缺少 core/）: $MMS_PATH"
echo "[mms] 使用 -> $MMS_PATH"

# --- 4. configure --------------------------------------------------------------
# --sdks=none : GeoIP 不依赖任何 HL2SDK，也避免拉取数 GB 的 SDK 仓库
# --no-mysql  : 不构建 MySQL 扩展（避免强制要求 MySQL 5.5 头文件/Lib）
# --targets   : SourceMod 服务端为 32 位
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# 诊断信息：1.12 的 SDK 解析依赖 deps 目录里实际存在哪些 hl2sdk-*，
# 出问题时这段日志能直接说明"库里有什么"。
if [ -d "$DEPS_DIR" ]; then
  echo "[deps] $DEPS_DIR 内容:"
  find "$DEPS_DIR" -maxdepth 1 -mindepth 1 -type d -printf '  %f\n' 2>/dev/null | sort || \
    ls -1 "$DEPS_DIR" | sed 's/^/  /'
fi

info "configure"
echo "[cmd] configure.py --enable-optimize --no-color --sdks=$SDK_ARG --no-mysql --targets=$TARGET_ARCH --mms-path=$MMS_PATH --hl2sdk-root=$DEPS_DIR"
(
  cd "$BUILD_DIR"
  "$PY" ../configure.py \
    --enable-optimize \
    --no-color \
    "--sdks=$SDK_ARG" \
    --no-mysql \
    --targets="$TARGET_ARCH" \
    "--mms-path=$MMS_PATH" \
    "--hl2sdk-root=$DEPS_DIR"
)

# --- 5. 编译 -------------------------------------------------------------------
info "ambuild"
(
  cd "$BUILD_DIR"
  ambuild
)

# --- 6. 收集产物（先把源码树恢复原状）-----------------------------------------
restore_amb
echo "[only] 已还原 $AMB_FILE"

mapfile -t built < <(find "$BUILD_DIR/package" -type f -name 'geoip.ext.so' | sort)
[ "${#built[@]}" -gt 0 ] || die "构建结束但没找到 geoip.ext.so（构建是否失败或被跳过？）"

BIN="${built[0]}"
if [ "${#built[@]}" -gt 1 ]; then
  # 多架构时优先取 32 位（服务端使用的架构）
  for f in "${built[@]}"; do case "$f" in *x86/geoip.ext.so) BIN="$f" ;; esac; done
fi

mkdir -p "$OUT_DIR/package/addons/sourcemod/extensions"
cp -f "$BIN" "$OUT_DIR/package/addons/sourcemod/extensions/geoip.ext.so"
printf '%s\n' "$SM_TREE" > "$OUT_DIR/package/BUILD_SOURCEMOD_TREE.txt"

echo "[ok] 二进制 -> $BIN"
echo "[ok] 已复制 -> $OUT_DIR/package/addons/sourcemod/extensions/geoip.ext.so"
info "完成"
