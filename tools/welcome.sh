#!/usr/bin/env bash
# OperatorConsole shell pane welcome — shows on launch

R='\033[0m'; B='\033[1m'; DIM='\033[2m'
GRN='\033[32m'; YLW='\033[33m'; CYN='\033[36m'; RED='\033[31m'
COLS="${COLUMNS:-80}"

hr() { printf "${DIM}%*s${R}\n" "$COLS" '' | tr ' ' '─'; }
ok()   { printf "  ${GRN}✓${R} ${B}%-12s${R} ${DIM}%s${R}\n" "$1" "$2"; }
miss() { printf "  ${YLW}✗${R} ${DIM}%-12s %s${R}\n" "$1" "$2"; }
chk()  { command -v "$1" &>/dev/null; }

clear
echo -e "${CYN}${B}"
cat << 'BANNER'
  ███████╗ ██████╗ ██████╗
  ██╔════╝██╔═══██╗██╔══██╗
  █████╗  ██║   ██║██████╔╝
  ██╔══╝  ██║   ██║██╔══██╗
  ██║     ╚██████╔╝██████╔╝
  ╚═╝      ╚═════╝ ╚═════╝
BANNER
echo -e "${DIM}  shell pane  ·  Operator Console${R}"
echo

hr
echo -e "  ${B}TOOL STATUS${R}"
hr
chk lazygit  && ok lazygit  "git TUI"            || miss lazygit  "run: console loadout"
chk fzf      && ok fzf      "fuzzy finder"       || miss fzf      "run: console loadout"
(chk bat || command -v batcat &>/dev/null) \
             && ok bat      "syntax cat"         || miss bat      "run: console loadout"
chk eza      && ok eza      "modern ls"          || miss eza      "run: console loadout"
chk rg       && ok rg       "fast grep"          || miss rg       "run: console loadout"
chk zoxide   && ok zoxide   "smart cd"           || miss zoxide   "run: console loadout"
chk delta    && ok delta    "git diffs"          || miss delta    "run: console loadout"
chk starship && ok starship "shell prompt"       || miss starship "run: console loadout"
echo

hr
echo -e "  ${B}QUICK REFERENCE${R}"
hr
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "console status"    "situation report"
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "console resume"    "claude startup context"
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "console test"      "run project tests"
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "console loadout"   "install / update dev tools"
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "console cheat"     "open full cheatsheet"
echo

hr
echo -e "  ${B}ZELLIJ${R}"
hr
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+p ↑↓←→"    "navigate panes"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+p z"        "zoom pane fullscreen"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+p f"        "toggle floating panes"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+p x"        "close pane"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+t t"        "new tab"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+t ←→"       "switch tab"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+o d"        "detach session"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+h"          "all keybindings"
echo
hr
echo -e "  ${DIM}run ${CYN}console cheat${DIM} to open the full floating reference${R}"
hr
echo

exec bash -l
