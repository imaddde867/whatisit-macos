"""Score catalog + local fallback (the CLI path) on fixed requests: pass / rejected (lint or no answer) / wrong, plus p50 latency.

Run with the upstream venv python so `whatisit` imports:
    PYTHONPATH=src ~/.local/pipx/venvs/whatisit/bin/python tools/eval_fallback.py
Accepted-answer regexes are deliberately loose: they check the right tool/flags, not exact text.
"""

import platform
import re
import shutil
import statistics
import sys
import time

from whatisit_macos.engine import suggest
from whatisit_macos.local_recovery import suggest_local

# (request, regex the command must match)
CASES = [
    ("show disk usage of each folder in the current directory, one level deep, sorted by size", r"\bdu\b.*(-d\s*1|-s)"),
    ("which process is listening on port 8080", r"\blsof\b.*:8080"),
    ("list all listening TCP ports", r"\blsof\b.*LISTEN|netstat.*LISTEN"),
    ("replace foo with bar in config.txt in place", r"sed -i ''"),
    ("show the modification time of notes.txt", r"stat -f|ls -l"),
    ("print yesterday's date as YYYY-MM-DD", r"date -v-1d"),
    ("show free memory", r"vm_stat|memory_pressure|top -l"),
    ("flush the DNS cache", r"dscacheutil -flushcache|killall -HUP mDNSResponder"),
    ("show my local IP address", r"ipconfig getifaddr|ifconfig"),
    ("show the number of CPU cores", r"sysctl.*(ncpu|cpu\.core_count|physicalcpu)"),
    ("copy the contents of id_rsa.pub to the clipboard", r"pbcopy"),
    ("show the top 10 processes by memory usage", r"top .*-o (mem|rsize)|ps .*-m"),
    ("find files modified in the last 24 hours", r"find .*-mtime -1|find .*-mmin -1440"),
    ("search for lines matching the regex \\d{3}-\\d{4} in log.txt", r"grep -E|egrep"),
    ("kill the process using port 3000", r"lsof.*:3000.*(kill|xargs)|kill.*lsof.*:3000"),
    ("show battery cycle count", r"ioreg.*(AppleSmartBattery|CycleCount)|system_profiler SPPowerDataType"),
    ("show assertions preventing sleep", r"pmset -g assertions"),
    ("find files bigger than 100MB in this folder", r"find .*-size \+100M"),
    ("compress the logs directory into logs.tar.gz", r"tar .*-?c.*z.*logs\.tar\.gz"),
    ("show the last 50 lines of the system log", r"\blog (show|stream)\b|tail .*system\.log"),
    ("list installed homebrew packages", r"brew (list|ls)"),
    ("show wifi network name", r"^(?!.*\$\{).*(networksetup -getairportnetwork|ipconfig getsummary|airport -I)"),
    ("show the size of each file in the current directory in human readable form sorted largest first", r"ls -.*S|du -.*h.*sort"),
    ("convert all png files in this folder to jpg", r"^(?!.*echo).*(sips|magick|convert)"),
    ("show the 5 largest files under ~/Downloads", r"find .*Downloads|du .*Downloads|ls .*-S"),
    ("count lines in all python files recursively", r"find .*\.py.*wc -l|wc -l"),
    ("list USB devices", r"system_profiler SPUSBDataType|ioreg -p IOUSB"),
    ("show hardware model and serial number", r"system_profiler SPHardwareDataType|ioreg.*(serial|model)|sysctl.*hw\.model"),
    ("keep the mac awake for an hour", r"caffeinate .*3600"),
    ("show open files of the Safari process", r"lsof .*Safari|pgrep.*Safari.*lsof"),
    ("compute the sha256 checksum of disk.iso", r"shasum -a 256|openssl.*sha256"),
    ("eject the external disk named Backup", r"diskutil eject .*Backup|hdiutil detach .*Backup"),
    ("list all disks and partitions", r"diskutil list"),
    ("remove the quarantine attribute from MyApp.app", r"xattr .*-d.*com\.apple\.quarantine|xattr -cr"),
    ("show hidden files in Finder", r"defaults write com\.apple\.finder AppleShowAllFiles"),
    ("list network hardware ports", r"networksetup -listallhardwareports"),
    ("show error messages from the unified log in the last 5 minutes", r"log show .*--last 5m|log show .*error"),
    ("show which processes use the most CPU right now", r"top .*-o cpu|ps .*-r"),
    ("show the current wifi interface IP address", r"ipconfig getifaddr en0|ifconfig en0"),
    ("list files in the current directory sorted by modification time, newest first", r"ls -.*t"),
    ("show the md5 hash of file.txt", r"\bmd5\b|md5sum"),
    ("resize photo.jpg to 800 pixels wide", r"sips .*(-Z|--resampleWidth) 800"),
    ("show the path of the frontmost Xcode developer directory", r"xcode-select -p|xcode-select --print-path"),
    ("show total RAM installed", r"sysctl.*hw\.memsize|system_profiler SPHardwareDataType"),
]


def main() -> int:
    passed = rejected = wrong = 0
    times = []
    for request, accept in CASES:
        start = time.perf_counter()
        answer = suggest(request, system=platform.system(), which=shutil.which)
        if answer['status'] in ('unsupported', 'ambiguous'):  # same routing as the CLI
            answer = suggest_local(request)
        times.append(time.perf_counter() - start)
        command = answer['command']
        if command is None:
            rejected += 1
            label, shown = 'REJECT', answer['reason']
        elif re.search(accept, command):
            passed += 1
            label, shown = 'pass', command
        else:
            wrong += 1
            label, shown = 'WRONG', command
        print(f'{label:7} {request}\n        {shown}')
    print(f'\npass {passed}/{len(CASES)}  rejected {rejected}  wrong {wrong}  '
          f'p50 {statistics.median(times):.2f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
