#!/bin/bash -l
# Teacher pilot on Roihu-GPU: vLLM serves Qwen3.8-Flash-Next-FP8, tools/teacher_sample.py samples against it.
# Same protocol as the 27B pilot: r00001-r00100, n=5, temp 0.7, top-p 0.95, top-k off, seeds 1000+, max_tokens 16384.
#
# One-time setup (login node roihu-gpu; compute nodes may have no internet):
#   export P=/scratch/project_2020845/$USER/whatisit; mkdir -p $P/hf $P/out
#   module load python-vllm/0.29.0 && HF_HOME=$P/hf hf download Qwen/Qwen3.8-Flash-Next-FP8   # ~173 GiB, note the revision it prints
#   rsync -a tools/teacher_sample.py data/corpus/requests.jsonl roihu-gpu:$P/    # from the repo root on the Mac; also copy this file
#
# Smoke test (3 requests, 1 sample):  sbatch --time=01:00:00 --export=ALL,LIMIT=3,N=1,TAG=smoke tools/roihu_teacher_pilot.sbatch
# Pilot:                               sbatch --export=ALL,MODEL_REV=<hash> tools/roihu_teacher_pilot.sbatch
#
#SBATCH --job-name=whatisit-teacher
#SBATCH --account=project_2020845
#SBATCH --partition=gpumedium
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1 --cpus-per-task=288
#SBATCH --gres=gpu:gh200:4
#SBATCH --output=%x-%j.out

type module >/dev/null 2>&1 || source /usr/share/lmod/lmod/init/bash
# batch shells on GPU nodes start with an empty MODULEPATH
[ -n "${MODULEPATH:-}" ] || export MODULEPATH=/appl/modulefiles/manual/aida/aarch64:/appl/modulefiles/manual/general/aarch64
set -euo pipefail

P=${P:-/scratch/$SLURM_JOB_ACCOUNT/$USER/whatisit}
MODEL=Qwen/Qwen3.8-Flash-Next-FP8
LIMIT=${LIMIT:-100}
N=${N:-5}
TAG=${TAG:-pilot}
PORT=8000
OUT=$P/out/$TAG-$SLURM_JOB_ID
mkdir -p "$OUT"

module purge
module load "${VLLM_MODULE:-python-vllm/0.29.0}"

export HF_HOME=$P/hf
export HF_HUB_OFFLINE=1
export TORCHINDUCTOR_CACHE_DIR=$TMPDIR/torch-cache

# --generation-config vllm: ignore the model's generation_config.json so unset top_k stays off, matching the 27B pilot.
# Verified on 0.29.0: --max-num-seqs must stay <= the Mamba cache blocks (411 here); triton GDN prefill avoids the
# flashinfer cutlass.cute import that is missing in the container; autotune off because one run spent 31 min in
# trtllm fused_moe tuning and hit gloo's 30 min barrier timeout. No --reasoning-parser: thinking arrives in content.
srun apptainer exec "$SIF" \
  vllm serve "$MODEL" --served-model-name teacher \
  --tensor-parallel-size 4 --enable-expert-parallel \
  --generation-config vllm --max-model-len 32768 --max-num-seqs 32 --gdn-prefill-backend triton \
  --kernel-config '{"enable_flashinfer_autotune": false}' \
  --host 127.0.0.1 --port $PORT > "$OUT/vllm.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT

# Wait for the server: weights come off Lustre, allow 45 min.
for _ in $(seq 270); do
  curl -sf "http://127.0.0.1:$PORT/v1/models" > /dev/null && break
  kill -0 $SERVER 2>/dev/null || { echo "vllm died, see $OUT/vllm.log"; exit 1; }
  sleep 10
done
curl -sf "http://127.0.0.1:$PORT/v1/models" > /dev/null || { echo "vllm not ready in 45 min"; exit 1; }

# thinking/content shape of this server, for the manifest review
python3 "$P/roihu_probe.py" > "$OUT/probe.log" 2>&1 || true

python3 "$P/teacher_sample.py" \
  --requests "$P/requests.jsonl" --out "$OUT/raw_samples.jsonl" --manifest "$OUT/manifest.json" \
  --base-url "http://127.0.0.1:$PORT/v1" --model teacher \
  --n "$N" --limit "$LIMIT" --temperature 0.7 --top-p 0.95 --top-k 0 --max-tokens 16384 \
  --concurrency 8 --seed 1000 \
  --quant "FP8 checkpoint, revision ${MODEL_REV:-unset}" \
  --server "vLLM $(python3 -c 'import vllm;print(vllm.__version__)' 2>/dev/null || echo unknown) via ${VLLM_MODULE:-python-vllm/0.29.0}, TP4 EP, 4xGH200" \
  --note "Roihu pilot, ${MODEL}, job $SLURM_JOB_ID"
