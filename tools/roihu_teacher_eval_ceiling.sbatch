#!/bin/bash -l
# Parameterized copy of tools/roihu_teacher_pilot.sbatch for the dev+everyday teacher-ceiling eval.
# Difference: REQUESTS selects the request file (default: the corpus copy at $P/requests.jsonl),
# so the eval request file lands in its own directory instead of overwriting the corpus copy.
#
# Smoke:  sbatch --time=01:00:00 --export=ALL,MODEL_REV=<hash>,LIMIT=3,N=1,TAG=smokeceiling,REQUESTS=$P/eval-ceiling/requests.jsonl tools/roihu_teacher_eval_ceiling.sbatch
# Full:   sbatch --export=ALL,MODEL_REV=<hash>,TAG=ceiling,RUN=dev-everyday,REQUESTS=$P/eval-ceiling/requests.jsonl tools/roihu_teacher_eval_ceiling.sbatch
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
: "${MODEL_REV:?MODEL_REV is required; set it to the downloaded Hugging Face commit hash}"

P=${P:-/scratch/$SLURM_JOB_ACCOUNT/$USER/whatisit}
REQUESTS=${REQUESTS:-$P/requests.jsonl}
MODEL=Qwen/Qwen3.8-Flash-Next-FP8
LIMIT=${LIMIT:-100}
N=${N:-5}
TAG=${TAG:-pilot}
PORT=8000
OUT=$P/out/$TAG-${RUN:-$SLURM_JOB_ID}   # fixed RUN=<name> makes a re-submit resume the same raw file
mkdir -p "$OUT"

module purge
module load "${VLLM_MODULE:-python-vllm/0.29.0}"

export HF_HOME=$P/hf
export HF_HUB_OFFLINE=1
export TORCHINDUCTOR_CACHE_DIR=$TMPDIR/torch-cache

# Serve flags are identical to the pilot/full run: --generation-config vllm ignores the model's
# generation_config.json so unset top_k stays off; --max-num-seqs <= the Mamba cache blocks (411);
# triton GDN prefill avoids the flashinfer cutlass.cute import missing in the container; autotune off
# (one run spent 31 min in trtllm fused_moe tuning and hit gloo's 30 min barrier timeout).
# No --reasoning-parser: thinking arrives in content. $SIF is set by the python-vllm module.
srun apptainer exec "$SIF" \
  vllm serve "$MODEL" --revision "$MODEL_REV" --tokenizer-revision "$MODEL_REV" --served-model-name teacher \
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
  --requests "$REQUESTS" --out "$OUT/raw_samples.jsonl" --manifest "$OUT/manifest.json" \
  --base-url "http://127.0.0.1:$PORT/v1" --model teacher \
  --n "$N" --limit "$LIMIT" --temperature 0.7 --top-p 0.95 --top-k 0 --max-tokens 16384 \
  --concurrency "${CONC:-8}" --seed 1000 \
  --quant "FP8 checkpoint, revision ${MODEL_REV}" \
  --server "vLLM $(python3 -c 'import vllm;print(vllm.__version__)' 2>/dev/null || echo unknown) via ${VLLM_MODULE:-python-vllm/0.29.0}, TP4 EP, 4xGH200" \
  --note "Roihu teacher-ceiling eval, ${MODEL}, job $SLURM_JOB_ID"
