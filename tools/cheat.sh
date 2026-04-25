#!/usr/bin/env bash
# cheat.sh — OperatorConsole quick reference, runs in a floating pane

R='\033[0m'; B='\033[1m'; DIM='\033[2m'
BCYN='\033[96m'; BYLW='\033[93m'; BGRN='\033[92m'; WHT='\033[97m'
COLS="${COLUMNS:-90}"

hr()  { printf "${BCYN}${DIM}%*s${R}\n" "$COLS" '' | tr ' ' '─'; }
sec() { echo; hr; printf "  ${B}${WHT}%s${R}\n" "$1"; hr; }
K()   { printf "  ${BYLW}${B}%-26s${R}  ${BGRN}%s${R}\n" "$1" "$2"; }
CMD() { printf "  ${BCYN}%-26s${R}  ${DIM}%s${R}\n" "$1" "$2"; }
SUB() { echo -e "\n  ${B}${WHT}$1${R}"; }

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

sec "OperatorConsole WORKSPACE"
CMD "console [open] [repo]"        "launch — auto-selects current repo"
CMD "console multi"                "multi-select picker — open several repos"
CMD "console restore [--show]"     "re-open last saved session group"
CMD "console rewatch [profiles…]"  "restart git watcher for this tab's profile"
CMD "console attach"               "re-attach to running console session"
CMD "console kill"                 "terminate session + all panes"
echo
CMD "console status [--all]"       "session, layout, branch, .console/ state"
CMD "console resume"               "print Claude startup context"
CMD "console init [repo]"          "initialize .console/ context files"
CMD "console test / console audit"     "run project tests / audit"
CMD "console doctor"               "check all dependencies"
CMD "console loadout"              "install / update dev tools"
echo

sec "RESET & LAYOUT"
CMD "console reset"                "full reset — session + layout + state"
CMD "console reset --session"      "kill session only"
CMD "console reset --layout"       "clear saved layout only"
CMD "console reset --state"        "delete .console/ context files only"
CMD "console layout save/load"     "save or restore workspace layout"
echo

sec "ZELLIJ"

SUB "Panes"
K "Ctrl+p ↑↓←→"      "navigate panes"
K "Ctrl+p n / d / r"  "new / split down / split right"
K "Ctrl+p z"          "zoom pane fullscreen"
K "Ctrl+p f"          "toggle floating panes"
K "Ctrl+p x"          "close pane"

SUB "Tabs"
K "Ctrl+t t"          "new tab"
K "Ctrl+t ←→ / 1-9"  "switch tab"
K "Ctrl+t r"          "rename tab"
K "Ctrl+t x"          "close tab"

SUB "Sessions & Scroll"
K "Ctrl+o d"          "detach (session keeps running)"
K "Ctrl+o w"          "session manager"
K "Ctrl+s ↑↓ / j k"  "scroll"
K "Ctrl+s e"          "edit scrollback in \$EDITOR"
K "Ctrl+h"            "help — all keybindings"
echo

hr
echo -e "  ${DIM}Ctrl+p f to toggle floating  ·  Ctrl+p x to close${R}"
hr
echo

read -rsp "" 2>/dev/null || true
