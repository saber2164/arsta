# ARSTA Project — Multi-Agent Execution Plan for GitHub Copilot

**Project:** Adaptive RRC State Transition Algorithm (ARSTA) for 5G NR UE Energy Optimisation  
**Simulator:** ns-3.44 + 5G-LENA NR v4.0  
**Language:** C++ (simulation) · Python 3.11 (analysis) · MATLAB (validation)  
**Base Paper:** Ding et al., "Energy Optimization for Mobile Applications by Exploiting 5G Inactive State," IEEE TMC 2024 — DOI: 10.1109/TMC.2024.3377696  
**Target:** Beat base paper: >9.5% energy reduction → achieve 25–35%

---

## How to use this plan with Copilot

Open this file in VS Code with GitHub Copilot Chat enabled.  
For each agent block below, paste the **Copilot prompt** into Copilot Chat (`Ctrl+Shift+I`).  
Each agent is self-contained — run them in the order shown, or run independent agents in parallel using multiple Copilot Chat windows.  
Agents marked `[PARALLEL]` can run simultaneously. Agents marked `[SEQUENTIAL]` must wait for the previous agent to finish.

```
Copilot agent mode: Use @workspace to give each agent access to all project files.
Enable: Settings → Copilot → Agent Mode → ON
Multi-agent: Open multiple Copilot Chat panels (View → Open View → Copilot Chat × 6)
```

---

## Project file structure (create this first)

```
5g-rrc-research/
├── plan.md                          ← this file
├── .github/copilot-instructions.md  ← global project context for all agents
├── ns3/
│   └── scratch/
│       ├── 5g-rrc-baseline.cc       ← Agent 1 creates
│       ├── 5g-rrc-arsta.cc          ← Agent 1 creates
│       └── 5g-rrc-sweep.cc          ← Agent 1 creates
├── python/
│   ├── energy_model.py              ← Agent 2 creates
│   ├── arsta.py                     ← Agent 2 creates
│   ├── parse_results.py             ← Agent 4 creates
│   ├── plot_results.py              ← Agent 4 creates
│   └── stats.py                     ← Agent 4 creates
├── matlab/
│   ├── energy_analytical.m          ← Agent 5 creates
│   └── validate_ns3.m               ← Agent 5 creates
├── results/
│   ├── raw/                         ← simulation CSV/XML output goes here
│   ├── processed/                   ← Agent 4 output
│   └── figures/                     ← Agent 4 plots
├── scripts/
│   ├── run_all.sh                   ← Agent 3 creates
│   └── install_deps.sh              ← Agent 1 creates
└── paper/
    ├── main.tex                     ← Agent 6 creates
    └── references.bib               ← Agent 6 creates
```

---

## Global Copilot context file

**Create this file first:** `.github/copilot-instructions.md`  
Paste this verbatim so every agent has shared project context:

```markdown
# ARSTA Project — Copilot global context

You are working on ARSTA: Adaptive RRC State Transition Algorithm for 5G NR UE energy optimisation.

## What ARSTA does
ARSTA is a UE-side algorithm running inside ns-3. It has 4 modules:
1. Traffic Prediction: EWMA of inter-packet arrival times → predicts idle periods → triggers early RRC_INACTIVE entry before inactivity timer expires
2. Mobility-Aware DRX: reads UE velocity → sets DRX cycle (20ms at >15m/s, 80ms at 5–15m/s, 160ms at <5m/s)
3. Handover-Aware Locking: monitors RSRP gradient → if dRSRP/dt < -2dB/s, locks UE in CONNECTED for predicted HO window
4. Paging Optimisation: velocity-based RNA area sizing (small RNA for stationary, large for mobile)

## Power model (3GPP TR 38.840)
- RRC_IDLE: 5 mW
- RRC_INACTIVE: 15 mW  
- RRC_CONNECTED: 900 mW
- TRANSITION: 250 mW

## Simulation parameters
- ns-3.44 + 5G-LENA NR v4.0
- 3.5 GHz FR1, 40 MHz BW
- 3 gNBs in equilateral triangle (500m sides, height 25m)
- 20–50 UEs, RandomWaypointMobility, 0–30 m/s, height 1.5m
- Bursty Poisson traffic: OnOff (ON=ExponentialRV[Mean=2s], OFF=ExponentialRV[Mean=8s], 1Mbps)
- Simulation time: 300s, 10 seeds per config, 95% CI
- Channel: 3GPP TR 38.901 UMa, shadowing enabled σ=4/6dB (LoS/NLoS)

## Base paper to beat
Ding et al. IEEE TMC 2024: 9.5% energy reduction, 12.4% latency reduction.
ARSTA target: 25–35% energy reduction.

## Key constraints
- NEVER use waf — use ./ns3 (CMake, ns-3 ≥ 3.36)
- NEVER pass values directly to constructors — use SetAttribute()
- ALWAYS wrap time values: Seconds(), MilliSeconds(), not raw numbers
- RRC_INACTIVE does not exist natively in 5G-LENA — implement as custom state extension
- All Python plots must use Times New Roman, 300 DPI, save as PDF for IEEE submission
```

---

## Agent 1 — Simulation Engineer [SEQUENTIAL — run first]

**Responsibility:** ns-3 build setup, baseline simulation, ARSTA C++ integration  
**Output files:** `ns3/scratch/5g-rrc-baseline.cc`, `ns3/scratch/5g-rrc-arsta.cc`, `scripts/install_deps.sh`  
**Estimated time:** Week 1–2

### Copilot prompt — paste into Chat window 1:

```
@workspace You are Agent 1: Simulation Engineer for the ARSTA project.
Read .github/copilot-instructions.md for full project context.

Your job this session: Create the three ns-3 simulation files listed below.
Follow ALL constraints in the context file exactly.

TASK 1 — Create scripts/install_deps.sh
Write a bash script that:
- Installs ns-3.44 from https://gitlab.com/nsnam/ns-3-dev.git at tag ns-3.44
- Clones 5G-LENA NR into contrib/nr at tag nr-v4.0 from https://gitlab.com/cttc-lena/nr.git
- Installs Ubuntu dependencies: g++ cmake ninja-build python3 git libsqlite3-dev
- Runs ./ns3 configure --enable-examples --enable-tests
- Runs ./ns3 build
- Verifies by running ./ns3 run cttc-nr-demo
- Prints PASS or FAIL at the end

TASK 2 — Create ns3/scratch/5g-rrc-baseline.cc
This is the 3GPP static-timer baseline simulation. It must:
- Use NrHelper + NrPointToPointEpcHelper + IdealBeamformingHelper
- Create 3 gNBs in equilateral triangle (positions: (0,0,25), (500,0,25), (250,433,25))
- Create 20 UEs with RandomWaypointMobility (speed: UniformRV[1,10] m/s default)
- Configure 3.5 GHz, 40 MHz BW, numerology mu=1, TxPower=43dBm
- Use GridScenarioHelper if available for gNB placement
- Install OnOff traffic: rate=1Mbps, ON=ExponentialRV[Mean=2], OFF=ExponentialRV[Mean=8]
- Connect trace callbacks for RRC state transitions writing to CSV:
  time_s,imsi,cell_id,old_state,new_state
- Connect FlowMonitor and save to XML
- Accept command-line args: --numUes (default 20), --simTime (default 300),
  --rngRun (default 1), --inactivityTimer (default 10), --outputDir (default "results/raw/")
- Run for simTime seconds with RngSeedManager::SetRun(rngRun)
- Print summary to stdout: total tx bytes, total rx bytes, simulation duration

TASK 3 — Create ns3/scratch/5g-rrc-arsta.cc
Copy the baseline structure, then add the ARSTA algorithm as a UeRrcMonitor class:

class UeRrcMonitor {
public:
  struct UeState {
    uint64_t imsi;
    LteUeRrc::State rrcState;  // actual ns-3 RRC state
    int customState;           // 0=IDLE 1=INACTIVE 2=CONNECTED
    double ewmaIat;            // EWMA inter-arrival time estimate
    Time lastPktTime;
    Time lastStateChange;
    double velocity;           // m/s, updated from mobility model
    double rsrp;               // dBm, updated from PHY trace
    double rsrpGradient;       // dRSRP/dt dB/s
    bool hoLocked;             // true = state locked during HO window
    Time hoLockExpiry;
  };

  // Module 1: EWMA traffic predictor
  // alpha = 0.3 default, updates ewmaIat on each packet arrival
  // if ewmaIat > inactivityThreshold * 0.6: trigger early INACTIVE
  void OnPacketArrival(uint64_t imsi, Time arrivalTime);

  // Module 2: Velocity-aware DRX tuning
  // v < 5 m/s: drxCycle = 160ms
  // 5 <= v < 15: drxCycle = 80ms
  // v >= 15: drxCycle = 20ms
  void UpdateDrxCycle(uint64_t imsi);

  // Module 3: HO-aware state locking
  // if rsrpGradient < -2.0 dB/s: lock state, set expiry = Now + velocity*10ms
  void CheckHandoverLock(uint64_t imsi);

  // Module 4: RNA area sizing (log to CSV, not enforced in simulation)
  // v < 3: rnaSize = "small", v < 15: "medium", else "large"
  std::string GetRnaSize(double velocity);

  // Logging
  std::ofstream logFile;
  void LogStateChange(uint64_t imsi, int oldState, int newState, std::string reason);
};

The ARSTA simulation CSV output must add columns:
time_s,imsi,cell_id,old_state,new_state,custom_state,ewma_iat,velocity,drx_cycle_ms,ho_locked,rna_size

Accept all same command-line args as baseline PLUS:
--ewmaAlpha (default 0.3)
--hoLockThreshold (default -2.0, dB/s)

After writing each file, verify it compiles with: ./ns3 build 2>&1 | tail -5
If compilation fails, read the error and fix it before moving on.
```

---

## Agent 2 — Algorithm Designer [PARALLEL with Agent 1]

**Responsibility:** Python ARSTA prototype, EWMA implementation, energy model  
**Output files:** `python/arsta.py`, `python/energy_model.py`  
**Estimated time:** Week 1–2

### Copilot prompt — paste into Chat window 2:

```
@workspace You are Agent 2: Algorithm Designer for the ARSTA project.
Read .github/copilot-instructions.md for full project context.

TASK 1 — Create python/energy_model.py
Implement the TR 38.840 UE power model exactly as specified in copilot-instructions.md.
The file must contain:

class EnergyModel:
    POWER_MW = {
        'RRC_IDLE': 5.0,
        'RRC_INACTIVE': 15.0,
        'RRC_CONNECTED': 900.0,
        'TRANSITION': 250.0
    }

    def compute_session_energy_mj(self, state_trace_df: pd.DataFrame) -> float:
        """
        Input: DataFrame with columns [time_s, imsi, old_state, new_state, dwell_ms]
        Output: total energy in mJ for one UE session
        Maps ns-3 state integers to power levels:
          5 (IDLE_CAMPED_NORMALLY) → RRC_IDLE
          9 (CONNECTED_NORMALLY)   → RRC_CONNECTED
          99 (custom INACTIVE)     → RRC_INACTIVE
          anything else            → TRANSITION
        """

    def compute_state_ratios(self, state_trace_df: pd.DataFrame) -> dict:
        """Returns fraction of time in each state as percentages"""

    def energy_reduction_pct(self, baseline_mj: float, arsta_mj: float) -> float:
        """Returns (baseline - arsta) / baseline * 100"""

    def transition_count(self, state_trace_df: pd.DataFrame) -> int:
        """Count total IDLE↔CONNECTED and INACTIVE↔CONNECTED transitions"""

Include a __main__ block that generates synthetic test data and prints results.
All functions must have type hints and docstrings.

TASK 2 — Create python/arsta.py
Implement the ARSTA algorithm in Python exactly matching the C++ logic in arsta.cc.
This Python version is used to: (a) validate algorithm logic before C++ integration,
(b) run parameter sensitivity analysis without recompiling.

class ARSTASimulator:
    def __init__(self, alpha=0.3, inactive_threshold=0.6,
                 ho_lock_threshold=-2.0, inactivity_timer=10.0):
        self.alpha = alpha
        self.inactive_threshold = inactive_threshold  # fraction of inactivity_timer
        self.ho_lock_threshold = ho_lock_threshold    # dB/s
        self.inactivity_timer = inactivity_timer

    class UEContext:
        imsi: int
        ewma_iat: float       # seconds
        velocity: float       # m/s
        rsrp_history: list    # last 5 RSRP readings
        rsrp_gradient: float  # dB/s
        custom_state: int     # 0=IDLE, 1=INACTIVE, 2=CONNECTED
        ho_locked: bool
        ho_lock_expiry: float # simulation time

    def update_ewma(self, ctx: UEContext, iat_seconds: float) -> float:
        """Update EWMA: ewma = alpha * iat + (1-alpha) * ewma. Return new ewma."""

    def should_enter_inactive(self, ctx: UEContext) -> bool:
        """Return True if ewma_iat > inactivity_timer * inactive_threshold
        AND not ho_locked AND current state is CONNECTED"""

    def get_drx_cycle_ms(self, velocity: float) -> int:
        """v<5→160, 5≤v<15→80, v≥15→20"""

    def update_ho_lock(self, ctx: UEContext, current_time: float) -> None:
        """If rsrp_gradient < ho_lock_threshold: lock for velocity*10ms.
        If lock expired: unlock."""

    def get_rna_size(self, velocity: float) -> str:
        """v<3→'small', v<15→'medium', else→'large'"""

    def step(self, ctx: UEContext, event: dict, current_time: float) -> dict:
        """
        Process one event. event dict: {type: 'packet'|'rsrp_update'|'velocity_update',
                                        value: float, timestamp: float}
        Returns: {state_changed: bool, new_state: int, drx_ms: int,
                  ho_locked: bool, rna_size: str, reason: str}
        """

    def run_trace(self, events: list, ue_count: int = 20) -> pd.DataFrame:
        """Run full simulation from event list. Return per-UE state trace DataFrame."""

Write unit tests in a test_arsta.py file using pytest:
- test_ewma_convergence: verify EWMA converges to mean after 50 packets
- test_inactive_trigger: verify early INACTIVE fires at 60% of inactivity timer
- test_ho_lock_activates: verify lock triggers when gradient < -2 dB/s
- test_drx_boundaries: verify all 3 velocity thresholds give correct DRX cycle
- test_energy_reduction: run 100 simulated UEs, verify energy < baseline

Run: pytest python/test_arsta.py -v and fix any failures.
```

---

## Agent 3 — Experiment Planner [SEQUENTIAL — after Agent 1 baseline runs successfully]

**Responsibility:** Batch experiment runner, parameter sweep orchestration  
**Output files:** `scripts/run_all.sh`, `scripts/run_exp1.sh` through `run_exp5.sh`  
**Estimated time:** Week 2

### Copilot prompt — paste into Chat window 3:

```
@workspace You are Agent 3: Experiment Planner for the ARSTA project.
Read .github/copilot-instructions.md for full project context.

5 experiments must be run. Create one bash script per experiment PLUS a master script.
Each script runs both baseline AND arsta simulations for fair comparison.
All results go to results/raw/EXP{N}_{config}_seed{S}/

TASK 1 — Create scripts/run_exp1.sh (Inactivity Timer Sweep)
Variable: --inactivityTimer in {5, 10, 20, 30} seconds
Fixed: --numUes=20, --simTime=300, UE speed 1–10 m/s
Seeds: 1 through 10 for each timer value
Run baseline AND arsta for each (timer, seed) combination
Total runs: 4 timers × 10 seeds × 2 schemes = 80 simulation runs
Use background jobs (&) with wait after each seed batch to parallelise
Print progress: "Running EXP-1: timer=X seed=Y [Z/80]"

TASK 2 — Create scripts/run_exp2.sh (UE Count Scalability)
Variable: --numUes in {10, 20, 30, 50}
Fixed: --inactivityTimer=10, --simTime=300
Seeds: 1 through 10
Total: 4 counts × 10 seeds × 2 schemes = 80 runs

TASK 3 — Create scripts/run_exp3.sh (Velocity Sweep)
Variable: UE speed in {0, 3, 10, 30} m/s
Implementation: use --ueSpeed command-line arg (add this to both .cc files)
The ns-3 scripts must use ConstantVelocityMobilityModel when ueSpeed > 0,
and ConstantPositionMobilityModel when ueSpeed == 0
Fixed: --numUes=20, --inactivityTimer=10
Seeds: 1 through 10
Total: 4 speeds × 10 seeds × 2 schemes = 80 runs

TASK 4 — Create scripts/run_exp4.sh (Traffic Intensity)
Variable: traffic profile in {low, medium, high}
  low:    ON=ConstantRV[0.5], OFF=ConstantRV[20], rate=0.5Mbps
  medium: ON=ExponentialRV[2], OFF=ExponentialRV[8], rate=1Mbps (default)
  high:   ON=ConstantRV[8], OFF=ConstantRV[2], rate=2Mbps
Add --trafficProfile {low|medium|high} arg to both .cc files
Fixed: --numUes=20, --inactivityTimer=10
Seeds: 1 through 10
Total: 3 profiles × 10 seeds × 2 schemes = 60 runs

TASK 5 — Create scripts/run_exp5.sh (EWMA Alpha Tuning — ARSTA only)
Variable: --ewmaAlpha in {0.1, 0.3, 0.5, 0.7}
Fixed: --numUes=20, --inactivityTimer=10
Only run arsta.cc (no baseline needed — comparing ARSTA variants)
Seeds: 1 through 10
Total: 4 alphas × 10 seeds = 40 runs

TASK 6 — Create scripts/run_all.sh (Master script)
Must:
- Check that ns3 build is up to date before starting
- Run EXP-1 through EXP-5 in sequence
- Log total runtime
- At the end, call python python/parse_results.py to verify CSV files are valid
- Print final summary: how many CSV files were generated, any missing

IMPORTANT constraints for all scripts:
- Set NS_LOG="" to suppress ns-3 debug output
- Redirect stdout to {outputDir}/sim.log and stderr to {outputDir}/sim.err
- If a simulation run exits with non-zero code, print WARNING but continue
- Use $(nproc) to detect CPU count and limit parallel jobs to nproc/2
- All paths relative to project root (5g-rrc-research/)
```

---

## Agent 4 — Statistics Analyst [SEQUENTIAL — after Experiment runs complete]

**Responsibility:** Python analysis pipeline, statistical tests, publication figures  
**Output files:** `python/parse_results.py`, `python/plot_results.py`, `python/stats.py`  
**Estimated time:** Week 3–4

### Copilot prompt — paste into Chat window 4:

```
@workspace You are Agent 4: Statistics Analyst for the ARSTA project.
Read .github/copilot-instructions.md for full project context.

TASK 1 — Create python/parse_results.py
This script aggregates all raw simulation output into clean DataFrames.

Required functions:

def parse_rrc_log(filepath: str) -> pd.DataFrame:
    """
    Parse ns-3 RRC state CSV. Columns: time_s,imsi,cell_id,old_state,new_state
    Add computed columns:
    - state_name: map {5:'RRC_IDLE', 9:'RRC_CONNECTED', 99:'RRC_INACTIVE', else:'TRANSITION'}
    - dwell_ms: time until next transition for that UE (shift by 1 per IMSI group)
    Return sorted by (imsi, time_s)
    """

def parse_flow_monitor(xml_path: str) -> pd.DataFrame:
    """
    Parse FlowMonitor XML. Return DataFrame with columns:
    flow_id, src_ip, dst_ip, tx_packets, rx_packets,
    throughput_mbps, mean_delay_ms, jitter_ms, loss_pct
    """

def load_experiment(exp_dir: str, scheme: str) -> dict:
    """
    Load all seeds for one experiment+scheme combination.
    exp_dir: e.g. "results/raw/EXP1_timer10"
    scheme: "baseline" or "arsta"
    Returns: {
      'rrc': pd.DataFrame,           # concatenated all seeds
      'flows': pd.DataFrame,         # concatenated all seeds
      'energy_per_seed': list[float],# one value per seed (mJ averaged over UEs)
      'transitions_per_seed': list[int]
    }
    """

def summarise(values: list) -> dict:
    """Return {mean, std, ci_low, ci_high} using scipy.stats.t.interval at 95%"""

def compare_schemes(baseline_vals: list, arsta_vals: list) -> dict:
    """
    Welch t-test. Return:
    {reduction_pct, p_value, significant (bool, p<0.05),
     baseline_mean, arsta_mean, baseline_ci, arsta_ci}
    """

Add __main__ block:
- Load EXP-1 results for baseline and arsta
- Print comparison table to stdout
- Save processed/exp1_summary.csv

TASK 2 — Create python/stats.py
Full statistical analysis across all 5 experiments.

Must produce results/processed/full_results_table.csv with columns:
experiment, config_value, scheme, energy_mean_mj, energy_ci_low, energy_ci_high,
reduction_pct, p_value, significant, transitions_mean, throughput_mean_mbps,
paging_success_pct, ho_success_pct

TASK 3 — Create python/plot_results.py
IEEE-format publication figures. Use these exact settings at the top:

import matplotlib
matplotlib.rcParams.update({
    'font.family': 'Times New Roman',
    'font.size': 11,
    'axes.labelsize': 12,
    'legend.fontsize': 10,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.dpi': 300,
    'savefig.bbox': 'tight',
    'pdf.fonttype': 42
})

SCHEME_COLORS = {
    'Baseline (3GPP)': '#E24B4A',
    'ARSTA (Proposed)': '#1D9E75',
    '5GSaver [1]':      '#378ADD',
    'Khlass et al. [2]':'#EF9F27'
}

Create these 6 functions (one per required figure):

def fig1_energy_cdf(data: dict, save_path: str):
    """CDF of per-UE energy consumption. X=energy mJ, Y=CDF 0–1.
    One line per scheme. Figure size (3.5, 2.8) inches (IEEE single column).
    Add vertical dashed line at baseline mean with annotation '5GSaver baseline'.
    """

def fig2_state_dwell_bar(data: dict, save_path: str):
    """Stacked bar: fraction of time in IDLE/INACTIVE/CONNECTED per scheme.
    Group bars by scheme. Colours: IDLE=gray, INACTIVE=blue, CONNECTED=coral.
    """

def fig3_energy_vs_velocity(data: dict, save_path: str):
    """Line plot: energy mJ vs UE speed (0,3,10,30 m/s).
    One line per scheme. Error bars = 95% CI. X-axis log scale.
    """

def fig4_energy_vs_traffic(data: dict, save_path: str):
    """Bar chart: energy mJ for low/medium/high traffic per scheme.
    Annotate reduction % above each ARSTA bar.
    """

def fig5_paging_success_rate(data: dict, save_path: str):
    """Line: paging success rate % vs UE speed. Target line at 99% dashed.
    """

def fig6_ho_latency_cdf(data: dict, save_path: str):
    """CDF of handover latency ms. Compare baseline vs ARSTA.
    Add annotation: 'ARSTA adds Xms HO locking overhead'.
    """

def table2_comparison(data: dict, save_path: str):
    """
    Save LaTeX table to save_path (.tex file).
    Columns: Method | Energy(mJ) | Reduction% | Transitions/UE/hr |
             Paging% | HO Latency(ms) | Throughput(Mbps)
    Rows: Baseline(3GPP) | 5GSaver[1] | Khlass[2] | ARSTA(Proposed)
    Bold the ARSTA row. Use booktabs formatting.
    """

Add __main__ block that generates all 6 figures from processed results
and saves to results/figures/fig{N}_{name}.pdf
```

---

## Agent 5 — MATLAB Validator [PARALLEL with Agent 4]

**Responsibility:** Markov chain analytical model, ns-3 result validation  
**Output files:** `matlab/energy_analytical.m`, `matlab/validate_ns3.m`  
**Estimated time:** Week 3–4

### Copilot prompt — paste into Chat window 5:

```
@workspace You are Agent 5: MATLAB Validator for the ARSTA project.
Read .github/copilot-instructions.md for full project context.

TASK 1 — Create matlab/energy_analytical.m
Build a discrete-time Markov chain analytical energy model.

States: IDLE(1), INACTIVE(2), CONNECTED(3)
Power (mW): P = [5, 15, 900]

Transition matrix P_base (3GPP baseline, inactivity_timer=10s, mean_iat=8s):
% Empirically derived from Kotaba et al. GLOBECOM 2022 queuing model
% P(IDLE→CONNECTED) = packet arrival rate * Δt
% P(CONNECTED→INACTIVE/IDLE) = 1/inactivity_timer * Δt
% Adjust for ARSTA: P(CONNECTED→INACTIVE) increases by EWMA factor

Function signature:
function [energy_mw, state_dist] = compute_energy(P_matrix, dt, T_sim)
% P_matrix: 3x3 transition probability matrix
% dt: time step in seconds (use 0.1)
% T_sim: simulation duration (300)
% Returns: mean power in mW, steady-state distribution vector

function P = build_transition_matrix(lambda_pkt, mu_inact, alpha_ewma, scheme)
% lambda_pkt: packet arrival rate (packets/s)
% mu_inact: 1/inactivity_timer
% alpha_ewma: EWMA smoothing factor (0 for baseline, 0.3 for ARSTA)
% scheme: 'baseline' or 'arsta'

% For ARSTA: increase P(CONNECTED→INACTIVE) by factor (1 + alpha_ewma * 2)
% This models the early-trigger effect of traffic prediction

function [energy_reduction, p_value] = compare_schemes(lambda_vals, mu_inact)
% Sweep lambda_pkt over [0.1, 0.5, 1.0, 2.0, 5.0] packets/s
% For each lambda: compute energy for baseline and ARSTA
% Return array of reduction percentages

Generate a figure:
subplot(2,2,1): Energy vs lambda_pkt (baseline vs ARSTA)
subplot(2,2,2): State distribution pie chart for ARSTA at lambda=0.5
subplot(2,2,3): Energy reduction % vs inactivity_timer (5,10,20,30s)
subplot(2,2,4): Energy reduction % vs EWMA alpha (0.1,0.3,0.5,0.7)
Save as: results/figures/analytical_model.pdf (use exportgraphics)

TASK 2 — Create matlab/validate_ns3.m
Load ns-3 CSV results and compare against analytical predictions.

function validate(ns3_results_dir, analytical_results)
% Load results/processed/full_results_table.csv
% For each experiment: compare ns3 energy_mean vs analytical prediction
% Compute RMSE and R^2
% Print validation table:
%   Config | NS3 Energy | Analytical | RMSE | R^2 | Status

Accept deviation < 15% as PASS, flag > 15% as WARNING.
Generate scatter plot: ns3_energy vs analytical_energy with 1:1 line.
Save as results/figures/validation_scatter.pdf

Add at the top of both files:
% ARSTA Project - Analytical Model
% Reference: Kotaba et al., IEEE GLOBECOM 2022, DOI 10.1109/GLOBECOM48099.2022.9977764
% Power model: 3GPP TR 38.840 V16.0.0
```

---

## Agent 6 — Paper Writer [SEQUENTIAL — after Agent 4 figures are complete]

**Responsibility:** IEEE paper LaTeX skeleton, all sections, bibliography  
**Output files:** `paper/main.tex`, `paper/references.bib`, `paper/arsta_algorithm.tex`  
**Estimated time:** Week 4–5

### Copilot prompt — paste into Chat window 6:

```
@workspace You are Agent 6: Paper Writer for the ARSTA project.
Read .github/copilot-instructions.md for full project context.

Target venue: IEEE WCNC 2026 (camera-ready format) or IEEE Transactions on Wireless Communications
Page limit: 6 pages (conference) or 14 pages (journal)
Format: IEEE two-column, Times New Roman 10pt

TASK 1 — Create paper/main.tex
Full IEEE paper skeleton with all sections populated with real content.
Use \documentclass[conference]{IEEEtran}

Sections to include with placeholder content ready to fill:

\section{Introduction}
Write 4 paragraphs:
P1: 5G NR battery drain context — cite [1] for the problem scale
P2: RRC state machine — cite [2] (Hoglund 2019) and 3GPP TS 38.331 [S1]
P3: Gap statement — cite [3] (García-Martínez survey 2024) for the specific gap:
    "combining traffic prediction with INACTIVE exploitation remains an open problem [3]"
P4: Contributions list (use \begin{enumerate}\item...\end{enumerate}):
    1. ARSTA algorithm with 4 co-designed modules (first to combine all 4)
    2. Custom RRC_INACTIVE implementation in open-source ns-3 5G-LENA
    3. X\% energy reduction vs 5GSaver [base paper] and Y\% vs Khlass et al. [2]
    4. Statistical validation across 5 experiments, 10 seeds, 95\% CI

\section{Background \& Related Work}
Subsections:
2A: 5G NR RRC State Machine — cite [S1] (TS 38.331), [2] (Hoglund), explain IDLE/INACTIVE/CONNECTED
2B: DRX Mechanism — cite [4] (Lin COMST 2023 survey)
2C: Related Work table using \begin{table} comparing:
    5GSaver[1] | Khlass[2] | Lin Survey[4] | Ma et al.[8] | ARSTA
    Rows: Traffic-aware | Mobility-aware | HO-aware | Paging | INACTIVE | ns-3 sim

\section{System Model}
Subsections:
3A: Network topology — describe 3-gNB triangle, UE distribution
3B: Channel model — cite TR 38.901 [S5], state "UMa scenario, σ=4/6dB LoS/NLoS"
3C: UE energy model — cite TR 38.840 [S2], include \begin{table} with power values
3D: Traffic model — describe bursty Poisson OnOff, justify with real app measurements

\section{ARSTA Algorithm}
Include paper/arsta_algorithm.tex via \input{}
Subsections:
4A: System overview — describe 4 modules, include \begin{figure} placeholder for block diagram
4B: Module 1 Traffic Prediction — write EWMA equation:
    \hat{\tau}_{n} = \alpha \cdot \tau_n + (1-\alpha) \cdot \hat{\tau}_{n-1}
    Derive optimal alpha using MSE minimisation
4C: Module 2 DRX Tuning — write piecewise DRX function with cases environment
4D: Module 3 HO-Aware Locking — write gradient detection equation
4E: Module 4 Paging Optimisation — RNA area sizing function
4F: Complexity analysis — state O(1) per packet for all modules

\section{Simulation Setup}
Include \begin{table*} with ALL parameters (2-column wide table)
State baseline algorithms compared: (1) 3GPP static timer, (2) 5GSaver approximation
State: "10 independent runs per configuration, 95\% CI reported"

\section{Results}
Use \begin{figure*} for double-column figures
Subsections: one per figure (fig1–fig6)
Each: describe what the figure shows, state the key number
e.g. "Fig.~\ref{fig:energy_cdf} shows ARSTA reduces median energy by X\% vs baseline"
Include \input{paper/table2.tex} for comparison table

\section{Conclusion}
4 sentences:
1. Problem restated
2. ARSTA approach summary
3. Key results (use placeholder \textbf{XX\%})
4. Future work: O-RAN xApp deployment, LSTM-based HO prediction, joint UE+network optimisation

TASK 2 — Create paper/references.bib
Include ALL 12 references from the project in proper BibTeX format.
Key entries (write all 12):
@article{Ding2024, author={Z. Ding and Y. Lin and W. Xu and J. Lv and Y. Gao and W. Dong},
  title={Energy Optimization for Mobile Applications by Exploiting 5G Inactive State},
  journal={IEEE Trans. Mobile Comput.}, volume={23}, number={12}, year={2024},
  doi={10.1109/TMC.2024.3377696}}

@inproceedings{Khlass2019, ... doi={10.1109/VTCFall.2019.8891551}}
@article{Hoglund2019, ... doi={10.1109/MCOM.2018.1700957}}
@article{LinSurvey2023, ... doi={10.1109/COMST.2022.3217854}}
@article{IslamJSAC2023, ... doi={10.1109/JSAC.2023.3271241}}
@inproceedings{Raghunath2022, ... doi={10.1109/GLOBECOM48099.2022.10000873}}
@inproceedings{WCNC2023HO, ... doi={10.1109/WCNC55385.2023.10060203}}
@article{Ma2024, ... doi={10.1016/j.dcan.2024.07.005}}
@article{Quek2021, ... doi={10.1109/LCOMM.2021.3098069}}
@inproceedings{Polese2021, ... doi={10.1145/3460797.3460805}}
@techreport{3GPPTS38331, author={{3GPP}}, title={{TS 38.331 V18.3.0}}, year={2024}}
@techreport{3GPPTR38840, author={{3GPP}}, title={{TR 38.840 V16.0.0}}, year={2019}}

TASK 3 — Create paper/arsta_algorithm.tex
Write the full ARSTA pseudocode using \begin{algorithm} (algorithmicx package):

Algorithm 1: ARSTA State Decision (called every inactivity timer tick)
Input: UE context (ewma_iat, velocity, rsrp_gradient, current_state, ho_lock_expiry)
Output: new_state, drx_cycle_ms, rna_size

Pseudocode must match python/arsta.py ARSTASimulator.step() exactly.
```

---

## Agent coordination rules

```
RULE 1 — Shared state:
All agents write to the same git repo. Commit after each task.
git add -A && git commit -m "Agent N: task description"

RULE 2 — Blocking dependencies:
Agent 3 (experiments) CANNOT start until Agent 1 baseline.cc compiles and runs.
Agent 4 (analysis) CANNOT start until at least EXP-1 results exist.
Agent 6 (paper) CANNOT start until Agent 4 has produced at least fig1 and fig3.
Agents 2 and 5 are PARALLEL — start them immediately alongside Agent 1.

RULE 3 — Error handling:
If any agent produces code that throws an error, paste the full error message
back into that agent's Copilot Chat window with: "Fix this error: [paste error]"
Do not move to the next agent until the current agent's code runs.

RULE 4 — Integration check:
After Agent 1 and Agent 2 are both done, run:
  python python/test_arsta.py -v
  ./ns3 run "scratch/5g-rrc-arsta --simTime=10 --rngRun=1 --outputDir=results/raw/test/"
  python python/energy_model.py
All three must succeed before Agent 3 starts experiments.

RULE 5 — Result verification:
After each experiment batch, run:
  python python/parse_results.py results/raw/EXP{N}*/
Verify: (a) CSV files exist for all seeds, (b) no NaN in energy column,
(c) ARSTA runs have custom_state column with INACTIVE entries (value=99).
```

---

## Week-by-week delivery checklist

### Week 1
- [ ] `scripts/install_deps.sh` runs without error
- [ ] `cttc-nr-demo` passes on local machine
- [ ] `ns3/scratch/5g-rrc-baseline.cc` compiles and runs for 10s
- [ ] `python/arsta.py` unit tests all pass
- [ ] `python/energy_model.py` produces sensible energy values on synthetic data

### Week 2
- [ ] `ns3/scratch/5g-rrc-arsta.cc` compiles and runs for 10s
- [ ] ARSTA CSV output contains `custom_state`, `ewma_iat`, `drx_cycle_ms` columns
- [ ] EXP-1 and EXP-2 complete (160 simulation runs total)
- [ ] First energy comparison: ARSTA vs baseline visible in output

### Week 3
- [ ] EXP-3 through EXP-5 complete (180 more runs)
- [ ] `matlab/energy_analytical.m` runs and produces figure
- [ ] `python/parse_results.py` loads all results without error
- [ ] `full_results_table.csv` generated

### Week 4
- [ ] All 6 publication figures generated in `results/figures/`
- [ ] ARSTA shows energy reduction > 9.5% vs baseline (beat base paper minimum)
- [ ] p < 0.05 for all primary comparisons
- [ ] MATLAB validation shows < 15% deviation from ns-3

### Week 5
- [ ] `paper/main.tex` compiles to PDF without errors
- [ ] All figures referenced in paper
- [ ] Abstract written with real numbers filled in
- [ ] Paper sent to guide for review

---

## Quick commands reference

```bash
# Build ns-3 with NR module
cd ~/ns-3-dev && ./ns3 build

# Run baseline for 10 seconds (quick test)
./ns3 run "scratch/5g-rrc-baseline --simTime=10 --rngRun=1 --outputDir=results/raw/test/"

# Run ARSTA for 10 seconds
./ns3 run "scratch/5g-rrc-arsta --simTime=10 --rngRun=1 --outputDir=results/raw/test/ --ewmaAlpha=0.3"

# Run all experiments (background, takes hours)
nohup bash scripts/run_all.sh > run_all.log 2>&1 &

# Check simulation progress
tail -f run_all.log

# Run Python analysis after experiments
python python/parse_results.py
python python/stats.py
python python/plot_results.py

# Run MATLAB validation (from MATLAB command window)
cd matlab && energy_analytical && validate_ns3

# Unit tests
pytest python/test_arsta.py -v

# Compile paper
cd paper && pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```
