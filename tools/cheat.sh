#!/usr/bin/env bash
# cheat.sh — full reference cheatsheet, designed to run in a floating pane

R='\033[0m'; B='\033[1m'; DIM='\033[2m'
BCYN='\033[96m'; BYLW='\033[93m'; BGRN='\033[92m'
BMAG='\033[95m'; WHT='\033[97m'; RED='\033[91m'
COLS="${COLUMNS:-90}"

hr()    { printf "${BCYN}${DIM}%*s${R}\n" "$COLS" '' | tr ' ' '─'; }
sec()   { echo; hr; printf "  ${B}${WHT}%s${R}\n" "$1"; hr; }
K()     { printf "  ${BYLW}${B}%-26s${R}  ${BGRN}%s${R}\n" "$1" "$2"; }
CMD()   { printf "  ${BCYN}%-26s${R}  ${DIM}%s${R}\n" "$1" "$2"; }
SUB()   { echo -e "\n  ${B}${WHT}$1${R}"; }

_cheat_content() {
echo -e "${BCYN}${B}"
cat << 'BANNER'
  ███████╗ ██████╗ ██████╗     CHEATSHEET
  ██╔════╝██╔═══██╗██╔══██╗
  █████╗  ██║   ██║██████╔╝
  ██╔══╝  ██║   ██║██╔══██╗
  ██║     ╚██████╔╝██████╔╝
  ╚═╝      ╚═════╝ ╚═════╝
BANNER
echo -e "${R}"

# ── FOB Commands ──────────────────────────────────────────────────────────────
sec "FOB COMMANDS"
CMD "fob brief [repo]"      "pick repos and launch workspace (or add tabs)"
CMD "fob attach"            "re-attach to running fob session"
CMD "fob exit"              "kill fob session and all panes"
CMD "fob status"            "repo, branch, session, .fob/ state"
CMD "fob resume"            "print Claude mission brief"
CMD "fob init [repo]"       "initialize .fob/ mission files"
CMD "fob test"              "run project tests"
CMD "fob audit"             "run project audit"
CMD "fob doctor"            "check all dependencies"
CMD "fob loadout"           "install and configure dev tools"
CMD "fob clear [--all]"    "delete saved layout (this repo or all)"
CMD "fob cheat"             "this screen"
echo

# ── Zellij ────────────────────────────────────────────────────────────────────
sec "ZELLIJ"

SUB "Panes"
K "Ctrl+p ↑↓←→"      "navigate panes"
K "Ctrl+p n"          "new pane"
K "Ctrl+p d"          "split down"
K "Ctrl+p r"          "split right"
K "Ctrl+p z"          "zoom pane fullscreen"
K "Ctrl+p x"          "close pane"
K "Ctrl+p f"          "toggle floating panes"
K "Ctrl+p e"          "embed / float pane"

SUB "Tabs"
K "Ctrl+t t"          "new tab"
K "Ctrl+t ←→"         "switch tab"
K "Ctrl+t 1-9"        "jump to tab"
K "Ctrl+t r"          "rename tab"
K "Ctrl+t x"          "close tab"

SUB "Sessions"
K "Ctrl+o d"          "detach (session keeps running)"
K "Ctrl+o w"          "session manager"

SUB "Scroll / Copy"
K "Ctrl+s ↑↓ / j k"  "scroll"
K "Ctrl+s e"          "edit scrollback in \$EDITOR"
K "select text"       "auto-copied to clipboard"
K "Shift+right-click" "terminal native clipboard menu"

SUB "Misc"
K "Ctrl+g"            "lock / unlock all keybindings"
K "Ctrl+h"            "help — all keybindings"
echo

# ── Dev Tools ─────────────────────────────────────────────────────────────────
sec "DEV TOOLS"

SUB "fzf — fuzzy finder"
CMD "Ctrl+r"              "fuzzy search shell history"
CMD "Ctrl+t"              "fuzzy search files"
CMD "Alt+c"               "fuzzy cd into directory"

SUB "lazygit — git TUI"
CMD "space"               "stage / unstage file"
CMD "c"                   "commit"
CMD "p"                   "push"
CMD "P"                   "pull"
CMD "b"                   "branch menu"
CMD "?"                   "help / all keybindings"

SUB "eza — modern ls"
CMD "eza --icons"         "ls with icons"
CMD "eza -la --git"       "long list with git status"
CMD "eza --tree -L 3"     "directory tree (3 levels)"

SUB "bat — syntax cat"
CMD "bat <file>"          "view file with syntax highlight"
CMD "bat -l python <file>" "force language"

SUB "zoxide — smart cd"
CMD "z <partial>"         "jump to most used matching dir"
CMD "zi"                  "interactive fuzzy jump (needs fzf)"

SUB "delta — git diffs"
CMD "git diff"            "auto-uses delta if configured"
CMD "git log -p"          "syntax-highlighted patch log"

SUB "rg — ripgrep"
CMD "rg <pattern>"        "search files recursively"
CMD "rg <pattern> -t py"  "search only Python files"
CMD "rg <pattern> -l"     "list matching files only"

SUB "fd — smart find"
CMD "fd <name>"           "find files by name (respects .gitignore)"
CMD "fd -e py"            "find by extension"
CMD "fd -t d <name>"      "find directories only"
echo

hr
echo -e "  ${DIM}Ctrl+p f to toggle floating  ·  Ctrl+s to scroll  ·  Ctrl+p x to close${R}"
hr
echo
}

_cheat_content
read -rsp "" 2>/dev/null || true
