#!/bin/bash

# ///// Python Environment ///// #
BUILD_ENV="utility-cockpit"
PYTHON_VERSION="3.12.3"
PROJECT_FOLDER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REQUIREMENTS_FILE="$PROJECT_FOLDER/requirements.txt"

# ///// Utility Functions ///// #

function log_location() {
  echo -e "\n# //////////////////////////////////////////////////////////// Script Location"
  echo -e "\n$PROJECT_FOLDER"
}

function script_usage() {
  echo -e "\n# //////////////////////////////////////////////////////////// Script Usage"
  echo -e "\nbash $0 [-c]"
  echo -e "\nOptions:\n  [-c] (Optional) Removes Virtual Environment After Script Execution"
}

function list_contents() {
  echo -e "\nCurrently Inside:::\n$(pwd)\n"
  echo -e "Contents:::\n"
  ls -alrt
}

# ///// Virtual Environment Setup ///// #

function linux_setup_pyenv() {
  eval "$(pyenv init --path)"
  eval "$(pyenv init -)"
  eval "$(pyenv virtualenv-init -)"
  PYENV_AVAILABLE=$(command -v pyenv &>/dev/null && echo true || echo false)
}

function activate_environment() {
  echo -e "\n# ////////// Activating Python Environment"
  echo -e "\npyenv activate $BUILD_ENV"
  pyenv activate "$BUILD_ENV"
  list_contents
}

function create_environment() {
  echo -e "\n# ////////// Creating Python Environment"
  echo -e "\npyenv virtualenv $PYTHON_VERSION $BUILD_ENV"
  pyenv virtualenv "$PYTHON_VERSION" "$BUILD_ENV"
  activate_environment

  echo -e "\n# ////////// Installing Python Tools"
  python -m pip install --upgrade pip wheel

  echo -e "\n# ////////// Installing Requirements"
  python -m pip install -r "$REQUIREMENTS_FILE"
  python -m pip list -v
}

function check_environment() {
  echo -e "\n# //////////////////////////////////////////////////////////// Checking Python Environment"
  linux_setup_pyenv

  if [[ "$PYENV_AVAILABLE" == true ]] && pyenv virtualenvs | grep -q "$BUILD_ENV"; then
    echo -e "\n# ////////// FOUND: $BUILD_ENV"
    activate_environment
  else
    echo -e "\n# ////////// NOT FOUND: $BUILD_ENV"
    create_environment
  fi
}

function cleanup() {
  echo -e "\n# //////////////////////////////////////////////////////////// Cleaning Up Environment"
  echo "pyenv virtualenv-delete -f $BUILD_ENV"
  pyenv virtualenv-delete -f "$BUILD_ENV"
}

# ///// Main Runner ///// #

function run_script() {
  echo -e "\n# //////////////////////////////////////////////////////////// Starting Bootstrap"

  check_environment

  cd "$PROJECT_FOLDER"

  echo -e "\n# //////////////////////////////////////////////////////////// Verifying Cockpit"
  export PYTHONPATH="$PROJECT_FOLDER/src:${PYTHONPATH:-}"
  python3 -m cockpit.cli doctor

  echo -e "\n# //////////////////////////////////////////////////////////// Bootstrap Complete"
  echo -e "\nEnvironment ready. Run:  fob help\n"
}

# ///// Script Entry Point ///// #

script_usage
log_location

cd "$PROJECT_FOLDER"

while getopts 'c' OPTION; do
  case "$OPTION" in
    c)
      run_script
      cleanup
      exit
      ;;
    ?)
      script_usage
      exit 1
      ;;
  esac
done
shift "$((OPTIND -1))"

run_script
