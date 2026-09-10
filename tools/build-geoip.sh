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
#    （注意 public/amtl 是指向 alliedmodders/amtl 的 submodule，而 AMTL 仓库里还有一层
#      amtl/ 目录，头文件实际在 public/amtl/amtl/ —— AMBuildScript 的 include 路径同样如此）
#    用进程替换而非管道：管道里的 while 在子 shell 中运行，die 只会退出子 shell。
#    下面 heredoc 是纯数据（引号形式不做展开），因此不能写行内注释。
while IFS=: read -r dir probe label; do
  [ -n "$dir" ] || continue
  if [ -f "$SM_TREE/$dir/$probe" ]; then
    echo "[ok] $label 已就绪"
  elif [ -d "$SM_TREE/$dir" ] && [ "$(find "$SM_TREE/$dir" -type f 2>/dev/null | wc -l)" -eq 0 ]; then
    die "$label 为空：submodule 未拉取。请用 --recurse-submodules 克隆，或执行 git -C \"$SM_TREE\" submodule update --init --recursive"
  else
    die "$label 缺少 $dir/$probe —— 源码树结构不符合预期（submodule 版本不对？）"
  fi
done < <(cat <<'SUBMODULES'
public/amtl:amtl/am-string.h:AMTL（public/amtl）
sourcepawn:include/sp_vm_api.h:SourcePawn（sourcepawn）
public/safetyhook:include/safetyhook.hpp:SafetyHook（public/safetyhook）
SUBMODULES
)

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
info "产物目录         : $OUT_DIR"

# --- 1. 把扩展源码同步进 SourceMod 源码树 --------------------------------------
mkdir -p "$SM_TREE/extensions"
rm -rf "$SM_TREE/extensions/geoip"
cp -a "$SRC_DIR" "$SM_TREE/extensions/geoip"
echo "[ok] 已同步扩展源码 -> $SM_TREE/extensions/geoip"

# --- 2. 依赖：Metamod:Source ---------------------------------------------------
# 注意: SourceMod 的 AMBuildScript 在 detectSDKs() 里无条件要求一个 Metamod:Source 源码副本
#       （用于 core 的 SourceHook 头文件），即使 --sdks=none 也一样。用官方脚本拉取。
if [ "$SKIP_DEPS" -eq 0 ]; then
  mkdir -p "$DEPS_DIR"
  if [ ! -d "$SM_TREE/tools/checkout-deps.sh" ] && [ ! -f "$SM_TREE/tools/checkout-deps.sh" ]; then
    die "SourceMod 源码树缺少 tools/checkout-deps.sh，无法拉取依赖（可加 --skip-deps 自行准备）"
  fi
  info "拉取 Metamod:Source（官方 tools/checkout-deps.sh，-s none 表示不拉 HL2SDK）"
  # checkout-deps.sh 要求当前目录是源码树之外的同级目录（它会写入 sourcemod/ 作为占位）
  (
    cd "$DEPS_DIR"
    mkdir -p sourcemod
    bash "$SM_TREE/tools/checkout-deps.sh" -s none
  )
else
  info "按 --skip-deps 跳过依赖拉取"
fi

# --- 3. 定位 Metamod:Source ----------------------------------------------------
# 各分支要求的 MetaMod 版本不同（1.11-dev 用 mmsource-1.10，1.12-dev 用 mmsource-1.12），
# 因此不写死版本号，按 glob 自动发现。
shopt -s nullglob
mms_candidates=("$DEPS_DIR"/mmsource-*)
shopt -u nullglob

[ "${#mms_candidates[@]}" -gt 0 ] \
  || die "在 $DEPS_DIR 找不到 mmsource-*（AMBuildScript 需要 Metamod:Source 源码）"
[ "${#mms_candidates[@]}" -eq 1 ] \
  || die "在 $DEPS_DIR 找到多个 mmsource-*，请清理只留一个: ${mms_candidates[*]}"
MMS_PATH="$(cd "${mms_candidates[0]}" && pwd)"
[ -d "$MMS_PATH/core" ] || die "Metamod:Source 副本不完整（缺少 core/）: $MMS_PATH"
echo "[ok] Metamod:Source -> $MMS_PATH"

# --- 4. configure --------------------------------------------------------------
# --sdks=none : GeoIP 不依赖任何 HL2SDK，也避免拉取数 GB 的 SDK 仓库
# --no-mysql  : 不构建 MySQL 扩展（避免强制要求 MySQL 5.5 头文件/Lib）
# --targets   : SourceMod 服务端为 32 位
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
info "configure"
(
  cd "$BUILD_DIR"
  "$PY" ../configure.py \
    --enable-optimize \
    --no-color \
    --sdks=none \
    --no-mysql \
    --targets="$TARGET_ARCH" \
    "--mms-path=$MMS_PATH"
)

# --- 5. 编译 -------------------------------------------------------------------
info "ambuild"
(
  cd "$BUILD_DIR"
  ambuild
)

# --- 6. 收集产物 ---------------------------------------------------------------
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
