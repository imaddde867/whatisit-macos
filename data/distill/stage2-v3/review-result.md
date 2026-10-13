# Data v3 model review

Model review, not human review. Seed 314159; 60 of 64 recovered
command rows, proportional category strata with largest-remainder allocation.
Only OK counts as correct. OK: 52; debatable: 1;
wrong: 7. Precision: 86.7%; Wilson 95% interval:
[75.8%, 93.1%]. This estimates synthetic recovered-label precision,
not deployment accuracy. Stratification is nearly proportional; Wilson is a
descriptive binomial interval, not a design-weighted survey interval.

Gate: **PASS** (at most 9 non-OK rows).
Each row was judged for request correctness, stock-macOS flags and safety.
Local man pages and scratch-only read checks are documented in the verdict notes.
No generated writes, deletes, sudo or network changes were executed.
No evaluation scores were used to select these labels.

| id | category | verdict | model review notes |
|---|---|---|---|
| r00024 | search | OK | man mdfind: -onlyin and literal author/type conjunction; stock indexed PDF metadata. Read-only; no user index queried. |
| r00030 | system-info | OK | man date: ISO-style local time and %z offset without spaces. Read-only; dynamic clock not used for label selection. |
| r00046 | power-and-hardware | OK | man system_profiler: -xml with SPPowerDataType limits output to the power report. Read-only. |
| r00127 | macos-tools | OK | man osascript/grep: clipboard info reports data flavors; PNGf check reports PNG presence. Read-only; real clipboard not accessed. |
| r00159 | security-and-apps | OK | man fdesetup/grep: status text FileVault is On distinguishes enabled encryption. Read-only; actual disk state not queried. |
| r00167 | network | OK | man networksetup: -getdnsservers reads the explicitly requested Ethernet service. Service must exist; no network change. |
| r00172 | network | OK | man printf/nc: sends hello to the explicitly owned loopback UDP listener with a timeout. It tests sending, not receipt. Not executed. |
| r00203 | archives-and-media | OK | man cp: -R recursive, -p preserves metadata/ACLs, -v prints copied paths; source trailing slash preserves the requested contents semantics. Requested destination write; not executed. |
| r00307 | network | OK | man networksetup: -getproxybypassdomains for Wi-Fi is the documented read query. No network change; not executed. |
| r00314 | files-and-folders | OK | man find plus scratch fixtures: mindepth/maxdepth 1 with type d lists only direct subdirectories. Read-only. |
| r00320 | files-and-folders | wrong | man cp explicitly says -H/-L/-P are ignored without -R and symlinks are followed. -pP copies the target, not symlink metadata. No generated copy executed. |
| r00326 | disk-and-storage | OK | man diskutil/grep: info for the named disk includes Solid State; case-insensitive line filtering displays it. Read-only; actual disk not queried. |
| r00336 | system-info | OK | man date plus scratch execution returned 2025-06-15T11:30:00Z. -j prevents setting the clock; -u renders UTC. |
| r00342 | processes-and-ports | OK | man ps: ruid is real UID and uid is effective UID; -p limits the named process. Read-only; real process information not queried. |
| r00364 | macos-tools | OK | man plutil: -p reads the specified launch-agent plist; HOME/tilde are path aliases. Read-only; real home files not opened. |
| r00396 | security-and-apps | OK | stock openssl req -help confirms -in/-noout/-text; decodes a CSR without submitting or modifying it. Not executed on user files. |
| r00475 | git-and-dev | wrong | xcodebuild -list/-project is an Xcode developer command, but full Xcode is not stock macOS. On this CLT host its help fails because Xcode is required; no stock man page. No project executed. |
| r00553 | text-processing | OK | man grep plus scratch ISO timestamps: ERE/o extraction returned +03:00, -0500, Z. Read-only. |
| r00724 | search | OK | man mdfind and local metadata schema: kMDItemUserTags exact Draft query under the named scope. Assumes indexed tags. Real Documents not queried. |
| r00740 | git-and-dev | wrong | Scratch Git fixture with a commit after the last checkout proves HEAD@{1} returns the prior reflog event, not necessarily HEAD before that checkout. Read-only generated query. |
| r00896 | files-and-folders | OK | Stock BSD stat scratch check returned 644 for a 0644 fixture using %A. Numeric permissions are correct; read-only. |
| r00980 | files-and-folders | OK | man mdls: -name selects kMDItemFinderComment, -raw prints its value. Read-only; real file metadata not opened. |
| r00984 | system-info | OK | man date plus scratch execution returned 2028-02-29; -j parses March 1 then -v-1d handles the leap year. No clock change. |
| r01082 | disk-and-storage | OK | man du: -s/-h summary with -I mask ignores .DS_Store names; read-only fixture check completed. |
| r01088 | disk-and-storage | OK | man iostat: -d selects disks, -w 1 and -c 5 sample the named disk once per second for five displays. Read-only; actual device not sampled. |
| r01095 | search | OK | man grep plus scratch fixture: -r/-i/-w restricts matches to whole-word draft regardless of case. Read-only. |
| r01134 | files-and-folders | OK | man ditto: copies directory contents while preserving ACLs and extended attributes by default. Requested destination write; not executed. |
| r01168 | files-and-folders | OK | man find/sort plus scratch fixture: direct directory paths only, lexically sorted. Read-only. |
| r01209 | text-processing | OK | man grep plus scratch fixture: extracts IPv4-looking dotted quads, intentionally not a numeric-validity validator. Read-only. |
| r01219 | archives-and-media | OK | afinfo usage and grep man: audio information includes estimated duration; filter retains the duration line. Read-only; no real audio opened. |
| r01235 | disk-and-storage | OK | man du: -I node_modules skips matching directories, -s/-h summarizes. Read-only fixture check completed. |
| r01263 | security-and-apps | OK | socketfilterfw help documents --getappblocked for a named application. Reads the application firewall rule; no policy change and not executed. |
| r01310 | system-info | OK | man system_profiler: -xml SPHardwareDataType selects only hardware overview; redirection writes the explicitly requested hardware.plist. Generated write not executed. |
| r01334 | archives-and-media | OK | man hdiutil: attach with -nobrowse suppresses Finder browsing; default is noautoopen. Requested mount, not destructive; not executed. |
| r01476 | system-info | OK | man date: -u and explicit UTC Z suffix produce an ISO timestamp. Read-only. |
| r01502 | power-and-hardware | OK | man system_profiler: -json and the two named report types produce USB/Thunderbolt JSON only. Read-only. |
| r01563 | network | OK | man curl: -H sets User-Agent: LocalTest and the URL is the explicitly requested loopback HTTP endpoint. No request was executed. |
| r01564 | search | OK | man find plus scratch fixture: mindepth/maxdepth 3 and type/name select only third-level cache directories. Read-only. |
| r01642 | macos-tools | OK | man defaults: reads Terminal Default Window Settings; Basic is the built-in fallback when that preference is absent. Read-only; real preferences not queried. |
| r01658 | search | OK | man mdfind and mdimport schema: image content-type tree plus kMDItemISOSpeed >=800 in the named scope. Read-only; real index not queried. |
| r01674 | files-and-folders | OK | man test plus scratch fixture: both read and write permission predicates must succeed before yes. Read-only. |
| r01690 | text-processing | OK | man PlistBuddy plus scratch plist: Print :CFBundlePackageType returned APPL. Read-only. |
| r01811 | git-and-dev | OK | man grep plus scratch fixture: -n/-E finds and numbers opening, separator and closing conflict markers. Read-only. |
| r01824 | processes-and-ports | OK | man time: /usr/bin/time -l reports elapsed time and maximum resident set size for the explicitly requested executable script. Script safety depends on user-supplied contents; no script executed. |
| r01848 | search | wrong | Apple Spotlight query syntax requires CFDate numeric seconds or $time.iso for dates. Bare 2024-01-01 does not encode the requested cutoff. Scratch query had no indexed results and cannot validate semantics. |
| r01851 | network | OK | man networksetup: -getinfo for the named Ethernet service displays its addressing configuration, including DHCP/manual indication. No network change; not executed. |
| r01911 | files-and-folders | OK | man stat: default lstat reads the alias file itself and %SB formats its birth time. Read-only fixture check completed. |
| r01958 | archives-and-media | wrong | kMDItemVideoFrameRate is absent from the stock mdimport attribute schema and Apple video metadata keys. mdls cannot supply an MP4 frame rate through that invented attribute. Read-only command not executed. |
| r02031 | network | OK | man system_profiler: SPNetworkDataType with -json reads the network hardware report. No network change; not executed. |
| r02059 | system-info | OK | man date: -v+1d adjusts the displayed local calendar date; %A prints weekday. No clock setting option. |
| r02102 | search | debatable | Nil comparison for missing Spotlight authors is not established by Apple query syntax documentation; an empty scratch index gives no semantic evidence. Also no document-type predicate. Read-only and safe, but not counted correct. |
| r02271 | text-processing | OK | man grep plus scratch fixture: -F literal FAILURE with -C 2 emits the matching record and two surrounding lines. Read-only. |
| r02276 | files-and-folders | wrong | Stock BSD stat rejects the mutually exclusive -l and -f output modes; scratch command exits 1 before reporting symlink birth time. Both cluster forms fail the same way. |
| r02284 | network | wrong | networksetup -getinfo takes a named network service; Global IPv6 is SystemConfiguration global state, not a stock service name. This does not query global IPv6 state. No network change. |
| r02338 | files-and-folders | OK | man stat and scratch fixture: %i is the BSD inode/file ID. Read-only. |
| r02393 | disk-and-storage | OK | man stat and scratch fixture: %l/%b report hard-link count and allocated blocks. Read-only. |
| r02397 | disk-and-storage | OK | man du: -L follows symlinks and -s/-h summarizes the named directory. Read-only fixture check completed. |
| r02417 | search | OK | Apple Spotlight wildcard syntax and mdimport schema: kMDItemWhereFroms equals *example.com* matches a containing URL in the named scope. Read-only; no real index queried. |
| r02442 | system-info | OK | man stat: %Su prints the owner of /dev/console, the usual current console-login account. Loginwindow/root state is a normal boundary case. Read-only; actual owner not queried. |
| r02485 | search | OK | man find and scratch fixture: four explicit [0-9] classes match exactly four digits and no trailing suffix. Read-only. |
