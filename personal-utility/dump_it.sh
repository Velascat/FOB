#!/bin/bash

# === Config ===
repo_root="${1:-.}"
utility_folder="personal-utility"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="$script_dir/repo_dump"
chunk_base="$output_dir/repo_chunk"
max_chunk_lines=500

# Only include files with these extensions
allowed_extensions=("py" "md" "toml" "yml" "yaml" "txt")

# Internal state
chunk_number=1
solo_file_number=1
current_chunk_lines=0
current_chunk_file="${chunk_base}_${chunk_number}.txt"

# Rebuild output folder
rm -rf "$output_dir"
mkdir -p "$output_dir"

# === Helpers ===

write_chunk_header() {
    local file="$1"
    {
        echo -e "\n===== REPO STRUCTURE =====\n"
        command -v tree &>/dev/null && tree "$repo_root" -I '$utility_folder' || echo "(tree not installed)"
        echo -e "\n===== FILE CONTENTS =====\n"
    } >> "$file"
}

start_new_chunk() {
    ((chunk_number++))
    current_chunk_file="${chunk_base}_${chunk_number}.txt"
    > "$current_chunk_file"
    write_chunk_header "$current_chunk_file"
    current_chunk_lines=$(wc -l < "$current_chunk_file")
}

dump_big_file() {
    local file_path="$1"
    local relative_path="${file_path#$repo_root/}"
    local solo_file="${chunk_base}_BIGBOI_${solo_file_number}.txt"

    {
        echo -e "\n===== SOLO FILE DUMP =====\n"
        echo "========================================"
        echo "File: $relative_path"
        echo "========================================"
        cat "$file_path"
        echo
    } > "$solo_file"

    echo "🔥 $relative_path is a chonker (${file_lines} lines). Dumped to: $solo_file"
    ((solo_file_number++))
}

append_to_chunk() {
    local file_path="$1"
    local relative_path="${file_path#$repo_root/}"
    local file_lines
    file_lines=$(wc -l < "$file_path")

    if (( current_chunk_lines + file_lines > max_chunk_lines )); then
        start_new_chunk
    fi

    {
        echo "========================================"
        echo "File: $relative_path"
        echo "========================================"
        cat "$file_path"
        echo
    } >> "$current_chunk_file"

    ((current_chunk_lines += file_lines))
}

# === Start ===
> "$current_chunk_file"
write_chunk_header "$current_chunk_file"
current_chunk_lines=$(wc -l < "$current_chunk_file")

# === File Walker ===
find "$repo_root" -type f ! -path "$repo_root/$utility_folder/*" -print0 | while IFS= read -r -d '' file; do
    extension="${file##*.}"

    if [[ " ${allowed_extensions[*]} " == *" $extension "* ]]; then
        file_lines=$(wc -l < "$file")

        if (( file_lines + 10 > max_chunk_lines )); then
            dump_big_file "$file"
        else
            append_to_chunk "$file"
        fi
    fi
done

echo "✅ Done. Dumps are in '$output_dir'. No recursion traps, no namespace nightmares."
