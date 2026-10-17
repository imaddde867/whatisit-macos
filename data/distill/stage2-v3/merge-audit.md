# Equivalence merge audit (model review)

Every recovered multi-string cluster is listed below, including excluded rows.

## r00024 (3 votes)

spotlight find PDFs with author Sample Editor under paper-tests/

```json
[
  "mdfind -onlyin paper-tests 'kMDItemAuthors == \"Sample Editor\" && kMDItemContentType == \"com.adobe.pdf\"'",
  "mdfind -onlyin paper-tests/ 'kMDItemAuthors == \"Sample Editor\" && kMDItemContentType == \"com.adobe.pdf\"'"
]
```

## r00030 (3 votes)

Can you print the current timestamp including the local timezone offset, with no spaces?

```json
[
  "date '+%Y-%m-%dT%H:%M:%S%z'",
  "date +%Y-%m-%dT%H:%M:%S%z"
]
```

## r00046 (4 votes)

Display the power-source hardware report as a property list.

```json
[
  "system_profiler -xml SPPowerDataType",
  "system_profiler SPPowerDataType -xml"
]
```

## r00127 (3 votes)

show whether the clipboard contains a PNG image

```json
[
  "osascript -e 'clipboard info' | grep -q 'PNGf' && echo 'yes' || echo 'no'",
  "osascript -e 'clipboard info' | grep -q 'PNGf' && echo yes || echo no"
]
```

## r00159 (3 votes)

check whether FileVault reports encryption enabled

```json
[
  "fdesetup status | grep -q \"FileVault is On\" && echo enabled || echo disabled",
  "fdesetup status | grep -q 'FileVault is On' && echo enabled || echo disabled"
]
```

## r00167 (4 votes)

show ethernet service dns addreses on mac

```json
[
  "networksetup -getdnsservers \"Ethernet\"",
  "networksetup -getdnsservers 'Ethernet'",
  "networksetup -getdnsservers Ethernet"
]
```

## r00172 (3 votes)

I'd like to test whether UDP packets can be sent to my own test listener at 127.0.0.1:9999 using the text hello.

```json
[
  "printf 'hello' | nc -u -w 1 127.0.0.1 9999",
  "printf hello | nc -u -w 1 127.0.0.1 9999"
]
```

## r00203 (3 votes)

copy project/ to backup/ with metadata preserved and print each path as it is copied

```json
[
  "cp -Rp -v project/ backup/",
  "cp -Rpv project/ backup/"
]
```

## r00307 (4 votes)

List Wi-Fi proxy bypass domains.

```json
[
  "networksetup -getproxybypassdomains \"Wi-Fi\"",
  "networksetup -getproxybypassdomains Wi-Fi"
]
```

## r00320 (4 votes)

Copy symlink metadata from link-source to link-copy on macOS.

```json
[
  "cp -P -p link-source link-copy",
  "cp -Pp link-source link-copy",
  "cp -pP link-source link-copy"
]
```

## r00326 (3 votes)

Can you identify whether disk4 is solid-state using its macOS disk information?

```json
[
  "diskutil info disk4 | grep -i \"Solid State\"",
  "diskutil info disk4 | grep -i 'Solid State'"
]
```

## r00336 (3 votes)

Convert 2025-06-15T14:30:00+0300 to a UTC timestamp using the BSD date utility.

```json
[
  "date -j -u -f \"%Y-%m-%dT%H:%M:%S%z\" \"2025-06-15T14:30:00+0300\" \"+%Y-%m-%dT%H:%M:%SZ\"",
  "date -u -j -f \"%Y-%m-%dT%H:%M:%S%z\" \"2025-06-15T14:30:00+0300\" \"+%Y-%m-%dT%H:%M:%SZ\"",
  "date -u -j -f '%Y-%m-%dT%H:%M:%S%z' '2025-06-15T14:30:00+0300' '+%Y-%m-%dT%H:%M:%SZ'"
]
```

## r00342 (3 votes)

Display the real and effective user IDs of process 4200 as separate columns.

```json
[
  "ps -o ruid,uid -p 4200",
  "ps -p 4200 -o ruid,uid"
]
```

## r00364 (3 votes)

show the launch agent definition at ~/Library/LaunchAgents/com.example.MyApp.plist

```json
[
  "plutil -p \"$HOME/Library/LaunchAgents/com.example.MyApp.plist\"",
  "plutil -p ~/Library/LaunchAgents/com.example.MyApp.plist"
]
```

## r00396 (4 votes)

decode teh contents of request.csr without submitting it

```json
[
  "openssl req -in request.csr -noout -text",
  "openssl req -in request.csr -text -noout"
]
```

## r00475 (4 votes)

Could you show the schemes in MyApp.xcodeproj?

```json
[
  "xcodebuild -list -project MyApp.xcodeproj",
  "xcodebuild -project MyApp.xcodeproj -list"
]
```

## r00553 (3 votes)

Extract the timezone offsets from ISO timestamps in mac-log-times.txt.

```json
[
  "grep -Eo '([+-][0-9]{2}:?[0-9]{2}|Z)' mac-log-times.txt",
  "grep -oE '([+-][0-9]{2}:?[0-9]{2}|Z)' mac-log-times.txt"
]
```

## r00724 (3 votes)

Ask Spotlight for items with the Finder tag Draft under ~/Documents.

```json
[
  "mdfind 'kMDItemUserTags == \"Draft\"' -onlyin ~/Documents",
  "mdfind -onlyin ~/Documents 'kMDItemUserTags == \"Draft\"'"
]
```

## r00740 (3 votes)

can u show where HEAD pointed before the last checkout in project/

```json
[
  "git -C project rev-parse 'HEAD@{1}'",
  "git -C project/ rev-parse 'HEAD@{1}'"
]
```

## r00896 (3 votes)

show permissions on .env.example numercially

```json
[
  "stat -f \"%A\" .env.example",
  "stat -f '%A' .env.example"
]
```

## r00980 (3 votes)

Show notes.md's Finder comment.

```json
[
  "mdls -name kMDItemFinderComment -raw notes.md",
  "mdls -raw -name kMDItemFinderComment notes.md"
]
```

## r00984 (3 votes)

Can you tell me the last calendar date of February 2028?

```json
[
  "date -j -v-1d -f \"%Y-%m-%d\" \"2028-03-01\" +%Y-%m-%d",
  "date -j -v-1d -f '%Y-%m-%d' '2028-03-01' '+%Y-%m-%d'"
]
```

## r01082 (3 votes)

Measure project/ excluding files named .DS_Store.

```json
[
  "du -sh -I '.DS_Store' project/",
  "du -sh -I .DS_Store project/"
]
```

## r01088 (3 votes)

Watch disk4 I/O once per second for five samples.

```json
[
  "iostat -d -w 1 -c 5 disk4",
  "iostat -d disk4 -w 1 -c 5"
]
```

## r01095 (4 votes)

Please search prose/ for whole-word draft matches while ignoring capitalization.

```json
[
  "grep -riw \"draft\" prose/",
  "grep -riw draft prose/",
  "grep -rwi draft prose/"
]
```

## r01209 (3 votes)

Extract all IPv4-looking addresses from access.log.

```json
[
  "grep -Eo '([0-9]{1,3}\\.){3}[0-9]{1,3}' access.log",
  "grep -oE '([0-9]{1,3}\\.){3}[0-9]{1,3}' access.log"
]
```

## r01219 (3 votes)

could u show the duration of recording.wav

```json
[
  "afinfo recording.wav | grep -i 'duration'",
  "afinfo recording.wav | grep -i duration"
]
```

## r01235 (3 votes)

Can you measure project/ without counting anything in directories named node_modules?

```json
[
  "du -sh -I 'node_modules' project/",
  "du -sh -I node_modules project/"
]
```

## r01263 (4 votes)

inspect teh application firewall policy for /System/Applications/Preview.app

```json
[
  "/usr/libexec/ApplicationFirewall/socketfilterfw --getappblocked \"/System/Applications/Preview.app\"",
  "/usr/libexec/ApplicationFirewall/socketfilterfw --getappblocked '/System/Applications/Preview.app'",
  "/usr/libexec/ApplicationFirewall/socketfilterfw --getappblocked /System/Applications/Preview.app"
]
```

## r01310 (4 votes)

Save the hardware overview to hardware.plist as XML, excluding other report categories.

```json
[
  "system_profiler -xml SPHardwareDataType > hardware.plist",
  "system_profiler SPHardwareDataType -xml > hardware.plist"
]
```

## r01334 (4 votes)

Please mount backup.dmg without opening Finder.

```json
[
  "hdiutil attach -nobrowse backup.dmg",
  "hdiutil attach backup.dmg -nobrowse"
]
```

## r01476 (5 votes)

Print the current time in UTC as an ISO 8601 timestamp.

```json
[
  "date -u '+%Y-%m-%dT%H:%M:%SZ'",
  "date -u +\"%Y-%m-%dT%H:%M:%SZ\"",
  "date -u +%Y-%m-%dT%H:%M:%SZ"
]
```

## r01495 (3 votes)

Find indexed audio items whose channel count is two inside audio-tests/.

```json
[
  "mdfind -onlyin audio-tests 'kMDItemAudioNumberOfChannels == 2'",
  "mdfind -onlyin audio-tests/ 'kMDItemAudioNumberOfChannels == 2'"
]
```

## r01502 (3 votes)

I'd like a JSON report containing Thunderbolt and USB device information.

```json
[
  "system_profiler -json SPUSBDataType SPThunderboltDataType",
  "system_profiler SPUSBDataType SPThunderboltDataType -json"
]
```

## r01517 (3 votes)

is en1 marked active in its interface details

```json
[
  "ifconfig en1 2>/dev/null | grep -q \"status: active\" && echo yes || echo no",
  "ifconfig en1 2>/dev/null | grep -q 'status: active' && echo yes || echo no"
]
```

## r01563 (3 votes)

get http://localhost:4000/ with a User-Agent of LocalTest

```json
[
  "curl -H \"User-Agent: LocalTest\" http://localhost:4000/",
  "curl -H 'User-Agent: LocalTest' http://localhost:4000/"
]
```

## r01564 (3 votes)

find directories named cache only at depth three in fixtures/

```json
[
  "find fixtures -mindepth 3 -maxdepth 3 -type d -name 'cache'",
  "find fixtures -mindepth 3 -maxdepth 3 -type d -name cache"
]
```

## r01642 (4 votes)

Could you show the Terminal app's default profile name?

```json
[
  "defaults read com.apple.Terminal \"Default Window Settings\" 2>/dev/null || echo \"Basic\"",
  "defaults read com.apple.Terminal \"Default Window Settings\" 2>/dev/null || echo Basic"
]
```

## r01658 (3 votes)

Spotlight-find images with ISO speed at least 800 in photo-tests/.

```json
[
  "mdfind -onlyin photo-tests 'kMDItemContentTypeTree == \"public.image\" && kMDItemISOSpeed >= 800'",
  "mdfind -onlyin photo-tests/ 'kMDItemContentTypeTree == \"public.image\" && kMDItemISOSpeed >= 800'"
]
```

## r01674 (3 votes)

is sample.txt readable and writable by me right now

```json
[
  "test -r sample.txt && test -w sample.txt && echo \"yes\" || echo \"no\"",
  "test -r sample.txt && test -w sample.txt && echo yes || echo no"
]
```

## r01690 (3 votes)

print CFBundlePackageType from MyApp.app Info.plist plz

```json
[
  "/usr/libexec/PlistBuddy -c \"Print :CFBundlePackageType\" MyApp.app/Contents/Info.plist",
  "/usr/libexec/PlistBuddy -c 'Print :CFBundlePackageType' MyApp.app/Contents/Info.plist"
]
```

## r01811 (3 votes)

Can you show conflict markers remaining in notes.txt in project/?

```json
[
  "grep -n -E '^(<<<<<<<|=======|>>>>>>>)' project/notes.txt",
  "grep -nE '^(<<<<<<<|=======|>>>>>>>)' project/notes.txt"
]
```

## r01824 (3 votes)

Can you run project/check.sh and show how long it took along with its peak memory usage on macOS?

```json
[
  "/usr/bin/time -l ./project/check.sh",
  "/usr/bin/time -l project/check.sh"
]
```

## r01848 (3 votes)

Find indexed files last opened before 2024-01-01 under review/.

```json
[
  "mdfind -onlyin review 'kMDItemLastUsedDate < 2024-01-01'",
  "mdfind -onlyin review/ \"kMDItemLastUsedDate < 2024-01-01\"",
  "mdfind -onlyin review/ 'kMDItemLastUsedDate < 2024-01-01'"
]
```

## r01851 (3 votes)

Can you inspect whether Ethernet is configured with DHCP or a manual address?

```json
[
  "networksetup -getinfo \"Ethernet\"",
  "networksetup -getinfo Ethernet"
]
```

## r01911 (4 votes)

show finder creation date for alias Project.alias itself plz

```json
[
  "stat -f \"%SB\" \"Project.alias\"",
  "stat -f \"%SB\" Project.alias",
  "stat -f '%SB' Project.alias"
]
```

## r01958 (3 votes)

show the frame rate of movie.mp4

```json
[
  "mdls -name kMDItemVideoFrameRate -raw movie.mp4",
  "mdls -raw -name kMDItemVideoFrameRate movie.mp4"
]
```

## r02031 (3 votes)

Display the network-related hardware report as JSON using the macOS system profiler.

```json
[
  "system_profiler -json SPNetworkDataType",
  "system_profiler SPNetworkDataType -json"
]
```

## r02059 (4 votes)

Please print tomorrow's local date followed by the weekday name.

```json
[
  "date -v+1d \"+%Y-%m-%d %A\"",
  "date -v+1d '+%Y-%m-%d %A'"
]
```

## r02102 (3 votes)

Please find indexed documents whose author field is missing inside document-tests/.

```json
[
  "mdfind -onlyin document-tests 'kMDItemAuthors == nil'",
  "mdfind -onlyin document-tests/ 'kMDItemAuthors == nil'"
]
```

## r02163 (3 votes)

What calendar date is ninety days after 2025-01-15?

```json
[
  "date -j -v+90d -f \"%Y-%m-%d\" \"2025-01-15\" \"+%Y-%m-%d\"",
  "date -j -v+90d -f \"%Y-%m-%d\" \"2025-01-15\" +%Y-%m-%d"
]
```

## r02271 (4 votes)

Print records containing literal FAILURE with two surrounding lines from errors.txt.

```json
[
  "grep -C 2 -F 'FAILURE' errors.txt",
  "grep -F -C 2 'FAILURE' errors.txt",
  "grep -F -C 2 FAILURE errors.txt"
]
```

## r02276 (3 votes)

Report the macOS birth time of the symlink current itself.

```json
[
  "stat -f '%SB' -l current",
  "stat -l -f \"%SB\" current"
]
```

## r02284 (3 votes)

I'd like to see the macOS network state for the global IPv6 service.

```json
[
  "networksetup -getinfo \"Global IPv6\"",
  "networksetup -getinfo 'Global IPv6'"
]
```

## r02338 (4 votes)

Show report.pdf's file ID using BSD stat.

```json
[
  "stat -f \"%i\" report.pdf",
  "stat -f %i report.pdf",
  "stat -f '%i' report.pdf"
]
```

## r02393 (4 votes)

Report the number of hard links and allocated blocks for data.bin.

```json
[
  "stat -f \"%l %b\" data.bin",
  "stat -f '%l %b' data.bin"
]
```

## r02397 (4 votes)

Measure project/ while following symbolic links.

```json
[
  "du -Lsh project/",
  "du -sh -L project/",
  "du -shL project/"
]
```

## r02417 (3 votes)

Find indexed files whose where-from URL contains example.com in download-tests/.

```json
[
  "mdfind -onlyin download-tests 'kMDItemWhereFroms == \"*example.com*\"'",
  "mdfind -onlyin download-tests/ 'kMDItemWhereFroms == \"*example.com*\"'"
]
```

## r02442 (3 votes)

who is logged into the console right now on mac

```json
[
  "stat -f \"%Su\" /dev/console",
  "stat -f '%Su' /dev/console"
]
```

## r02473 (3 votes)

I want to compare the creation dates of original.txt and copy.txt on macOS.

```json
[
  "stat -f \"%B %N\" original.txt copy.txt | sort -n",
  "stat -f '%B %N' original.txt copy.txt | sort -n"
]
```

Model merge review: read all 60 clusters and 131 distinct strings. No remaining meaning-changing pair found. Prior parser defects and their conservative fixes are documented in protocol.md; this conclusion concerns merge equivalence, not request correctness.
