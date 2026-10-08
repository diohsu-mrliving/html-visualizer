#!/usr/bin/env bash
# 把這四個 skill 裝進任何支援 skill 的 agent。
#
#   ./install.sh                 裝到 ~/.agents/skills（跨 agent 共通慣例）
#   ./install.sh --detect        掃機器上已存在的 agent skill 目錄，全部裝
#   ./install.sh --dir <path>    裝到指定目錄
#   ./install.sh --copy          用複製取代 symlink（預設 symlink，改了原始碼即時生效）
#   ./install.sh --uninstall     移除本腳本裝過的項目
#
# 只動自己的東西：目標位置不存在、是指向本 repo 的 symlink、或帶本 repo 安裝標記的目錄，才會安裝／移除；
# 其他（別人的同名 skill、指到別處的 symlink）一律跳過並警告。
# help 獨立安裝時改名為 html-visualizer-help（help 太通用、會撞別人的 skill 與 agent 內建的 /help）；
# plugin 安裝仍是 /html-visualizer:help。
# Claude Code 使用者建議改用 plugin 安裝（見 README），可以拿到版本管理與更新。
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills"
SKILLS=(html-visualizer chart diagram-design help)
MARK=".installed-by-html-visualizer"   # 本腳本建的目錄（--copy 或改名的 help）裡放這個標記

# 來源資料夾 → 安裝後的名字
dest_name() { [ "$1" = help ] && echo html-visualizer-help || echo "$1"; }

# 這個位置是不是本腳本裝的（可以覆蓋或移除）
ours() {
  local dest="$1" src="$2"
  if [ -L "${dest}" ]; then
    [ "$(readlink "${dest}")" = "$src" ]
  elif [ -d "${dest}" ]; then
    [ -f "${dest}/$MARK" ] && [ "$(cat "${dest}/$MARK")" = "${SRC}" ]
  else
    return 1
  fi
}

# 改名安裝的 help：frontmatter 的 name 要跟資料夾同名（Agent Skills 規範），所以不能直接 symlink，
# 改建一個真目錄：SKILL.md 換掉 name，references 連回（--copy 時複製）原始碼
install_renamed() {
  local src="$1" dest="$2" name="$3"
  mkdir -p "${dest}"
  awk -v n="${name}" 'NR==1 && /^---$/ {fm=1; print; next}
    fm && /^---$/ {fm=0}
    fm && !done && /^name:/ {print "name: " n; done=1; next}
    {print}' "$src/SKILL.md" > "${dest}/SKILL.md"
  if [ "$MODE" = copy ]; then
    cp -R "$src/references" "${dest}/references"
  else
    ln -s "$src/references" "${dest}/references"
  fi
  printf '%s' "${SRC}" > "${dest}/$MARK"
}

# 各家 agent 的 user-level skill 目錄。~/.agents 是多家共用的慣例路徑。
CANDIDATES=(
  "$HOME/.agents/skills"
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.cursor/skills"
  "$HOME/.cline/skills"
  "$HOME/.copilot/skills"
  "$HOME/.factory/skills"
  "$HOME/.kiro/skills"
  "$HOME/.config/opencode/skills"
  "$HOME/.pi/agent/skills"
)

MODE=link
ACTION=install
TARGETS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --detect)
      for d in "${CANDIDATES[@]}"; do
        [ -d "$(dirname "$d")" ] && TARGETS+=("$d")
      done
      shift ;;
    --dir) TARGETS+=("$2"); shift 2 ;;
    --copy) MODE=copy; shift ;;
    --uninstall) ACTION=uninstall; shift ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知參數：$1（用 --help 看用法）" >&2; exit 2 ;;
  esac
done

[ ${#TARGETS[@]} -eq 0 ] && TARGETS=("$HOME/.agents/skills")

[ -d "${SRC}" ] || { echo "找不到 skills 目錄：${SRC}" >&2; exit 1; }

for target in "${TARGETS[@]}"; do
  mkdir -p "${target}"
  # 舊版本腳本把 help 直接裝成 <target>/help：是指向本 repo 的 symlink 才清掉（別人的 help 不碰）
  if ours "${target}/help" "${SRC}/help"; then rm "${target}/help"; echo "移除舊名稱  ${target}/help"; fi
  for s in "${SKILLS[@]}"; do
    name="$(dest_name "${s}")"
    dest="${target}/${name}"
    if [ "$ACTION" = uninstall ]; then
      if ours "${dest}" "${SRC}/${s}"; then
        if [ -L "${dest}" ]; then rm "${dest}"; else rm -rf "${dest}"; fi
        echo "移除  ${dest}"
      elif [ -e "${dest}" ] || [ -L "${dest}" ]; then
        echo "跳過（不是本 repo 裝的，不動）  ${dest}" >&2
      fi
      continue
    fi
    if [ -e "${dest}" ] || [ -L "${dest}" ]; then
      if ! ours "${dest}" "${SRC}/${s}"; then
        echo "跳過：${dest} 已存在且不是本 repo 裝的（別的 skill 或指到別處的 symlink），不覆蓋。" >&2
        echo "  要換成本版請先自行確認、移除或改名。" >&2
        continue
      fi
      if [ -L "${dest}" ]; then rm "${dest}"; else rm -rf "${dest}"; fi
    fi
    if [ "${name}" != "${s}" ]; then
      install_renamed "${SRC}/${s}" "${dest}" "${name}"; echo "建立  ${dest}（${s} 改名安裝）"
    elif [ "$MODE" = copy ]; then
      cp -R "${SRC}/${s}" "${dest}"; printf '%s' "${SRC}" > "${dest}/$MARK"; echo "複製  ${dest}"
    else
      ln -s "${SRC}/${s}" "${dest}"; echo "連結  ${dest} -> ${SRC}/${s}"
    fi
  done
done

if [ "$ACTION" = install ]; then
  echo
  echo "裝好了。重開 agent 或重新載入 skill 後即可使用。"
  echo "選配（真瀏覽器版面檢查）：npm i -D playwright && npx playwright install chromium"
fi
