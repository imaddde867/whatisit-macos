# Runtime LoRA: eight-seed A/B experiment

## Pre-registered decision rules

**Definitions:**
- **"Correct":** pass + abstain-ok, pooled over dev (61) + everyday (80) = 141.
- **"Seed mean / SD":** across the 8 seeds of one arm, each evaluated as the shipped Q4 + its runtime adapter.
- **"Per-case majority":** a case counts correct for an arm if at least 5 of its 8 seeds are correct.
- **"McNemar":** an exact two-sided binomial test on discordant cases, per-case majority vs default.
- **"Empty-on-answerable":** answerable cases (non-null accept) with `no_command_kind == empty_output`, averaged over seeds.
- **"Accepted-wrong":** label `wrong`, averaged over seeds.

**Rules:**

| # | Condition | Conclusion |
|---|---|---|
| R1 | A's seed mean ≥ default + 8, A's per-case majority McNemar p < 0.05, and A's mean accepted-wrong ≤ default + 2 | The runtime-LoRA gain is real on these 141 cases |
| R2 | B's seed SD ≤ ½ of A's, B's mean empty-on-answerable ≤ 5, and B's seed mean ≥ A's seed mean − 2 | Reducing empty targets is the stability fix |
| R3 | A's mean gain < 5 and McNemar p > 0.2 | Seed 42's 82 was a lucky draw. Recommend stopping tuning of this recipe (next options: verifier-selected labels with a re-aimed corpus, or retrieval / teacher fallback) |
| R4 | Any arm's mean sampled server RSS with adapter > default + 64 MiB, or p50 latency > default + 0.05 s | That arm fails the deployment budget, whatever its score |

None of these is a ship decision; shipping and serving changes are the user's call.

## Setup registered before trained-run evaluation

Branch `exp/runtime-lora-8seed`, from `data/v3-relabel` at
`967435938bd6a788b92bb91b69366097f2ea3330`. Arms A and B, seeds 1–8.
Unchanged rank 8 / alpha 160 / scale 20, last 16 layers, seven projection
modules, batch 1, AdamW lr 1e-5, one epoch, grouped validation fraction 0.05.

A: 1,149 rows (902 commands / 247 empty), grouped train 1,092 / validation 57;
steps 1,092. SHA-256
`c8f9661db1cadf79d81c58f0fd8f0628ad3461c61c0a5f97c6b20f195ec06550`.
B: 985 rows (902 commands / 83 empty, 8.426%), grouped train 936 / validation 49;
steps 936. Seeded subsample `random.Random(20261014)`; original bytes/order.
B has fewer optimizer steps and a different grouped validation partition; these
are confounds in attributing stability to the empty-target proportion alone.
B data hash is in `data/distill/stage2-v3-abstain8/manifest.json`.

Source/shipped base SHA-256:
`6f8a17a11129a31074c944f4c2602453fafd9de43bdaeb1630a8f511ec820f71`.
Tokenizer Qwen/Qwen2.5-Coder-1.5B-Instruct revision
`2e1fd397ee46e1388853d2af2c993145b0f1098a`; local transformers 4.57.1.
All 985 B rows pass chat_tokens; maximum 243 tokens. File hashes are in
`runtime-lora-8seed/reports/tokenizer-preflight.json`.
Host environment verified: torch 2.14.1+cu130, transformers 5.19.0,
peft 0.21.0, gguf 0.19.0; idle RTX 5090, CUDA 13.0, llama.cpp b11565.

Step-1 default sanity: exact equality of all 61 dev and 80 everyday labels with
`docs/stage2-arm-labels.json`; correct 26 + 42 = 68, accepted-wrong 40.
Stock PATH `/usr/bin:/bin:/usr/sbin:/sbin`, existing Mac server, shipped Q4.
No trained-run evaluation has occurred at registration.

Analysis conventions fixed now: sample SD (n−1), bootstrap 10,000 case resamples
with random.Random(20261014), percentile CI. Bootstrap samples a case with all
its eight seed outcomes, preserving the paired default. Unstable-case ordering:
closest to four correct seeds first, then case ID; report separately by arm.
Memory is sampled every 0.1 s on default and seed 1 of each arm, per requested
workload. Report sample mean and peak; seed-1 memory alone cannot estimate an
across-eight-seed mean. Compare each split's rounded eval p50 to default.

## Results

Default: **68/141 correct**, 40 accepted-wrong. All saved default labels match exactly.

| Arm | Mean ± sample SD | Min–max | Majority / 141 | Majority vs default wins / losses | Exact p | Mean accepted-wrong | Mean empty-on-answerable |
|---|---|---|---|---|---|---|---|
| A | 79.375 ± 3.777 | 72–85 | 81 | 25 / 12 | 0.047031 | 41.500 | 9.125 |
| B | 84.125 ± 4.454 | 77–90 | 84 | 28 / 12 | 0.016589 | 40.250 | 4.750 |

| Arm / seed | Dev / 61 | Everyday / 80 | Pooled / 141 | Accepted-wrong | Abstain-missed | Empty-on-answerable | Lint-rejected-on-answerable |
|---|---|---|---|---|---|---|---|
| A / 1 | 27 | 52 | 79 | 47 | 2 | 2 | 11 |
| A / 2 | 23 | 54 | 77 | 49 | 1 | 6 | 8 |
| A / 3 | 27 | 54 | 81 | 39 | 2 | 5 | 14 |
| A / 4 | 29 | 52 | 81 | 35 | 0 | 16 | 9 |
| A / 5 | 25 | 47 | 72 | 36 | 0 | 22 | 11 |
| A / 6 | 28 | 53 | 81 | 41 | 1 | 8 | 10 |
| A / 7 | 27 | 58 | 85 | 40 | 1 | 6 | 9 |
| A / 8 | 27 | 52 | 79 | 45 | 1 | 8 | 8 |
| B / 1 | 30 | 57 | 87 | 41 | 3 | 1 | 9 |
| B / 2 | 31 | 59 | 90 | 37 | 3 | 0 | 11 |
| B / 3 | 24 | 56 | 80 | 46 | 2 | 1 | 12 |
| B / 4 | 25 | 59 | 84 | 48 | 2 | 0 | 7 |
| B / 5 | 31 | 57 | 88 | 36 | 1 | 6 | 10 |
| B / 6 | 28 | 49 | 77 | 39 | 1 | 12 | 12 |
| B / 7 | 29 | 57 | 86 | 40 | 2 | 3 | 10 |
| B / 8 | 28 | 53 | 81 | 35 | 1 | 15 | 9 |

| Arm | Mean abstain-missed | Mean lint-rejected-on-answerable | Correct all 8 | Correct none | Mixed |
|---|---|---|---|---|---|
| A | 1.000 | 10.000 | 55 | 43 | 43 |
| B | 1.875 | 10.000 | 58 | 42 | 41 |

A vs B per-case majority: A-only 3, B-only 6; exact McNemar p = 0.507812.
A mean − default = 11.375 correct cases; paired case-bootstrap 95% CI [0.875, 22.250] (10,000 resamples, seed 20261014).
The interval resamples cases, retaining all seed outcomes per selected case; it does not estimate uncertainty from drawing eight new training seeds.

## Registered rule outcomes

- **R1: PASS**.
  Mean 79.375 versus required 76; majority p 0.047031 versus <0.05; accepted-wrong 41.500 versus ≤42.
- **R2: FAIL**.
  B SD 4.454 versus ≤1.889; B empty-on-answerable 4.750 versus ≤5; B mean 84.125 versus ≥77.375.
- **R3: FAIL**.
  A gain 11.375 versus <5; majority p 0.047031 versus >0.2.
- **R4 / A: FAIL (budget failure not triggered)**. Seed-1 sampled-mean RSS delta 3.247 MiB versus >64; dev/everyday p50 deltas -0.01 / +0.02 s versus >0.05.
- **R4 / B: FAIL (budget failure not triggered)**. Seed-1 sampled-mean RSS delta 14.793 MiB versus >64; dev/everyday p50 deltas +0.00 / -0.02 s versus >0.05.

PASS/FAIL above refers to the registered condition being true/false. For R4, a true condition means a deployment-budget failure. These are development results, not a ship decision.

R1 supports the registered conclusion: the runtime-LoRA gain is real on these 141 cases. R2 does not establish reducing empty targets as the stability fix. R3 does not support the lucky-draw/stop-tuning conclusion. Neither arm triggers R4; both sampled seed-1 runs pass the deployment budget.

## Memory and latency

| Run | Sample mean RSS MiB | Sample peak RSS MiB | Samples | Dev p50 s | Everyday p50 s |
|---|---|---|---|---|---|
| default | 1138.414 | 1156.781 | 310 | 0.21 | 0.24 |
| A-s1 | 1141.661 | 1168.750 | 306 | 0.20 | 0.26 |
| B-s1 | 1153.206 | 1170.438 | 274 | 0.21 | 0.22 |

Mean-RSS budget = 1202.414 MiB; peak-RSS budget for comparison = 1220.781 MiB. Per-split p50 budgets = 0.26 / 0.29 s.
RSS uses ps rss (KiB ×1024), approximately every 0.1 s during each split, including startup. These are sampled values, not OS high-water marks. Raw timestamps/RSS and all observed PIDs/command lines are retained. p50 is the existing eval output rounded to two decimals, per split; no pooled p50 is claimed. Only seed 1 of each arm was sampled, as requested; across-seed RSS is unmeasured.

## Converter and artifact verification

Official llama.cpp tag **b11565**, commit `f9a95aeb2096d0c0218e0cd6e6d901cd37be798a`, detached worktree `/tmp/whatisit-lora-converter-b11565` on the GPU host. Converter SHA-256 `3c5f109f3d7a5ef530ea388d8e994512df6f544ce1aa8b2e39be446223637b93`. `--base /tmp/whatisit-teacher/student-metadata --outtype f16`. Every adapter has 224 f16 tensors; all LoRA pairs have rank 8, metadata alpha 160, scale 20.

**Seed-42 parity: 141/141 labels identical** between official f16 and reviewer f32 conversion, dev 29/61 and everyday 53/80 (82 pooled). This uses the preserved v3 arm-A seed-42 adapter, not an additional trained member of the eight-seed cohort. Its original adapter hash matches the earlier training result. Converter fallback was not needed.

| Arm / seed | Original adapter weights SHA-256 | Runtime f16 GGUF SHA-256 |
|---|---|---|
| A / 1 | `51d5e3891527cb63841aa1839302b7af33558a8f944e940a412bd67d8812d8eb` | `51d6596201f06ebe3eed74f049ff80a0bcb4abcc6d39b6df9da3f061468efe36` |
| A / 2 | `9d9d9ea1f758bc381cbddaba066866547cfade50074d6f9bd0493b4d97315d49` | `7810d78ccb691b395049e3a1a3a8f21ede67b184407336984450b04e60abba9b` |
| A / 3 | `b1b94f2f4bffb6b52ed8bd53331a9a9e8c40e0dc7747dd52efb8c5c65f7bbcb5` | `abf6dc5400e321a04f891a2547604cdf81525646aa754e5a246d8062ef35de66` |
| A / 4 | `fb2a843234ba064704d5ee159271d74e5df233bb9f4f662da998ec9d53f70706` | `0f29011cbf703dbe107dd918e248766a1fdf01f32a8869a21897011b5ec0b825` |
| A / 5 | `dde0209bff0ec17c3404f3e0e37bf5a34c99597838156846047141cc99eade73` | `7ac076a4f8136fe9bb0d7c32bd6dec6af7b710e77a1a8c1bb462782a0157161b` |
| A / 6 | `93ffafd1bdc04565506b7a4cab84c4c1b0c996f1a037221a9003379512fad9a4` | `32116ce3f087a0ccaacb77621fb2a646e41747fead976e5fb8f195895c3c1258` |
| A / 7 | `ff6d2d3fa5921fe06ff9cfb3b2acf1ba17dc40d8b660a3f3e9ccb7cf02838562` | `a1f20b5cdb4efc9db76a8bccdad1dd885cd61b98b5a7fc8c3f0a985575bea1e0` |
| A / 8 | `e7998666206f543c60769cc442f2d44e69a8a04e4f6f0d2284e0e23ed4476553` | `6ba7dd31964af46946cb224cbb16ff9694620a9bf6f1edfe4943f2072e0fdff2` |
| B / 1 | `b91ee3f3734bded9333ceda9e3c5dd84e86ebbd7d539c64c904c16128e648e7b` | `03a68ca83baa03a9ef298a0993a7a662ec89489da460bf329266d7078e5b2948` |
| B / 2 | `7bc8e7d64078a362d4a6d132af4238cadfdfc7bd6b3aaa2f5f436ea395a10041` | `7a85a92a6e169f8fa7ddf7a8b001ed8e44a196c519491507139a88ffc1cb0106` |
| B / 3 | `7370085370e00959dd23f578dea63e85a0f7d3a2f64accaa9d5196917547d455` | `aeef94026f70e67f6bd26c8a169564646915c3e3536c380ea9501580a3f7a974` |
| B / 4 | `b5b26f816a1b6ec016ff6547ada49689af05214f2f24ac2953625ec838b6eae1` | `70e3b5ea9e21a5e8bc49d7836ae0fdbaa463bfd3ffef14e050bf1965c2d07b73` |
| B / 5 | `5c2e18a1b1c1e0049016145b24230f0743426201246398906e97d868662ef74a` | `783b2900a688b04f61ae5c449a62515f190cf62526373f4bdbb1f56635ed5f60` |
| B / 6 | `f435a2161310a5fb91792d0fd7051cc00f80a7a961382ee9fdb440ee98ea8b61` | `20b5baa196d1bd9ac1b28e6b41eef64c8e8cedf5b7234eea8dd2cab7eb92917c` |
| B / 7 | `798ffe4e90517197cbf0714e981f11bed876deb2d259809e778859b230916926` | `e8e77f85bad6640b74a76e0f43d6f9a002c4b5f15822f23dfbbdf438a78bfa03` |
| B / 8 | `5e2698101c66e79850820915384d1145470aa97b89e3eb5bff48548514a318f7` | `f7e35882c4963fe847e206ac42428048a8806e6b7b3f1f68886417c169684ee2` |

A data SHA-256 `c8f9661db1cadf79d81c58f0fd8f0628ad3461c61c0a5f97c6b20f195ec06550`; B data SHA-256 `e083bd4d1da30b9ed91d65236d08d19dbf0c7260fe3daeecc82d363a0c4f85f5`; base GGUF SHA-256 `6f8a17a11129a31074c944f4c2602453fafd9de43bdaeb1630a8f511ec820f71`.

Both arms train on 857 command rows, but two command IDs move each way between training and validation: A-only s2add002/s2add003, B-only r00288/r02160. The exact IDs are in reports/grouped-splits.json.

All 16 reports verify train_rows == steps, arm data/source hashes, actual adapter file hashes and exact equality of val_ids within each arm and with the local grouped split. Training logs, reports, conversion checks and transfer hashes are retained. Only tools/, src/, tests/, NOTICE and the two training JSONL files were copied as training inputs; no eval directory was copied. No merged model was transferred to the Mac.

All remaining data, report, code, tokenizer/metadata, converter-parity and Mac server hashes are in `reports/artifact-manifest.json`, `reports/host-environment.json`, `reports/mac-environment.json` and `SHA256SUMS`. Local GGUFs remain under `~/.local/share/whatisit/finetune/runtime-lora-8seed/`; original adapters/run outputs remain on the GPU host.

## Ten most seed-unstable cases per arm

Ranked by distance from four correct seeds, then case ID, as registered. Commands and labels are ordered seeds 1–8. Null means no returned command.

### Arm A

- `e041`: 4/8 correct. how much cpu is Finder using
  Commands: `[null, "ps -o %cpu= -p $(pgrep Finder)", null, "ps -o %cpu= -p $(pgrep Finder)", null, null, "ps -o %cpu= -p $(pgrep Finder)", "ps -o %cpu= -p $(pgrep Finder)"]`.
  Labels: rejected, pass, rejected, pass, rejected, rejected, pass, pass.
- `m052`: 4/8 correct. Are any automatic power-on or shutdown events scheduled?
  Commands: `["pmset -g sched", "pmset schedule", "pmset schedule", "pmset -g sched", null, "pmset -g sched", "pmset schedule", "pmset -g sched | grep 'sleep|wake'"]`.
  Labels: pass, wrong, wrong, pass, rejected, pass, wrong, pass.
- `e012`: 5/8 correct. list the 5 biggets files in this folder
  Commands: `[null, "ls -lS | head -n 5", "ls -lS | head -n 5", null, null, "ls -lS | head -n 5", "ls -lS | head -n 5", "ls -lS | head -n 5"]`.
  Labels: rejected, pass, pass, rejected, rejected, pass, pass, pass.
- `e018`: 3/8 correct. replace every foo with bar in notes.txt, save the change in the file
  Commands: `["sed -i '' 's/foo/bar/g' notes.txt", "sed 's/foo/bar/g' notes.txt > notes_modified.txt && mv notes_modified.txt notes.txt", "sed 's/foo/bar/g' notes.txt > notes_modified.txt && mv notes_modified.txt notes.txt", "sed -i '' 's/foo/bar/g' notes.txt", "sed 's/foo/bar/g' notes.txt > notes_modified.txt && mv notes_modified.txt notes.txt", "sed 's/foo/bar/g' notes.txt", "sed -i '' 's/foo/bar/g' notes.txt", "sed 's/foo/bar/g' notes.txt > notes_modified.txt && mv notes_modified.txt notes.txt"]`.
  Labels: pass, wrong, wrong, pass, wrong, wrong, pass, wrong.
- `e040`: 5/8 correct. run backup.sh in the background and keep it going if i close the terminal
  Commands: `["nohup ./backup.sh &", "nohup ./backup.sh &", null, null, "nohup ./backup.sh &", null, "nohup ./backup.sh &", "nohup ./backup.sh &"]`.
  Labels: pass, pass, rejected, rejected, pass, rejected, pass, pass.
- `m076`: 3/8 correct. Rotate photo.jpg clockwise 90 degrees into rotated.jpg, preserving the source.
  Commands: `["sips -r 90 photo.jpg --out rotated.jpg", null, null, "sips -r 90 photo.jpg --out rotated.jpg", null, null, "sips -rotate 90 photo.jpg --out rotated.jpg", "sips -r 90 photo.jpg --out rotated.jpg"]`.
  Labels: pass, rejected, rejected, pass, rejected, rejected, wrong, pass.
- `e007`: 6/8 correct. put all the jpgs in this folder into a new folder called photos
  Commands: `["mkdir photos && find . -type f -name '*.jpg' -exec mv {} photos/ \\;", "mkdir photos && find . -type f -name '*.jpg' -exec mv {} photos/ \\;", "mkdir photos && find . -type f -name '*.jpg' -exec mv {} photos/ \\;", "mkdir photos && find . -type f -name '*.jpg' -exec mv {} photos/ \\;", "find . -type f -name '*.jpg' -exec mv '{}' ./photos/ ';'", "mkdir photos && find . -type f -name '*.jpg' -exec mv {} photos/ \\;", "mkdir photos && find . -type f -name '*.jpg' -exec mv {} photos/ \\;", null]`.
  Labels: pass, pass, pass, pass, wrong, pass, pass, rejected.
- `e009`: 6/8 correct. make notes.txt read-only so I dont edit it by accident
  Commands: `["chmod -w notes.txt", "chmod +r notes.txt", "chmod -w notes.txt", "chmod -w notes.txt", "chmod -w notes.txt", "chmod read-only notes.txt", "chmod -w notes.txt", "chmod -w notes.txt"]`.
  Labels: pass, wrong, pass, pass, pass, wrong, pass, pass.
- `e026`: 6/8 correct. what's different between v1.txt and v2.txt
  Commands: `["diff -u <(sort v1.txt) <(sort v2.txt)", "diff v1.txt v2.txt", "diff -u v1.txt v2.txt", "diff -u v1.txt v2.txt", "diff -u v1.txt v2.txt", "diff -u v1.txt v2.txt", "diff -u v1.txt v2.txt", "diff -u <(sort v1.txt) <(sort v2.txt)"]`.
  Labels: wrong, pass, pass, pass, pass, pass, pass, wrong.
- `e027`: 6/8 correct. find all my pdf files in Documents
  Commands: `["find ~/Documents -type f -name '*.pdf'", "find ~/Documents -type f -name '*.pdf'", "find ~/Documents -type f -name '*.pdf'", null, null, "find ~/Documents -type f -name '*.pdf'", "find ~/Documents -type f -name '*.pdf'", "find ~/Documents -type f -name '*.pdf'"]`.
  Labels: pass, pass, pass, rejected, rejected, pass, pass, pass.
### Arm B

- `e034`: 4/8 correct. list apps in /Applications with chrome in the name
  Commands: `["mdfind -onlyin /Applications 'kMDItemContentTypeTree == \"public.app\" && kMDItemDisplayName == \"*chrome*\"'", "find /Applications -type d -name '*Chrome*'", "mdfind -onlyin /Applications 'kMDItemFSName == \"Google Chrome.app\"'", "find /Applications -type d -name '*Chrome*'", "mdfind -onlyin /Applications 'kMDItemContentType == \"com.apple.dock.app\" && kMDItemUserDescription == \"Chrome\"'", "mdfind -onlyin /Applications 'kMDItemCFBundleName == \"Google Chrome\"'", "mdfind -onlyin /Applications 'kMDItemCFBundleName == \"Google Chrome\"'", "mdfind -onlyin /Applications 'kMDItemContentTypeTree == \"com.apple.application\" && kMDItemUserVisibleName == \"*chrome*\"'"]`.
  Labels: pass, pass, wrong, pass, wrong, wrong, wrong, pass.
- `e050`: 4/8 correct. which apps are using the network right now
  Commands: `["lsof -nP -i -n | grep -E 'tcp|udp'", "lsof -nP -i -n | awk '{print $9}' | sort -u", "netstat -an | grep :80", "lsof -i -P -n | awk '{print $9}' | sort -u", "netstat -an | grep :80", "netstat -an | grep -E 'ESTABLISHED|LISTENING' | awk '{print $5}' | cut -d: -f1 | sort -u", "lsof -nP -i -n | awk '{print $9}' | sort -u", null]`.
  Labels: pass, pass, wrong, pass, wrong, wrong, pass, rejected.
- `m016`: 4/8 correct. Print only field three from colon-delimited input.txt.
  Commands: `["cut -d: -f3 input.txt", "cut -d: -f3 input.txt", "sed 's/:.*//' input.txt", "awk -F':' '{print $3}' input.txt", "cut -d: -f3 input.txt", "cut -d: -f3 input.txt", "awk -F':' '{print $3}' input.txt", "awk -F':' '{print $3}' input.txt"]`.
  Labels: pass, pass, wrong, wrong, pass, pass, wrong, wrong.
- `m058`: 4/8 correct. Open notes.txt specifically in TextEdit.
  Commands: `["open -a TextEdit notes.txt", "open -a TextEdit notes.txt", "open -a TextEdit notes.txt", "open notes.txt", "open notes.txt", "open notes.txt", "open -a TextEdit notes.txt", "open notes.txt"]`.
  Labels: pass, pass, pass, wrong, wrong, wrong, pass, wrong.
- `e038`: 5/8 correct. is Google Chrome running right now
  Commands: `["pgrep -x \"Google Chrome\"", "pgrep -x \"Google Chrome\"", "pgrep -x \"Google Chrome\" || osascript -e 'tell application \"Google Chrome\" to activate'", "pgrep -x \"Google Chrome\"", "osascript -e 'tell application \"Google Chrome\" to get name of front window'", null, "pgrep -x \"Google Chrome\"", null]`.
  Labels: pass, pass, pass, pass, wrong, rejected, pass, rejected.
- `e040`: 3/8 correct. run backup.sh in the background and keep it going if i close the terminal
  Commands: `[null, "nohup ./backup.sh &", null, null, "nohup ./backup.sh &", null, "nohup ./backup.sh &", null]`.
  Labels: rejected, pass, rejected, rejected, pass, rejected, pass, rejected.
- `e068`: 3/8 correct. undo my last commit but keep my changes
  Commands: `[null, "git reset HEAD~1", "git reset --soft HEAD~1", "git reset --soft HEAD~1", null, null, null, null]`.
  Labels: rejected, pass, pass, pass, rejected, rejected, rejected, rejected.
- `m052`: 3/8 correct. Are any automatic power-on or shutdown events scheduled?
  Commands: `["pmset -g sched", "pmset -g sched | grep -q 'sleep|wake' && echo yes || echo no", "pmset schedule", "pmset schedule", "pmset -g sched", "launchctl list | grep -E 'system|user'", "pmset schedule", "launchctl list | grep -i 'system boot'"]`.
  Labels: pass, pass, wrong, wrong, pass, wrong, wrong, wrong.
- `m054`: 3/8 correct. is my battry charging right now
  Commands: `["pmset -g batt", "pmset -g batt | grep 'Battery State' | cut -d':' -f2", null, "pmset battery charge", null, null, "pmset -g batt", null]`.
  Labels: pass, pass, rejected, wrong, rejected, rejected, pass, rejected.
- `m114`: 3/8 correct. Delete every app cache safely with zero risk to my open apps.
  Commands: `["find /private/var/Apps -maxdepth 1 -mindepth 1 -type d -exec rm -rf {} +", "find /private/var/Apps -maxdepth 1 -mindepth 1 -type d -exec rm -rf {} +", "for i in $(mdfind -onlyin /Applications com.apple.ImageLibrary Image Library); do rm -rf \"$i\"; done", "find ~/Library/Caches -type d -exec sh -c 'rm -rf \"{}\"' \\;", null, null, "for i in $(mdfind -onlyin /Applications com.apple.appstore \"kMDItemContentType == 'com.apple.application'\"); do rm -rf \"$i\" > /dev/null 2>&1; done", null]`.
  Labels: abstain-missed, abstain-missed, abstain-missed, abstain-missed, abstain-ok, abstain-ok, abstain-missed, abstain-ok.

## Validation and reproduction

Focused tests failed before each new behavior was implemented, then passed. Full suite: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests` — 90 tests run: 89 passed, one CUDA-only test skipped locally; all six trainer tests, including that real-GPU test, pass on the host. All three default checks (step 1, step 5 and postflight) exactly match all 141 saved labels. Postflight p50 is 0.22 s dev / 0.26 s everyday; registered budget comparisons retain the initial sampled default.

Analysis: `PYTHONPATH=src .venv/bin/python tools/analyze_runtime_lora.py`. Re-run inference only after moving recorded outputs to a fresh destination: the retained eval driver refuses overwrite, pins stock PATH, uses only dev/everyday, terminates servers by PID, requires pgrep empty before every split and checks the running command line contains the expected base and adapter. Training/convert/transfer drivers and hashes are retained under reports/.

Pre-registration commit `b6f43d3` was committed and pushed before any cohort evaluation. Draft PR [#31](https://github.com/imaddde867/whatisit-macos/pull/31) targets main. Results are in a later commit on `exp/runtime-lora-8seed`.

## Deviations

- During the run, the /usr/bin/git shim began requiring an Xcode licence acknowledgement. Git operations use the existing direct Xcode Git binary; no system settings or licence were changed. Evaluation retains stock PATH; a postflight default label check verifies no label drift.
- No experimental deviations. The existing v3 seed-42 adapter supplies the requested converter-parity check; the 16 new runs remain seeds 1–8.
- GitNexus could not resolve the eval main function by UID; pre-edit file-level impact succeeded (LOW, zero external callers/flows), and context confirms only its own script entry point calls main. New-symbol lookups are absent until indexed. No production symbol was changed. The final staged detect_changes check ran successfully through the same GitNexus MCP server with process-local DEVELOPER_DIR pointing to CommandLineTools; risk LOW, zero affected processes.

## Not done

- Frozen/held-out reads, copies, scoring or final gate: prohibited; neither protected file was opened or hashed.
- Serving, prompts, lint, guards, accept patterns, v3 data, training recipe, shipped model, shipping, PR merge or HF publication changes: prohibited.
- RSS/latency repetitions across all eight seeds: only the requested default/A1/B1 workload was sampled. No across-seed memory claim.
- Human semantic review or fixes to existing lint false positives: outside this experiment.
- Removing the optimizer-step/validation-partition confound: B uses 936 steps versus A 1,092 by the requested recipe.
