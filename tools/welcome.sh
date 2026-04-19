#!/usr/bin/env bash
# FOB shell pane welcome — shows on brief launch

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
echo -e "${DIM}  shell pane  ·  forward operating base${R}"
echo

hr
echo -e "  ${B}TOOL STATUS${R}"
hr
chk lazygit  && ok lazygit  "git TUI"            || miss lazygit  "run: fob loadout"
chk fzf      && ok fzf      "fuzzy finder"       || miss fzf      "run: fob loadout"
(chk bat || command -v batcat &>/dev/null) \
             && ok bat      "syntax cat"         || miss bat      "run: fob loadout"
chk eza      && ok eza      "modern ls"          || miss eza      "run: fob loadout"
chk rg       && ok rg       "fast grep"          || miss rg       "run: fob loadout"
chk zoxide   && ok zoxide   "smart cd"           || miss zoxide   "run: fob loadout"
chk delta    && ok delta    "git diffs"          || miss delta    "run: fob loadout"
chk starship && ok starship "shell prompt"       || miss starship "run: fob loadout"
echo

hr
echo -e "  ${B}QUICK REFERENCE${R}"
hr
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "fob status"    "situation report"
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "fob resume"    "claude mission brief"
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "fob test"      "run project tests"
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "fob loadout"      "install / update dev tools"
printf "  ${CYN}%-18s${R} ${DIM}%s${R}\n" "fob cheat"     "open full cheatsheet"
echo

hr
echo -e "  ${B}ZELLIJ${R}  ${DIM}(prefix: Ctrl+a)${R}"
hr
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+a |"       "split pane vertical"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+a -"       "split pane horizontal"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+a z"       "zoom pane fullscreen"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+a h/j/k/l" "navigate panes"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+a d"       "detach session"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+a n"       "new window/tab"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+a w"       "window list"
printf "  ${YLW}%-22s${R} ${DIM}%s${R}\n" "Ctrl+a ?"       "all keybindings"
echo
hr
echo -e "  ${DIM}run ${CYN}fob cheat${DIM} to open the full floating reference${R}"
hr
echo

exec bash -l
