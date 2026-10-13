#!/bin/bash
set -euo pipefail
BASE=/tank/hot/1cat-deploy
MODEL=/tank/hot/models/Swift-Qwen3.8-27B-NVFP4
export CUDA_VISIBLE_DEVICES=0,1
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_HOME=/usr/local/cuda-12.9
export PATH="$BASE/.venv/bin:$CUDA_HOME/bin:$PATH"
export CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13
export TORCH_CUDA_ARCH_LIST=7.0 MAX_JOBS=2
export OMP_NUM_THREADS=2 TORCHINDUCTOR_COMPILE_THREADS=1
export TORCHINDUCTOR_CACHE_DIR="$BASE/cache/torchinductor"
export TRITON_CACHE_DIR="$BASE/cache/triton"
export TORCH_EXTENSIONS_DIR="$BASE/cache/torch_extensions"
export VLLM_CACHE_ROOT="$BASE/cache/vllm"
export HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONNOUSERSITE=1
export VLLM_FLASH_V100_ROUTE_SUMMARY=1
export VLLM_SM70_QUANT_BACKEND=turbomind
export VLLM_SKIP_P2P_CHECK=0
export VLLM_USE_V2_MODEL_RUNNER=1
export NCCL_DEBUG=INFO NCCL_DEBUG_SUBSYS=INIT,GRAPH,P2P
: "${VLLM_API_KEY:?Set VLLM_API_KEY in the systemd EnvironmentFile}"
cd "$BASE"
# The 262144-token window includes prompt, reasoning and answer tokens; callers
# may request max_tokens=131072 when it fits. Natural EOS remains enabled.
# MM counts are admission limits; processor size and sampled frames bound work.
# Keep TP4-only QPN/custom-allreduce selectors shape-gated on these TP2 GPUs.
exec "$BASE/.venv/bin/vllm" serve "$MODEL" \
  --served-model-name [redacted model] \
  --host 10.10.10.11 --port 8000 \
  --dtype half --tensor-parallel-size 2 \
  --attention-backend FLASH_ATTN_V100 \
  --kv-cache-dtype fp8_e5m2 --max-model-len 262144 \
  --gpu-memory-utilization 0.92 \
  --max-num-batched-tokens 4096 --max-num-seqs 4 \
  --enable-chunked-prefill \
  --enable-prefix-caching --mamba-cache-mode align \
  --speculative-config '{"method":"mtp","num_speculative_tokens":4,"attention_backend":"FLASH_ATTN_V100"}' \
  --block-size 2048 --mamba-block-size 8192 \
  --limit-mm-per-prompt '{"image":{"count":10,"width":512,"height":512},"video":{"count":1,"num_frames":8,"width":512,"height":512}}' \
  --media-io-kwargs '{"video":{"num_frames":8}}' \
  --mm-processor-kwargs '{"size":{"shortest_edge":4096,"longest_edge":262144}}' \
  --mm-processor-cache-gb 0.25 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --seed 0 \
  --reasoning-parser qwen3 \
  --default-chat-template-kwargs '{"enable_thinking":true}' "$@"
