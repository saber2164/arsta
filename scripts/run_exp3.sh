#!/bin/bash
# =============================================================================
# ARSTA Experiment 3: Velocity Sweep
# Variable: UE speed in {0, 3, 10, 30} m/s via --ueSpeed
# Fixed: --numUes=20, --inactivityTimer=10
# Seeds: 1-10 per config
# Total: 4 speeds × 10 seeds × 2 schemes = 80 runs
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
SPEEDS=(0 3 10 30)
SEEDS=$(seq 1 10)
NUM_UES=20
INACTIVITY_TIMER=10
SIM_TIME=300
SCHEMES=("baseline" "arsta")

TOTAL_RUNS=$(( ${#SPEEDS[@]} * 10 * 2 ))
CURRENT_RUN=0

echo "========================================"
echo "ARSTA Experiment 3: Velocity Sweep"
echo "========================================"
echo "Speeds: ${SPEEDS[*]} m/s"
echo "Seeds: 1-10"
echo "Schemes: baseline, arsta"
echo "Total runs: ${TOTAL_RUNS}"
echo "Parallel jobs: ${MAX_JOBS}"
echo "========================================"

cd "${NS3_DIR}"

for speed in "${SPEEDS[@]}"; do
    for seed in ${SEEDS}; do
        for scheme in "${SCHEMES[@]}"; do
            CURRENT_RUN=$((CURRENT_RUN + 1))
            
            # Output directory
            OUTPUT_DIR="${RESULTS_DIR}/EXP3_speed${speed}_seed${seed}"
            mkdir -p "${OUTPUT_DIR}"
            
            # Select simulation script
            if [[ "$scheme" == "baseline" ]]; then
                SIM_SCRIPT="scratch/5g-rrc-baseline"
                LOG_PREFIX="baseline"
            else
                SIM_SCRIPT="scratch/5g-rrc-arsta"
                LOG_PREFIX="arsta"
            fi
            
            echo "Running EXP-3: speed=${speed}m/s seed=${seed} scheme=${scheme} [${CURRENT_RUN}/${TOTAL_RUNS}]"
            
            # Run simulation in background
            (
                ./ns3 run "${SIM_SCRIPT} -- \
                    --inactivityTimer=${INACTIVITY_TIMER} \
                    --numUes=${NUM_UES} \
                    --simTime=${SIM_TIME} \
                    --ueSpeed=${speed} \
                    --RngSeed=${seed} \
                    --outputDir=${OUTPUT_DIR}" \
                    > "${OUTPUT_DIR}/${LOG_PREFIX}_sim.log" 2> "${OUTPUT_DIR}/${LOG_PREFIX}_sim.err" \
                || echo "WARNING: ${scheme} speed=${speed} seed=${seed} exited with non-zero code"
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
echo "Experiment 3 completed: ${TOTAL_RUNS} runs"
echo "Results in: ${RESULTS_DIR}/EXP3_*"
echo "========================================"
