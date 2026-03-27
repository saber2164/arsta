#!/bin/bash
# =============================================================================
# ARSTA Experiment 1: Inactivity Timer Sweep
# Variable: --inactivityTimer in {5, 10, 20, 30} seconds
# Fixed: --numUes=20, --simTime=300, UE speed 1-10 m/s
# Seeds: 1-10 per config
# Total: 4 timers × 10 seeds × 2 schemes = 80 runs
# =============================================================================

set -euo pipefail

# Project root (parent of scripts directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS3_DIR="${PROJECT_ROOT}/ns3"
RESULTS_DIR="${PROJECT_ROOT}/results/raw"

# Suppress ns-3 debug output
export NS_LOG=""

# Parallelism: use half of available CPUs
MAX_JOBS=$(( $(nproc) / 2 ))
[[ $MAX_JOBS -lt 1 ]] && MAX_JOBS=1

# Experiment parameters
TIMERS=(5 10 20 30)
SEEDS=$(seq 1 10)
NUM_UES=20
SIM_TIME=300
UE_SPEED_MIN=1
UE_SPEED_MAX=10
SCHEMES=("baseline" "arsta")

TOTAL_RUNS=$(( ${#TIMERS[@]} * 10 * 2 ))
CURRENT_RUN=0

echo "========================================"
echo "ARSTA Experiment 1: Inactivity Timer Sweep"
echo "========================================"
echo "Timers: ${TIMERS[*]}"
echo "Seeds: 1-10"
echo "Schemes: baseline, arsta"
echo "Total runs: ${TOTAL_RUNS}"
echo "Parallel jobs: ${MAX_JOBS}"
echo "========================================"

cd "${NS3_DIR}"

for timer in "${TIMERS[@]}"; do
    for seed in ${SEEDS}; do
        for scheme in "${SCHEMES[@]}"; do
            CURRENT_RUN=$((CURRENT_RUN + 1))
            
            # Output directory
            OUTPUT_DIR="${RESULTS_DIR}/EXP1_timer${timer}_seed${seed}"
            mkdir -p "${OUTPUT_DIR}"
            
            # Select simulation script
            if [[ "$scheme" == "baseline" ]]; then
                SIM_SCRIPT="scratch/5g-rrc-baseline"
                LOG_PREFIX="baseline"
            else
                SIM_SCRIPT="scratch/5g-rrc-arsta"
                LOG_PREFIX="arsta"
            fi
            
            echo "Running EXP-1: timer=${timer} seed=${seed} scheme=${scheme} [${CURRENT_RUN}/${TOTAL_RUNS}]"
            
            # Run simulation in background
            (
                ./ns3 run "${SIM_SCRIPT} -- \
                    --inactivityTimer=${timer} \
                    --numUes=${NUM_UES} \
                    --simTime=${SIM_TIME} \
                    --ueSpeedMin=${UE_SPEED_MIN} \
                    --ueSpeedMax=${UE_SPEED_MAX} \
                    --RngSeed=${seed} \
                    --outputDir=${OUTPUT_DIR}" \
                    > "${OUTPUT_DIR}/${LOG_PREFIX}_sim.log" 2> "${OUTPUT_DIR}/${LOG_PREFIX}_sim.err" \
                || echo "WARNING: ${scheme} timer=${timer} seed=${seed} exited with non-zero code"
            ) &
            
            # Limit parallel jobs
            while [[ $(jobs -r -p | wc -l) -ge $MAX_JOBS ]]; do
                sleep 0.5
            done
        done
        
        # Wait for all jobs in this seed batch to complete
        wait
    done
done

# Final wait for any remaining jobs
wait

echo "========================================"
echo "Experiment 1 completed: ${TOTAL_RUNS} runs"
echo "Results in: ${RESULTS_DIR}/EXP1_*"
echo "========================================"
