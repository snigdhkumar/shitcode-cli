"""Automated version detection and Git-based update manager for ShitCode CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Optional
import urllib.request

from ui.theme import BOLD, DIM, GREEN, RED, RESET, YELLOW

ROOT_DIR = Path(__file__).resolve().parent.parent
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/snigdhkumar/shitcode-cli/main/version.json"


def load_client_version(root_dir: Optional[Path] = None) -> str:
    """Load client version from version.json or fallback to 1.3.0."""
    base_dir = root_dir or ROOT_DIR
    try:
        v_file = base_dir / "version.json"
        if v_file.is_file():
            with open(v_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return str(data.get("version", "1.3.0")).strip()
    except Exception:
        pass
    return "1.3.0"


CLIENT_VERSION = load_client_version()
PRODUCTION_GATEWAY_URL = "wss://api.shitcode.in/ws/client"


def parse_semver(ver_str: str) -> tuple[int, ...]:
    """Parse semver string into a comparable tuple of integers."""
    nums = re.findall(r"\d+", str(ver_str))
    return tuple(int(n) for n in nums) if nums else (0,)


def is_newer_version(remote_ver: str, current_ver: str) -> bool:
    """Check if the remote version is strictly greater than the current version."""
    try:
        return parse_semver(remote_ver) > parse_semver(current_ver)
    except Exception:
        return False


def check_for_updates_sync(current_version: Optional[str] = None) -> Optional[str]:
    """Fetch remote version with short timeout. Returns newer version string or None."""
    cur_ver = current_version or load_client_version()
    try:
        req = urllib.request.Request(
            UPDATE_CHECK_URL,
            headers={"User-Agent": f"ShitCode-CLI/{cur_ver}"}
        )
        with urllib.request.urlopen(req, timeout=1.8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                remote_ver = str(data.get("version", "")).strip()
                if remote_ver and is_newer_version(remote_ver, cur_ver):
                    return remote_ver
    except Exception:
        pass
    return None


def execute_update_routine(root_dir: Optional[Path] = None, skip_prompt: bool = False) -> bool:
    """Perform Git-based update of ShitCode CLI with safety checks and fallback."""
    base_dir = root_dir or ROOT_DIR
    git_bin = shutil.which("git")
    is_git_dir = (base_dir / ".git").is_dir()

    if not git_bin or not is_git_dir:
        current_loc = str(base_dir.resolve())
        print(f"\n{RED}[!] Git was not found on this system or this client was not installed via Git clone.{RESET}")
        print(f"{RED}    Please download the latest client from: https://shitcode.in/shitcode.zip{RESET}")
        print(f"{RED}    and extract (overwrite) into: {current_loc}{RESET}")
        print(f"    {DIM}Note: Your saved 'config.json' and custom 'skills/' will remain intact.{RESET}\n")
        return False

    if not skip_prompt:
        try:
            choice = input(f"\n{BOLD}{YELLOW}[?] Are you sure you want to update to the latest CLI version? [y/N]: {RESET}").strip().lower()
            if choice not in ("y", "yes"):
                print(f"  {DIM}[*] Update cancelled.{RESET}\n")
                return False
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {DIM}[*] Update cancelled.{RESET}\n")
            return False

    print(f"\n{BOLD}[*] Starting ShitCode CLI update...{RESET}")
    print(f"[*] Step 1/3: Fetching latest updates from remote repository...")

    # Preserve all existing .env files in skills/ so user API keys are never overwritten
    skills_dir = base_dir / "skills"
    existing_skill_envs: dict[Path, str] = {}
    if skills_dir.is_dir():
        for env_path in skills_dir.glob("**/.env*"):
            if env_path.is_file():
                try:
                    existing_skill_envs[env_path.resolve()] = env_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

    try:
        res = subprocess.run(
            [git_bin, "fetch", "origin", "main"],
            cwd=str(base_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            print(f"{RED}[!] Git fetch failed: {res.stderr.strip()}{RESET}\n")
            return False
    except Exception as e:
        print(f"{RED}[!] Git fetch error: {e}{RESET}\n")
        return False

    # If any tracked .env files have local user modifications, temporarily clean them so git pull --ff-only never aborts
    modified_tracked_envs = []
    try:
        status_res = subprocess.run([git_bin, "status", "--porcelain"], cwd=str(base_dir), capture_output=True, text=True, check=False)
        if status_res.returncode == 0:
            for line in status_res.stdout.splitlines():
                if "skills/" in line and ".env" in line:
                    file_part = line.strip().split()[-1]
                    modified_tracked_envs.append(file_part)
                    subprocess.run([git_bin, "checkout", "--", file_part], cwd=str(base_dir), capture_output=True, check=False)
    except Exception:
        pass

    print(f"[*] Step 2/3: Pulling latest changes into local client...")
    try:
        res = subprocess.run(
            [git_bin, "pull", "--ff-only", "origin", "main"],
            cwd=str(base_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            # If pull failed, restore user's files immediately
            for env_path_resolved, saved_content in existing_skill_envs.items():
                Path(env_path_resolved).write_text(saved_content, encoding="utf-8")
            print(f"{RED}[!] Git pull failed: {res.stderr.strip()}{RESET}")
            print(f"{RED}    If you have local changes, please commit or stash them before updating.{RESET}\n")
            return False
    except Exception as e:
        for env_path_resolved, saved_content in existing_skill_envs.items():
            Path(env_path_resolved).write_text(saved_content, encoding="utf-8")
        print(f"{RED}[!] Git pull error: {e}{RESET}\n")
        return False

    # Restore existing .env files (Never Overwrite rule) while keeping any newly downloaded .env files (Download if Missing rule)
    restored_count = 0
    for env_path_resolved, saved_content in existing_skill_envs.items():
        env_path = Path(env_path_resolved)
        try:
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(saved_content, encoding="utf-8")
            restored_count += 1
        except Exception as e:
            print(f"{YELLOW}[!] Notice: Could not restore {env_path.name}: {e}{RESET}")

    if restored_count > 0:
        print(f"  {DIM}[✓] Protected {restored_count} custom skill configuration (.env) file(s) from overwrite.{RESET}")

    print(f"[*] Step 3/3: Verifying and installing required dependencies...")
    try:
        req_file = base_dir / "requirements.txt"
        if req_file.exists():
            res = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)],
                cwd=str(base_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                print(f"{YELLOW}[!] Notice: Dependency update returned non-zero ({res.stderr.strip()}){RESET}")
    except Exception as e:
        print(f"{YELLOW}[!] Notice: Dependency update check skipped ({e}){RESET}")

    new_ver = load_client_version(base_dir)
    print(f"\n{GREEN}[+] ShitCode CLI successfully updated to v{new_ver}!{RESET}")
    print(f"[*] Please restart the client to apply changes.\n")
    return True
