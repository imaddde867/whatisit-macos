# Pilot label review (30 rows)

Mark each row: **OK** = command correctly does what the request asks on macOS and is safe to run; **BAD** = wrong, risky or only coincidentally works; **ALT** = works but a different valid approach (still OK to train on). Reply as `id: OK/BAD/ALT`.

| id | request | teacher command | verdict |
|---|---|---|---|
| r00061 | Can you show the architecture of the Python interpreter on this Mac? | `python3 -c 'import platform; print(platform.machine())'` |  |
| r00028 | Turn a comma-separated single line in values.txt into one value per line. | `tr ',' '\n' < values.txt` |  |
| r00037 | Find files ending in .log except debug.log under sessions/. | `find sessions/ -type f -name '*.log' ! -name 'debug.log'` |  |
| r00096 | Please show the readable text of the com.example.caption attribute on illustration.png. | `xattr -p com.example.caption illustration.png` |  |
| r00002 | Show the hardware cache-line size. | `sysctl -n hw.cachelinesize` |  |
| r00003 | I want to find files in tree/ with the same device and inode as linked.txt. | `find tree/ -samefile linked.txt` |  |
| r00082 | can u show the reflog for HEAD in project/ | `git -C project/ reflog show HEAD` |  |
| r00055 | validate the stapled notarization ticket attached to Utility.app | `xcrun stapler validate Utility.app` |  |
| r00005 | Can you show only APFS filesystems in the mounted-filesystem usage table? | `df -h -t apfs` |  |
| r00033 | Display system-extension status without altering extensions. | `systemextensionsctl list` |  |
| r00057 | Show thread count for PID 4200 on macOS. | `ps -o thcount= -p 4200` |  |
| r00088 | Report inode usage on /Volumes/WORK. | `df -i /Volumes/WORK` |  |
| r00052 | extract only notes.txt from backup.tar | `tar -xf backup.tar notes.txt` |  |
| r00016 | Show the friendly computer name registered with macOS, without changing it. | `scutil --get ComputerName` |  |
| r00064 | show the default macOS SDK version | `xcrun --sdk macosx --show-sdk-version` |  |
| r00087 | I need to remove write access for others from every file inside scratch/. | `find scratch/ -type f -exec chmod o-w {} +` |  |
| r00038 | Give deploy.sh mode 0750 while leaving its directory alone. | `chmod 0750 deploy.sh` |  |
| r00092 | Split ~/Library/Logs/MyApp/trace.log into chunks of 500 lines. | `split -l 500 ~/Library/Logs/MyApp/trace.log ~/Library/Logs/MyApp/trace.log.chunk` |  |
| r00069 | Could you write a binary-format copy of project/Config.plist to project/Config-binary.plist? | `plutil -convert binary1 -o project/Config-binary.plist project/Config.plist` |  |
| r00074 | read LSUIElement boolean from MyApp.app Info.plist plese | `plutil -extract LSUIElement raw -o - MyApp.app/Contents/Info.plist` |  |
| r00041 | Please verify the self-signature of request.csr. | `openssl req -in request.csr -noout -verify` |  |
| r00027 | Could you request https://example.org/ through my local HTTP proxy at 127.0.0.1:8888? | `curl -x http://127.0.0.1:8888 https://example.org/` |  |
| r00059 | Print Spotlight's indexed title and description fields for guide.pdf. | `mdls -name kMDItemTitle -name kMDItemDescription guide.pdf` |  |
| r00001 | Check whether standard output is connected to a terminal. | `[ -t 1 ] && echo yes \|\| echo no` |  |
| r00093 | Find empty directories anywhere under project/. | `find project/ -type d -empty` |  |
| r00051 | Please show the Spotlight-indexed page width and height of report.pdf. | `mdls -name kMDItemPageWidth -name kMDItemPageHeight report.pdf` |  |
| r00012 | Preserve the original symlinks while recursively copying source/ to duplicate/. | `cp -R -P source/ duplicate/` |  |
| r00030 | Can you print the current timestamp including the local timezone offset, with no spaces? | `date +%Y-%m-%dT%H:%M:%S%z` |  |
| r00006 | I need Spotlight's complete attribute dump for manual.pdf, including attributes with null values. | `mdls -all manual.pdf` |  |
| r00095 | I want to inspect the automation permission description in ScriptTool.app | `/usr/libexec/PlistBuddy -c "Print :NSAppleEventsUsageDescription" ScriptTool.app/Contents/Info.plist` |  |
