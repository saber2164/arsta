#!/bin/bash
# =============================================================================
# ARSTA Experiment 5: EWMA Alpha Tuning (ARSTA only)
# Variable: --ewmaAlpha in {0.1, 0.3, 0.5, 0.7}
# Fixed: --numUes=20, --inactivityTimer=10
# Only runs arsta.cc (no baseline needed)
# Seeds: 1-10 per config
# Total: 4 alphas × 10 seeds = 40 runs
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
ALPHAS=("0.1" "0.3" "0.5" "0.7")
SEEDS=$(seq 1 10)
NUM_UES=20
INACTIVITY_TIMER=10
SIM_TIME=300

TOTAL_RUNS=$(( ${#ALPHAS[@]} * 10 ))
CURRENT_RUN=0

echo "========================================"
echo "ARSTA Experiment 5: EWMA Alpha Tuning"
echo "========================================"
echo "EWMA alphas: ${ALPHAS[*]}"
echo "Seeds: 1-10"
echo "Scheme: arsta only (parameter tuning)"
echo "Total runs: ${TOTAL_RUNS}"
echo "Parallel jobs: ${MAX_JOBS}"
echo "========================================"

cd "${NS3_DIR}"

for alpha in "${ALPHAS[@]}"; do
    # Convert alpha to filename-safe format (replace . with p)
    alpha_safe="${alpha//./_}"
    
    for seed in ${SEEDS}; do
        CURRENT_RUN=$((CURRENT_RUN + 1))
        
        # Output directory
        OUTPUT_DIR="${RESULTS_DIR}/EXP5_alpha${alpha_safe}_seed${seed}"
        mkdir -p "${OUTPUT_DIR}"
        
        echo "Running EXP-5: alpha=${alpha} seed=${seed} [${CURRENT_RUN}/${TOTAL_RUNS}]"
        
        # Run simulation in background (ARSTA only)
        (
            ./ns3 run "scratch/5g-rrc-arsta -- \
                --inactivityTimer=${INACTIVITY_TIMER} \
                --numUes=${NUM_UES} \
                --simTime=${SIM_TIME} \
                --ewmaAlpha=${alpha} \
                --RngSeed=${seed} \
                --outputDir=${OUTPUT_DIR}" \
                > "${OUTPUT_DIR}/arsta_sim.log" 2> "${OUTPUT_DIR}/arsta_sim.err" \
            || echo "WARNING: arsta alpha=${alpha} seed=${seed} exited with non-zero code"
        ) &
        
        # Limit parallel jobs
        while [[ $(jobs -r -p | wc -l) -ge $MAX_JOBS ]]; do
            sleep 0.5
        done
    done
    
    # Wait for all jobs in this alpha batch to complete
    wait
done

# Final wait for any remaining jobs
wait

echo "========================================"
echo "Experiment 5 completed: ${TOTAL_RUNS} runs"
echo "Results in: ${RESULTS_DIR}/EXP5_*"
echo "========================================"
