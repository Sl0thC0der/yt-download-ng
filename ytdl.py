#!/usr/bin/env python3
"""
YouTube Music Downloader NG - All-in-One Script
Complete unified interface for all download operations

Features:
- Auto-fix aria2c issues
- Smart retry logic
- Profile management
- Batch downloads
- Server health monitoring
"""

import os
import sys
import time
import subprocess
import psutil
import json
import shutil
import argparse
from pathlib import Path
from typing import Optional, List, Dict


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def log_info(message: str):
    """Print info message with color"""
    print(f'[\033[36mINFO\033[0m] {message}')

def log_success(message: str):
    """Print success message with color"""
    print(f'[\033[32mSUCCESS\033[0m] {message}')

def log_warn(message: str):
    """Print warning message with color"""
    print(f'[\033[33mWARN\033[0m] {message}')

def log_error(message: str):
    """Print error message with color"""
    print(f'[\033[31mERROR\033[0m] {message}')

def check_dependencies() -> Dict[str, bool]:
    """Check if all required dependencies are available"""
    deps = {
        'python': sys.executable is not None,
        'node': shutil.which('node') is not None,
        'ffmpeg': shutil.which('ffmpeg') is not None,
        'aria2c': shutil.which('aria2c') is not None,
    }
    return deps

def print_dependency_status():
    """Print status of all dependencies"""
    deps = check_dependencies()
    print('\n\033[36mDependency Status:\033[0m')
    for name, available in deps.items():
        status = '\033[32m✓\033[0m' if available else '\033[31m✗\033[0m'
        print(f'  {status} {name}')
    print()

# ============================================================================
# SERVER MANAGEMENT
# ============================================================================

def is_server_running():
    """Check if PO token server is already running"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] in ('node.exe', 'node'):
                cmdline = proc.info['cmdline']
                if cmdline and any('main.js' in cmd for cmd in cmdline):
                    return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def check_server_health():
    """Check if server is responding"""
    try:
        import requests
        response = requests.get('http://127.0.0.1:4416/ping', timeout=1)
        return response.status_code == 200
    except:
        return False


def start_server():
    """Start PO token server"""
    root_dir = Path(__file__).parent.absolute()
    server_path = root_dir / 'bgutil-pot-provider' / 'server' / 'build' / 'main.js'
    
    # Check if already running
    pid = is_server_running()
    if pid:
        if check_server_health():
            log_info(f'PO token server is already running (PID: {pid})')
            return 0
        else:
            log_warn('Found node process but server not responding, restarting...')
            try:
                psutil.Process(pid).terminate()
                time.sleep(1)
            except:
                pass
    
    # Check if server file exists
    if not server_path.exists():
        log_error(f'Server file not found at: {server_path}')
        log_info('Run: cd bgutil-pot-provider && npm install && npx tsc')
        return 1
    
    # Start server
    log_info('Starting PO token server...')
    
    try:
        # Start node process in background
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            process = subprocess.Popen(
                ['node', str(server_path)],
                cwd=str(root_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            )
        else:
            process = subprocess.Popen(
                ['nohup', 'node', str(server_path)],
                cwd=str(root_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp
            )
        
        time.sleep(2)
        
        if check_server_health():
            log_success(f'PO token server started successfully (PID: {process.pid})')
            return 0
        else:
            log_warn('Server started but not responding yet, may need a moment...')
            return 0
            
    except FileNotFoundError:
        log_error('Node.js not found. Please install Node.js.')
        log_info('Install with: winget install OpenJS.NodeJS')
        return 1
    except Exception as e:
        log_error(f'Failed to start server: {e}')
        return 1


# ============================================================================
# PROFILE MANAGEMENT
# ============================================================================

def get_available_profiles(root_dir):
    """Get list of available configuration profiles"""
    profiles = []
    config_dir = root_dir / 'config'
    
    for config_file in config_dir.glob('*.json'):
        profiles.append(config_file.stem)
    
    profiles_dir = config_dir / 'profiles'
    if profiles_dir.exists():
        for config_file in profiles_dir.glob('*.json'):
            profiles.append(f'profiles/{config_file.stem}')
    
    return sorted(profiles)


def list_profiles():
    """List all available profiles"""
    root_dir = Path(__file__).parent.absolute()
    profiles = get_available_profiles(root_dir)
    
    print('\n\033[36mAvailable Profiles:\033[0m')
    print('\n\033[33mMain Configs:\033[0m')
    for profile in profiles:
        if '/' not in profile:
            print(f'  \033[32m✓\033[0m {profile}')
    print('\n\033[33mAudiophile Profiles:\033[0m')
    for profile in profiles:
        if '/' in profile:
            print(f'  \033[32m✓\033[0m {profile}')
    print()
    return 0


# ============================================================================
# DOWNLOAD FUNCTIONS
# ============================================================================

def backup_config(config_path: Path) -> Optional[Path]:
    """Create backup of config file"""
    try:
        backup_dir = config_path.parent.parent / 'backups' / 'configs'
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f'{config_path.stem}_backup.json'
        shutil.copy2(config_path, backup_path)
        return backup_path
    except Exception as e:
        log_warn(f'Could not backup config: {e}')
        return None

def fix_config_if_needed(config_path: Path, create_backup: bool = True) -> bool:
    """Fix config file if it has issues (aria2c, template formats, etc.)"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        fixed = False
        fixes_applied = []
        
        # Create backup first if we're going to make changes
        if create_backup and (config.get('download_mode') == 'aria2c' or 
                             '{date:%Y}' in str(config.get('template_folder', ''))):
            backup_path = backup_config(config_path)
            if backup_path:
                log_info(f'Config backup created: {backup_path.name}')
        
        # Fix 1: Remove aria2c download mode
        if config.get('download_mode') == 'aria2c':
            config.pop('download_mode', None)
            fixes_applied.append('removed aria2c mode')
            fixed = True
        
        # Fix 2: Fix date template format (gytmdl doesn't support {date:%Y})
        if 'template_folder' in config:
            template = config['template_folder']
            # Replace {date:%Y} with {date} or just remove it
            if '{date:%Y}' in template:
                # Simply remove the date part since it causes errors
                new_template = template.replace(' [{date:%Y}]', '').replace('[{date:%Y}]', '')
                config['template_folder'] = new_template
                fixes_applied.append('fixed date template')
                fixed = True
        
        # Write back the fixed config
        if fixed:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            return True
    except Exception as e:
        log_warn(f'Could not fix config: {e}')
    
    return False

def download_single(url: str, profile: str = 'gytmdl', auto_fix: bool = True, max_retries: int = 2) -> int:
    """Download single URL with retry logic
    
    Args:
        url: YouTube Music URL to download
        profile: Config profile to use
        auto_fix: Auto-fix aria2c issues
        max_retries: Number of retry attempts on failure
    
    Returns:
        0 on success, non-zero on failure
    """
    root_dir = Path(__file__).parent.absolute()
    os.chdir(root_dir)
    
    # Start server
    log_info('Checking PO token server...')
    start_server()
    
    # Build config path
    config_path = root_dir / 'config' / f'{profile}.json'
    if not config_path.exists():
        log_error(f'Profile not found: {config_path}')
        print(f'\n\033[33mAvailable profiles:\033[0m')
        for p in get_available_profiles(root_dir):
            print(f'  \033[32m-\033[0m {p}')
        return 1
    
    # Auto-fix config if needed
    if auto_fix:
        if fix_config_if_needed(config_path):
            log_info('Auto-fixed config: removed aria2c mode (using default for better compatibility)')
    
    # Determine Python executable (venv or system)
    venv_python = root_dir / 'env' / 'Scripts' / 'python.exe'
    if not venv_python.exists():
        venv_python = root_dir / 'env' / 'bin' / 'python'
    
    # If no venv exists, use system Python (e.g., in container)
    if not venv_python.exists():
        # Check if gytmdl is available in system Python
        result = subprocess.run(
            [sys.executable, '-c', 'import gytmdl'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            venv_python = Path(sys.executable)
            log_info('Using system Python (container mode)')
        else:
            log_error('Virtual environment not found and gytmdl not installed')
            log_info('Run: python -m venv env')
            return 1
    
    log_success(f'Using profile: {profile}')
    log_info(f'Downloading: {url}')
    
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    
    # Retry logic
    for attempt in range(max_retries + 1):
        if attempt > 0:
            log_warn(f'Retry attempt {attempt}/{max_retries}...')
            time.sleep(2)  # Wait before retry
        
        result = subprocess.run(
            [str(venv_python), '-m', 'gytmdl', '--config-path', str(config_path), url],
            env=env
        )
        
        if result.returncode == 0:
            return 0
    
    log_error(f'Download failed after {max_retries + 1} attempts')
    return result.returncode


def download_batch(list_file: str, profile: str = 'gytmdl', continue_on_error: bool = True) -> int:
    """Batch download from URL list with progress tracking
    
    Args:
        list_file: Path to text file containing URLs
        profile: Config profile to use
        continue_on_error: Continue downloading even if some URLs fail
    
    Returns:
        0 if all successful, 1 if any failures
    """
    list_path = Path(list_file)
    
    if not list_path.exists():
        log_error(f'File not found: {list_file}')
        return 1
    
    # Start server once
    log_info('Starting batch download...')
    start_server()
    
    # Read URLs
    urls = []
    with open(list_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            urls.append((line_num, line))
    
    if not urls:
        log_warn(f'No URLs found in {list_file}')
        return 0
    
    total_urls = len(urls)
    success_count = 0
    fail_count = 0
    failed_urls = []
    
    log_info(f'Found {total_urls} URL(s) to download')
    print()
    
    # Process each URL
    for index, (line_num, url) in enumerate(urls, 1):
        print('\n' + '=' * 70)
        print(f'\033[33m[{index}/{total_urls}] Line {line_num}: {url[:60]}...\033[0m' if len(url) > 60 else f'\033[33m[{index}/{total_urls}] Line {line_num}: {url}\033[0m')
        print('=' * 70)
        
        try:
            result = download_single(url, profile)
            if result == 0:
                success_count += 1
                log_success(f'Downloaded: {url[:50]}...')
            else:
                fail_count += 1
                failed_urls.append((line_num, url))
                log_error(f'Failed to download: {url[:50]}...')
                if not continue_on_error:
                    break
        except KeyboardInterrupt:
            log_warn('Batch download interrupted by user')
            break
        except Exception as e:
            fail_count += 1
            failed_urls.append((line_num, url))
            log_error(f'Exception: {e}')
            if not continue_on_error:
                break
    
    # Summary
    print('\n' + '=' * 70)
    print('\033[36m╔════════════════════════════════════════════════════════════════╗\033[0m')
    print('\033[36m║              Batch Download Complete                           ║\033[0m')
    print('\033[36m╚════════════════════════════════════════════════════════════════╝\033[0m')
    print(f'\nTotal: {total_urls} | Success: \033[32m{success_count}\033[0m | Failed: \033[31m{fail_count}\033[0m')
    
    if failed_urls:
        print('\n\033[31mFailed URLs:\033[0m')
        for line_num, url in failed_urls:
            print(f'  Line {line_num}: {url}')
    
    print()
    return 0 if fail_count == 0 else 1


# ============================================================================
# HELP & MAIN
# ============================================================================

def show_help():
    """Display help message"""
    # Set UTF-8 encoding for Windows console
    import sys
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("""
\033[36m╔═══════════════════════════════════════════════════════════╗
║      YouTube Music Downloader NG - All-in-One Script    ║
╚═══════════════════════════════════════════════════════════╝\033[0m

\033[33mUsage:\033[0m
  python ytdl.py <command> [options]

\033[33mCommands:\033[0m
  \033[32mdownload\033[0m <url> [-p PROFILE]    Download single URL
  \033[32mbatch\033[0m <file> [-p PROFILE]       Download from URL list
  \033[32mserver\033[0m                         Start/check PO token server
  \033[32mprofiles\033[0m                       List available profiles
  \033[32mcheck\033[0m                          Check dependencies and system status
  \033[32mfix-all\033[0m                        Fix all profile configurations
  \033[32mhelp\033[0m                           Show this help message

\033[33mExamples:\033[0m
  # Check system dependencies
  python ytdl.py check

  # Download with default profile
  python ytdl.py download "https://music.youtube.com/playlist?list=..."

  # Download with audiophile profile
  python ytdl.py download "URL" -p profiles/audiophile-max

  # Batch download
  python ytdl.py batch urls.txt -p profiles/classical

  # List all profiles
  python ytdl.py profiles

\033[33mFeatures:\033[0m
  ✓ Auto-fix aria2c issues
  ✓ Smart retry logic (2 retries per URL)
  ✓ Config backup before modifications
  ✓ Enhanced error messages
  ✓ Progress tracking for batch downloads

\033[33mAvailable Profiles:\033[0m
  gytmdl                      - Default (AAC 128kbps)
  profiles/audiobook          - Audiobook optimized
  profiles/music-hq           - High quality music (Opus)
  profiles/audiophile-max     - Maximum quality
  profiles/critical-listening - Pure audio focus
  profiles/archive-lossless   - Long-term preservation
  profiles/vinyl-collection   - Vinyl-style organization
  profiles/classical          - Classical music optimized
  profiles/live-recordings    - Concert recordings
  profiles/mobile-optimized   - Portable devices
  profiles/reference-testing  - Audio analysis/testing

\033[33mFor detailed information:\033[0m
  See PROFILES-GUIDE.md and README.md
""")


def main():
    if len(sys.argv) < 2:
        show_help()
        return 0
    
    command = sys.argv[1].lower()
    
    if command in ['help', '-h', '--help', '?']:
        show_help()
        return 0
    
    elif command == 'download':
        if len(sys.argv) < 3:
            print('[\033[31mERROR\033[0m] URL required')
            print('Usage: python ytdl.py download <url> [-p PROFILE]')
            return 1
        
        # Parse arguments
        url = sys.argv[2]
        profile = 'gytmdl'
        
        if len(sys.argv) > 3 and sys.argv[3] in ['-p', '--profile']:
            if len(sys.argv) > 4:
                profile = sys.argv[4]
        
        return download_single(url, profile)
    
    elif command == 'batch':
        if len(sys.argv) < 3:
            print('[\033[31mERROR\033[0m] URL list file required')
            print('Usage: python ytdl.py batch <file> [-p PROFILE]')
            return 1
        
        # Parse arguments
        list_file = sys.argv[2]
        profile = 'gytmdl'
        
        if len(sys.argv) > 3 and sys.argv[3] in ['-p', '--profile']:
            if len(sys.argv) > 4:
                profile = sys.argv[4]
        
        return download_batch(list_file, profile)
    
    elif command == 'server':
        return start_server()
    
    elif command == 'profiles':
        return list_profiles()
    
    elif command == 'fix-all':
        log_info('Fixing all profile configurations...')
        root_dir = Path(__file__).parent.absolute()
        config_dir = root_dir / 'config'
        
        fixed_count = 0
        profiles_dir = config_dir / 'profiles'
        
        # Fix main configs
        for config_file in config_dir.glob('*.json'):
            if fix_config_if_needed(config_file, create_backup=True):
                log_success(f'Fixed: {config_file.name}')
                fixed_count += 1
        
        # Fix profile configs
        if profiles_dir.exists():
            for config_file in profiles_dir.glob('*.json'):
                if fix_config_if_needed(config_file, create_backup=True):
                    log_success(f'Fixed: profiles/{config_file.name}')
                    fixed_count += 1
        
        if fixed_count == 0:
            log_info('No fixes needed - all profiles are OK')
        else:
            log_success(f'Fixed {fixed_count} profile(s)')
        
        print()
        return 0
    
    elif command == 'check':
        print('\n\033[36m╔═══════════════════════════════════════════════════════════╗\033[0m')
        print('\033[36m║            System Dependency Check                     ║\033[0m')
        print('\033[36m╚═══════════════════════════════════════════════════════════╝\033[0m')
        print_dependency_status()
        
        # Check server status
        pid = is_server_running()
        if pid and check_server_health():
            log_success(f'PO token server running (PID: {pid})')
        else:
            log_warn('PO token server not running')
            log_info('Start with: python ytdl.py server')
        
        # Check venv
        root_dir = Path(__file__).parent.absolute()
        venv_python = root_dir / 'env' / 'Scripts' / 'python.exe'
        if not venv_python.exists():
            venv_python = root_dir / 'env' / 'bin' / 'python'
        
        if venv_python.exists():
            log_success('Virtual environment found')
        else:
            log_error('Virtual environment not found')
            log_info('Run: python -m venv env')
        
        # Check profile count
        profiles = get_available_profiles(root_dir)
        log_info(f'Found {len(profiles)} profile(s)')
        print()
        return 0
    
    else:
        log_error(f'Unknown command: {command}')
        print('Run "python ytdl.py help" for usage information')
        return 1


if __name__ == '__main__':
    sys.exit(main())
