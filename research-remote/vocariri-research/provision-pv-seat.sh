#!/bin/bash
set -euo pipefail
root=/tank/docker/[container host]/agent-seats
project=/workspaces/vocariri-research
[ "$(readlink -f "$project")" = /workspaces/vocariri-research ]
mkdir -p "$root/vocariri/home/.omp/agent"
install -m 600 /workspaces/vocariri-research/seat-config.yml "$root/vocariri/home/.omp/agent/config.yml"
chown -R 1000:1000 "$root/vocariri/home"



docker commit vocariri-research vocariri/research-tools:20260924 >/dev/null
if ! docker container inspect [research container] >/dev/null 2>&1; then
 docker run -d --name [research container] --init --cpus 2 --memory 3g --pids-limit 256 --shm-size 512m --user 1000:1000 -e HOME=[home] \
  --mount type=bind,src="$project",dst=/workspace \
  --mount type=bind,src="$root/vocariri/home",dst=[home] \
  --mount type=bind,src="$root/qwen-scene-stress/home/.omp/agent/models.yml",dst=[home]/.omp/agent/models.yml,readonly \
  --workdir /workspace vocariri/research-tools:20260924 sleep infinity
fi
docker exec --user 1000:1000 [research container] omp models find swift-qwen --json
