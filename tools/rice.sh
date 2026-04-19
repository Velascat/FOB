#!/usr/bin/env bash
# rice.sh — terminal ricing guide & tool installer

R='\033[0m'; B='\033[1m'; DIM='\033[2m'
RED='\033[31m'; GRN='\033[32m'; YLW='\033[33m'; CYN='\033[36m'; MAG='\033[35m'

COLS="${COLUMNS:-80}"
hr()    { printf "${DIM}%*s${R}\n" "$COLS" '' | tr ' ' '─'; }
pause() { echo; read -rsp $'  \033[2mpress enter to continue...\033[0m'; echo; }
title() { echo; hr; echo -e "  ${B}${CYN}$1${R}"; hr; echo; }
note()  { echo -e "  ${DIM}▸ $1${R}"; }

banner() {
  echo -e "${MAG}${B}"
  cat <<'EOF'
  ██████╗ ██╗ ██████╗███████╗
  ██╔══██╗██║██╔════╝██╔════╝
  ██████╔╝██║██║     █████╗
  ██╔══██╗██║██║     ██╔══╝
  ██║  ██║██║╚██████╗███████╗
  ╚═╝  ╚═╝╚═╝ ╚═════╝╚══════╝
EOF
  echo -e "${DIM}  terminal ricing guide${R}"
  echo
}

# Tool table: "name|apt_pkg|check_cmd|description"
# check_cmd can be space-separated alternatives (e.g. "bat batcat")
TOOLS=(
  "fzf|fzf|fzf|Fuzzy finder — supercharges Ctrl+R, file & dir search"
  "bat|bat|bat batcat|Syntax-highlighted cat with line numbers"
  "eza|eza|eza|Modern ls — colors, icons, git status, tree view"
  "ripgrep|ripgrep|rg|Blazing fast grep — searches codebases instantly"
  "fd|fd-find|fd fdfind|Smarter find — simpler syntax, respects .gitignore"
  "zoxide|zoxide|zoxide|Smart cd — learns your dirs, jump with z"
  "delta|git-delta|delta|Beautiful git diffs with syntax highlighting"
  "lazygit|lazygit|lazygit|Full git TUI — stage, commit, diff, log visually"
  "btop|btop|btop|Beautiful system monitor — CPU/RAM/network/processes"
  "starship|starship|starship|Cross-shell prompt — fast, informative, customizable"
  "fastfetch|fastfetch|fastfetch|System info display — the classic flex"
)

# ── Helpers ───────────────────────────────────────────────────────────────────
tool_installed() {
  local alts="$1"
  for cmd in $alts; do
    command -v "$cmd" &>/dev/null && return 0
  done
  return 1
}

tool_check_cmd() {
  local alts="$1"
  for cmd in $alts; do
    command -v "$cmd" &>/dev/null && echo "$cmd" && return
  done
}

# ── Status ────────────────────────────────────────────────────────────────────
show_status() {
  title "TOOL STATUS"
  for entry in "${TOOLS[@]}"; do
    IFS='|' read -r name _pkg check_alts desc <<< "$entry"
    if tool_installed "$check_alts"; then
      printf "  ${GRN}✓${R} ${B}%-12s${R} ${DIM}%s${R}\n" "$name" "$desc"
    else
      printf "  ${DIM}✗ %-12s %s${R}\n" "$name" "$desc"
    fi
  done
  echo
}

# ── Install ───────────────────────────────────────────────────────────────────
install_starship() {
  echo -e "${CYN}▶ Installing starship via official installer...${R}"
  curl -sS https://starship.rs/install.sh | sh -s -- --yes
}

install_lazygit() {
  echo -e "${CYN}▶ Installing lazygit...${R}"
  local ver
  ver=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" \
    | grep '"tag_name"' | cut -d'"' -f4 | sed 's/v//')
  curl -Lo /tmp/lazygit.tar.gz \
    "https://github.com/jesseduffield/lazygit/releases/latest/download/lazygit_${ver}_Linux_x86_64.tar.gz"
  tar xf /tmp/lazygit.tar.gz -C /tmp lazygit
  sudo install /tmp/lazygit /usr/local/bin
  rm -f /tmp/lazygit.tar.gz /tmp/lazygit
}

install_eza() {
  echo -e "${CYN}▶ Installing eza from GitHub releases...${R}"
  local url="https://github.com/eza-community/eza/releases/latest/download/eza_x86_64-unknown-linux-musl.tar.gz"
  curl -Lo /tmp/eza.tar.gz "$url"
  tar xf /tmp/eza.tar.gz -C /tmp eza
  sudo install /tmp/eza /usr/local/bin/eza
  rm -f /tmp/eza.tar.gz /tmp/eza
}

install_delta() {
  echo -e "${CYN}▶ Installing git-delta from GitHub releases...${R}"
  local ver
  ver=$(curl -s "https://api.github.com/repos/dandavison/delta/releases/latest" \
    | grep '"tag_name"' | cut -d'"' -f4)
  curl -Lo /tmp/delta.deb \
    "https://github.com/dandavison/delta/releases/latest/download/git-delta_${ver}_amd64.deb"
  sudo dpkg -i /tmp/delta.deb
  rm -f /tmp/delta.deb
}

install_fastfetch() {
  echo -e "${CYN}▶ Installing fastfetch from GitHub releases...${R}"
  curl -Lo /tmp/fastfetch.deb \
    "https://github.com/fastfetch-cli/fastfetch/releases/latest/download/fastfetch-linux-amd64.deb"
  sudo dpkg -i /tmp/fastfetch.deb
  rm -f /tmp/fastfetch.deb
}

install_all_missing() {
  local apt_pkgs=()
  for entry in "${TOOLS[@]}"; do
    IFS='|' read -r name pkg check_alts _desc <<< "$entry"
    tool_installed "$check_alts" && continue
    case "$name" in
      starship)  install_starship ;;
      lazygit)   install_lazygit ;;
      eza)       install_eza ;;
      delta)     install_delta ;;
      fastfetch) install_fastfetch ;;
      *)         apt_pkgs+=("$pkg") ;;
    esac
  done
  if [[ ${#apt_pkgs[@]} -gt 0 ]]; then
    echo -e "${CYN}▶ apt install: ${apt_pkgs[*]}${R}"
    sudo apt-get update -q && sudo apt-get install -y "${apt_pkgs[@]}"
  fi
  echo
  echo -e "${GRN}✓ Done!${R}"
  note "bat may be installed as 'batcat' — the config below handles this."
  note "fd may be installed as 'fdfind' — the config below handles this."
  echo
}

# ── Shell config ──────────────────────────────────────────────────────────────
BASHRC_BLOCK='
# ── Rice ──────────────────────────────────────────────────────────────────────
# fzf — Ctrl+R history, Ctrl+T files, Alt+C dirs
command -v fzf &>/dev/null && eval "$(fzf --bash)"

# zoxide — smart cd (use z instead of cd)
command -v zoxide &>/dev/null && eval "$(zoxide init bash)"

# starship prompt
command -v starship &>/dev/null && eval "$(starship init bash)"

# bat / batcat — syntax-highlighted cat
if command -v batcat &>/dev/null; then
  alias cat="batcat --pager=never"
  alias bat="batcat"
elif command -v bat &>/dev/null; then
  alias cat="bat --pager=never"
fi

# eza — modern ls
if command -v eza &>/dev/null; then
  alias ls="eza --icons --group-directories-first"
  alias ll="eza -la --icons --git --group-directories-first"
  alias lt="eza --tree --icons -L 3"
fi

# ripgrep
command -v rg &>/dev/null && alias grep="rg"

# fd / fdfind
command -v fdfind &>/dev/null && alias fd="fdfind"

# lazygit
command -v lazygit &>/dev/null && alias lg="lazygit"
'

show_shell_config() {
  title "SHELL CONFIG"
  echo -e "  Add these to ${CYN}~/.bashrc${R} for the full experience:\n"
  echo -e "${DIM}$BASHRC_BLOCK${R}"
  read -rp $'  write to ~/.bashrc? [y/N] ' yn
  if [[ "${yn,,}" == "y" ]]; then
    if grep -qF '# ── Rice' "$HOME/.bashrc" 2>/dev/null; then
      echo -e "${YLW}⚠  Rice block already in ~/.bashrc${R}"
    else
      printf '%s\n' "$BASHRC_BLOCK" >> "$HOME/.bashrc"
      echo -e "${GRN}✓ Written to ~/.bashrc${R}"
      echo -e "${DIM}  Run: source ~/.bashrc${R}"
    fi
  fi
  echo
  pause
  main_menu
}

# ── Delta git config ──────────────────────────────────────────────────────────
setup_delta() {
  echo
  if ! command -v delta &>/dev/null; then
    echo -e "${YLW}⚠  delta not installed yet${R}"
    read -rp $'  install it now? [y/N] ' yn
    if [[ "${yn,,}" == "y" ]]; then
      sudo apt-get install -y git-delta
    else
      pause; main_menu; return
    fi
  fi
  git config --global core.pager delta
  git config --global interactive.diffFilter "delta --color-only"
  git config --global delta.navigate true
  git config --global delta.side-by-side true
  git config --global merge.conflictstyle diff3
  echo -e "${GRN}✓ git configured to use delta${R}"
  note "git diff, git log -p, git show will now look beautiful."
  echo
  pause
  main_menu
}

# ── Nerd Font hint ────────────────────────────────────────────────────────────
show_fonts() {
  title "NERD FONTS"
  echo -e "  Icons in eza/starship require a Nerd Font in your terminal.\n"
  echo -e "  ${B}Option 1: Download manually${R}"
  echo -e "  ${CYN}https://www.nerdfonts.com/font-downloads${R}"
  note "Recommended: JetBrainsMono, FiraCode, or CascadiaCode Nerd Font"
  echo
  echo -e "  ${B}Option 2: Install via script${R}"
  echo -e "  ${GRN}mkdir -p ~/.local/share/fonts${R}"
  echo -e "  ${GRN}cd ~/.local/share/fonts${R}"
  echo -e "  ${GRN}curl -fLo \"JetBrainsMono.zip\" https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip${R}"
  echo -e "  ${GRN}unzip JetBrainsMono.zip && fc-cache -fv${R}"
  echo
  note "Then set your terminal font to 'JetBrainsMono Nerd Font'."
  echo
  pause
  main_menu
}

# ── Main menu ─────────────────────────────────────────────────────────────────
main_menu() {
  clear
  banner
  show_status
  echo -e "  ${B}What do you want?${R}"
  echo
  echo -e "  ${CYN}1${R}  Install all missing tools"
  echo -e "  ${CYN}2${R}  Write shell config to ~/.bashrc"
  echo -e "  ${CYN}3${R}  Configure git to use delta (pretty diffs)"
  echo -e "  ${CYN}4${R}  Nerd Font setup (for icons)"
  echo -e "  ${CYN}q${R}  Quit"
  echo
  read -rp $'  choice: ' choice
  case "$choice" in
    1) install_all_missing; pause; main_menu ;;
    2) show_shell_config ;;
    3) setup_delta ;;
    4) show_fonts ;;
    q|Q) echo; exit 0 ;;
    *) main_menu ;;
  esac
}

# ── Entry ─────────────────────────────────────────────────────────────────────
case "${1:-menu}" in
  status)  banner; show_status ;;
  config)  banner; show_shell_config ;;
  install) banner; install_all_missing ;;
  *)       main_menu ;;
esac
