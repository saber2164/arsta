#!/bin/bash
# =============================================================================
# ARSTA Master Experiment Script
# Runs all 5 experiments in sequence:
#   EXP-1: Inactivity Timer Sweep (80 runs)
#   EXP-2: UE Count Scalability (80 runs)
#   EXP-3: Velocity Sweep (80 runs)
#   EXP-4: Traffic Intensity (60 runs)
#   EXP-5: EWMA Alpha Tuning (40 runs)
# Total: 340 simulation runs
# =============================================================================

set -euo pipefail

# Project root (parent of scripts directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
NS3_DIR="${PROJECT_ROOT}/ns3"
RESULTS_DIR="${PROJECT_ROOT}/results"

# Suppress ns-3 debug output
export NS_LOG=""

# Start timer
START_TIME=$(date +%s)
START_DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "========================================"
echo "ARSTA Master Experiment Runner"
echo "========================================"
echo "Start time: ${START_DATE}"
echo "Project root: ${PROJECT_ROOT}"
echo "========================================"

# -----------------------------------------------------------------------------
# Step 1: Verify ns-3 build is up to date
# -----------------------------------------------------------------------------
echo ""
echo "[STEP 1/7] Checking ns-3 build..."
cd "${NS3_DIR}"

if [[ ! -f "./ns3" ]]; then
    echo "ERROR: ns3 executable not found in ${NS3_DIR}"
    echo "Please run ./ns3 configure && ./ns3 build first"
    exit 1
fi

# Check if scratch programs are built
echo "Verifying simulation scripts are built..."
./ns3 build scratch/5g-rrc-baseline scratch/5g-rrc-arsta 2>&1 | tail -5

if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
    echo "ERROR: Failed to build simulation scripts"
    exit 1
fi

echo "ns-3 build verified."

# -----------------------------------------------------------------------------
# Step 2: Create results directory structure
# -----------------------------------------------------------------------------
echo ""
echo "[STEP 2/7] Creating results directory structure..."
mkdir -p "${RESULTS_DIR}/raw"
mkdir -p "${RESULTS_DIR}/processed"
mkdir -p "${RESULTS_DIR}/figures"
echo "Results directories created."

# -----------------------------------------------------------------------------
# Step 3-7: Run experiments
# -----------------------------------------------------------------------------
run_experiment() {
    local exp_num=$1
    local exp_script=$2
    local exp_name=$3
    local step=$4
    
    echo ""
    echo "[STEP ${step}/7] Running ${exp_name}..."
    local exp_start=$(date +%s)
    
    if bash "${SCRIPTS_DIR}/${exp_script}"; then
        local exp_end=$(date +%s)
        local exp_duration=$((exp_end - exp_start))
        echo "${exp_name} completed in ${exp_duration} seconds"
    else
        echo "WARNING: ${exp_name} completed with errors"
    fi
}

run_experiment 1 "run_exp1.sh" "EXP-1: Inactivity Timer Sweep" 3
run_experiment 2 "run_exp2.sh" "EXP-2: UE Count Scalability" 4
run_experiment 3 "run_exp3.sh" "EXP-3: Velocity Sweep" 5
run_experiment 4 "run_exp4.sh" "EXP-4: Traffic Intensity" 6
run_experiment 5 "run_exp5.sh" "EXP-5: EWMA Alpha Tuning" 7

# -----------------------------------------------------------------------------
# Parse results and verify CSV files
# -----------------------------------------------------------------------------
echo ""
echo "[POST] Parsing results and generating CSVs..."
cd "${PROJECT_ROOT}"

if [[ -f "${PROJECT_ROOT}/python/parse_results.py" ]]; then
    python3 "${PROJECT_ROOT}/python/parse_results.py"
    PARSE_STATUS=$?
    if [[ $PARSE_STATUS -ne 0 ]]; then
        echo "WARNING: Results parsing completed with errors"
    else
        echo "Results parsing completed successfully."
    fi
else
    echo "WARNING: python/parse_results.py not found, skipping result parsing"
fi

# -----------------------------------------------------------------------------
# Final summary
# -----------------------------------------------------------------------------
END_TIME=$(date +%s)
END_DATE=$(date '+%Y-%m-%d %H:%M:%S')
TOTAL_DURATION=$((END_TIME - START_TIME))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))
SECONDS=$((TOTAL_DURATION % 60))

echo ""
echo "========================================"
echo "ARSTA Experiment Suite Complete"
echo "========================================"
echo "Start time:  ${START_DATE}"
echo "End time:    ${END_DATE}"
echo "Duration:    ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo ""
echo "Experiments completed:"
echo "  EXP-1: Inactivity Timer Sweep (80 runs)"
echo "  EXP-2: UE Count Scalability   (80 runs)"
echo "  EXP-3: Velocity Sweep         (80 runs)"
echo "  EXP-4: Traffic Intensity      (60 runs)"
echo "  EXP-5: EWMA Alpha Tuning      (40 runs)"
echo "  ─────────────────────────────────────"
echo "  Total:                        340 runs"
echo ""
echo "Results location:"
echo "  Raw:       ${RESULTS_DIR}/raw/"
echo "  Processed: ${RESULTS_DIR}/processed/"
echo "  Figures:   ${RESULTS_DIR}/figures/"
echo "========================================"

# Count actual result directories
RAW_COUNT=$(find "${RESULTS_DIR}/raw" -maxdepth 1 -type d -name 'EXP*' 2>/dev/null | wc -l)
echo ""
echo "Result directories found: ${RAW_COUNT}"

# List any warnings/errors
ERROR_COUNT=$(find "${RESULTS_DIR}/raw" -name '*_sim.err' -size +0 2>/dev/null | wc -l)
if [[ $ERROR_COUNT -gt 0 ]]; then
    echo "WARNING: ${ERROR_COUNT} simulation(s) had errors. Check *_sim.err files."
fi

echo ""
echo "Done."
