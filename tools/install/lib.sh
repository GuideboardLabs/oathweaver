#!/usr/bin/env bash

# Shared installer helpers for Oathweaver shell installers.

ow_verify_sha256() {
    local file_path="$1"
    local expected="$2"
    if [[ -z "$file_path" || -z "$expected" ]]; then
        return 1
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        echo "$expected  $file_path" | sha256sum -c - >/dev/null
        return $?
    fi
    if command -v shasum >/dev/null 2>&1; then
        local actual
        actual="$(shasum -a 256 "$file_path" | awk '{print $1}')"
        [[ "${actual,,}" == "${expected,,}" ]]
        return $?
    fi
    return 2
}

ow_install_ollama_script() {
    local install_url="$1"
    local expected_sha="$2"
    local tmp_script
    tmp_script="$(mktemp)"
    curl -fsSL "$install_url" -o "$tmp_script"
    if [[ -n "$expected_sha" ]]; then
        ow_verify_sha256 "$tmp_script" "$expected_sha"
        local verify_rc=$?
        if [[ $verify_rc -eq 1 ]]; then
            rm -f "$tmp_script"
            return 1
        fi
    fi
    sh "$tmp_script"
    local rc=$?
    rm -f "$tmp_script"
    return $rc
}

ow_install_python_requirements() {
    local python_bin="$1"
    local requirements_path="$2"
    local pip_quiet="${3:-0}"
    local quiet_flag=()
    if [[ "$pip_quiet" == "1" ]]; then
        quiet_flag=(-q)
    fi
    if [[ "$requirements_path" == *"requirements.lock" ]]; then
        if grep -q -- "--hash=" "$requirements_path"; then
            "$python_bin" -m pip install "${quiet_flag[@]}" --require-hashes -r "$requirements_path"
            return $?
        fi
        if [[ "${OATHWEAVER_ALLOW_UNHASHED_LOCK:-0}" != "1" ]]; then
            echo "[ERROR] requirements.lock is missing hashes." >&2
            echo "[ERROR] Regenerate it with: ./tools/install/regenerate_hashed_lock.sh" >&2
            return 1
        fi
    fi
    "$python_bin" -m pip install "${quiet_flag[@]}" -r "$requirements_path"
}
