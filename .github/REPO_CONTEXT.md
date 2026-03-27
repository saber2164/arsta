# ARSTA Repository Context

> **Purpose**: Complete reference for the ARSTA project structure. Use this instead of exploring the repo each time.

**Project**: Adaptive RRC State Transition Algorithm for 5G NR UE Energy Optimisation  
**Target**: Beat Ding et al. IEEE TMC 2024 (9.5% energy reduction) → achieve 25–35%  
**Simulator**: ns-3.44 + 5G-LENA NR v4.0

---

## Directory Structure

```
arsta/
├── .github/
│   ├── copilot-instructions.md   # Global project context (37 lines)
│   └── REPO_CONTEXT.md           # THIS FILE - full repo reference
├── ns3/scratch/
│   ├── 5g-rrc-baseline.cc        # 3GPP static-timer baseline (493 lines)
│   └── 5g-rrc-arsta.cc           # ARSTA implementation (1054 lines)
├── python/
│   ├── arsta.py                  # Python ARSTA algorithm (543 lines)
│   ├── energy_model.py           # TR 38.840 power model (373 lines)
│   ├── test_arsta.py             # pytest tests - 13 tests (307 lines)
│   ├── parse_results.py          # CSV/XML parsing (461 lines)
│   ├── stats.py                  # Statistical analysis (565 lines)
│   └── plot_results.py           # IEEE figures (530 lines)
├── matlab/
│   ├── energy_analytical.m       # Markov chain model (301 lines)
│   └── validate_ns3.m            # ns-3 vs analytical validation (442 lines)
├── scripts/
│   ├── install_deps.sh           # ns-3 + 5G-LENA installer (194 lines)
│   ├── run_exp1.sh               # Inactivity timer sweep (99 lines)
│   ├── run_exp2.sh               # UE count scalability (95 lines)
│   ├── run_exp3.sh               # Velocity sweep (97 lines)
│   ├── run_exp4.sh               # Traffic intensity (97 lines)
│   ├── run_exp5.sh               # EWMA alpha tuning (89 lines)
│   └── run_all.sh                # Master experiment runner (161 lines)
├── paper/
│   ├── main.tex                  # IEEE WCNC paper (528 lines)
│   ├── references.bib            # 12 BibTeX entries (142 lines)
│   └── arsta_algorithm.tex       # Algorithm pseudocode (196 lines)
├── results/
│   ├── raw/                      # Simulation CSV/XML output
│   ├── processed/                # Aggregated results
│   │   └── full_results_table.csv
│   └── figures/                  # Publication figures (PDF)
│       └── table2_comparison.tex
└── plan.md                       # Original execution plan
```

---

## File Details

### NS-3 Simulations (`ns3/scratch/`)

#### `5g-rrc-baseline.cc` — 3GPP Static Timer Baseline
- **Purpose**: Reference simulation with standard 3GPP inactivity timer
- **Key classes**: Uses `NrHelper`, `NrPointToPointEpcHelper`, `IdealBeamformingHelper`
- **Topology**: 3 gNBs at (0,0,25), (500,0,25), (250,433,25) — equilateral triangle 500m
- **UEs**: 20 default, `RandomWaypointMobility` 1-10 m/s
- **Traffic**: OnOff 1Mbps, ON=Exp[2s], OFF=Exp[8s]
- **Output**: RRC state CSV (`time_s,imsi,cell_id,old_state,new_state`), FlowMonitor XML
- **CLI args**: `--numUes`, `--simTime`, `--rngRun`, `--inactivityTimer`, `--outputDir`

#### `5g-rrc-arsta.cc` — ARSTA Algorithm Implementation
- **Purpose**: ARSTA with all 4 modules
- **Key class**: `UeRrcMonitor` with `UeState` struct
- **ARSTA Modules**:
  1. **Traffic Prediction**: EWMA (α=0.3), triggers INACTIVE at 60% of inactivity timer
  2. **Velocity-Aware DRX**: 160ms (<5m/s), 80ms (5-15m/s), 20ms (≥15m/s)
  3. **HO-Aware Locking**: Locks state when RSRP gradient < -2 dB/s
  4. **RNA Sizing**: small (<3m/s), medium (3-15m/s), large (≥15m/s)
- **Extended output**: Adds `custom_state,ewma_iat,velocity,drx_cycle_ms,ho_locked,rna_size`
- **Extra CLI args**: `--ewmaAlpha`, `--hoLockThreshold`

### Python (`python/`)

#### `arsta.py` — Python ARSTA Prototype
- **Classes**: `RRCState` (enum), `UEContext` (dataclass), `ARSTASimulator`
- **Key methods**:
  - `update_ewma(ctx, iat)` → updates EWMA estimate
  - `should_enter_inactive(ctx)` → traffic prediction trigger
  - `get_drx_cycle_ms(velocity)` → DRX selection
  - `update_ho_lock(ctx, time)` → HO gradient check
  - `step(ctx, event, time)` → main event processor
  - `run_trace(events, ue_count)` → full simulation
- **Demo**: `if __name__ == "__main__"` runs 5 UEs for 60s

#### `energy_model.py` — TR 38.840 Power Model
- **Constants**: `POWER_MW = {IDLE: 5, INACTIVE: 15, CONNECTED: 900, TRANSITION: 250}`
- **State mapping**: ns-3 states → power (5→IDLE, 9→CONNECTED, 99→INACTIVE)
- **Key methods**:
  - `compute_session_energy_mj(df)` → total energy from state trace
  - `compute_state_ratios(df)` → time % in each state
  - `energy_reduction_pct(baseline, arsta)` → savings %
  - `transition_count(df)` → counts state transitions

#### `test_arsta.py` — Unit Tests (13 tests, all pass)
- `TestEWMAConvergence` — verifies EWMA converges to mean
- `TestInactiveTrigger` — early INACTIVE at 60% threshold
- `TestHandoverLock` — lock at gradient < -2 dB/s
- `TestDRXBoundaries` — velocity thresholds 5/15 m/s
- `TestEnergyReduction` — ARSTA saves ≥5% vs baseline
- `TestIntegration` — full workflow tests

#### `parse_results.py` — Data Loading
- `parse_rrc_log(filepath)` → DataFrame with `state_name`, `dwell_ms`
- `parse_flow_monitor(xml_path)` → throughput, delay, jitter, loss
- `load_experiment(exp_dir, scheme)` → concatenated seeds
- `summarise(values)` → mean, std, 95% CI
- `compare_schemes(baseline, arsta)` → Welch t-test

#### `stats.py` — Statistical Analysis
- Produces `results/processed/full_results_table.csv`
- Columns: experiment, config_value, scheme, energy metrics, p-value, significance
- Generates mock data if no real results exist

#### `plot_results.py` — IEEE Figures
- **Settings**: Times New Roman, 300 DPI, PDF output
- **Figures**:
  1. `fig1_energy_cdf` — per-UE energy CDF
  2. `fig2_state_dwell_bar` — stacked bar IDLE/INACTIVE/CONNECTED
  3. `fig3_energy_vs_velocity` — line plot with 95% CI
  4. `fig4_energy_vs_traffic` — grouped bar low/medium/high
  5. `fig5_paging_success_rate` — vs velocity with 99% target
  6. `fig6_ho_latency_cdf` — handover latency
  7. `table2_comparison` — LaTeX table

### MATLAB (`matlab/`)

#### `energy_analytical.m` — Markov Chain Model
- **States**: IDLE(1), INACTIVE(2), CONNECTED(3)
- **Functions**:
  - `compute_energy(P, dt, T)` → mean power, steady-state distribution
  - `build_transition_matrix(λ, μ, α, scheme)` → 3×3 matrix
  - `compare_schemes(λ_vals, μ)` → reduction % array
- **Output**: 4-subplot figure → `results/figures/analytical_model.pdf`

#### `validate_ns3.m` — Cross-Validation
- Compares ns-3 results vs analytical predictions
- RMSE, R² metrics; PASS if deviation <15%
- **Output**: `results/figures/validation_scatter.pdf`

### Scripts (`scripts/`)

| Script | Experiment | Variable | Total Runs |
|--------|------------|----------|------------|
| `run_exp1.sh` | Inactivity Timer | 5,10,20,30s | 80 |
| `run_exp2.sh` | UE Scalability | 10,20,30,50 UEs | 80 |
| `run_exp3.sh` | Velocity | 0,3,10,30 m/s | 80 |
| `run_exp4.sh` | Traffic | low/medium/high | 60 |
| `run_exp5.sh` | EWMA Alpha | 0.1,0.3,0.5,0.7 | 40 (ARSTA only) |
| `run_all.sh` | Master | All experiments | 340 total |

**Common features**:
- Parallel execution (nproc/2 jobs)
- Output: `results/raw/EXP{N}_{config}_seed{S}/`
- Logs: `sim.log`, `sim.err` per run

### Paper (`paper/`)

#### `main.tex` — IEEE WCNC 2026 Paper
- 6-page conference format
- Sections: Intro, Background, System Model, ARSTA Algorithm, Setup, Results, Conclusion
- `\input{arsta_algorithm.tex}` for pseudocode
- All 12 references cited

#### `references.bib` — Bibliography
Key entries:
- `Ding2024` — Base paper (IEEE TMC)
- `Khlass2019` — VTC comparison
- `Hoglund2019` — RRC background
- `LinSurvey2023` — DRX survey
- `3GPPTS38331`, `3GPPTR38840` — Standards

#### `arsta_algorithm.tex` — Pseudocode
- Algorithm 1: ARSTA State Decision
- Algorithm 2: EWMA Update
- Algorithm 3: RSRP Gradient Update

---

## Key Parameters & Constants

### Power Model (3GPP TR 38.840)
| State | Power (mW) | ns-3 Code |
|-------|------------|-----------|
| RRC_IDLE | 5 | 5 |
| RRC_INACTIVE | 15 | 99 (custom) |
| RRC_CONNECTED | 900 | 9 |
| TRANSITION | 250 | other |

### ARSTA Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| ewmaAlpha | 0.3 | EWMA smoothing factor |
| inactiveThreshold | 0.6 | Fraction of inactivity timer |
| hoLockThreshold | -2.0 dB/s | RSRP gradient trigger |
| DRX low velocity | <5 m/s | 160ms cycle |
| DRX medium velocity | 5-15 m/s | 80ms cycle |
| DRX high velocity | ≥15 m/s | 20ms cycle |

### Simulation Defaults
| Parameter | Value |
|-----------|-------|
| numUes | 20 |
| simTime | 300s |
| inactivityTimer | 10s |
| Frequency | 3.5 GHz FR1 |
| Bandwidth | 40 MHz |
| gNB TxPower | 43 dBm |
| Seeds per config | 10 |

---

## Quick Commands

```bash
# Run Python tests
python3 -m pytest python/test_arsta.py -v

# Run Python modules standalone
python3 python/arsta.py
python3 python/energy_model.py
python3 python/stats.py
python3 python/plot_results.py

# Install ns-3 (first time)
./scripts/install_deps.sh

# Run single simulation (after ns-3 installed)
cd ~/ns-3-dev
./ns3 run "scratch/5g-rrc-baseline --simTime=10 --rngRun=1"
./ns3 run "scratch/5g-rrc-arsta --simTime=10 --ewmaAlpha=0.3"

# Run all experiments (hours)
./scripts/run_all.sh

# Compile paper
cd paper && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

---

## Dependencies

### Python
- pandas, numpy, scipy, matplotlib
- pytest (for tests)

### ns-3
- ns-3.44 + 5G-LENA NR v4.0
- g++, cmake, ninja-build, libsqlite3-dev

### MATLAB
- Statistics Toolbox (for validation)

### LaTeX
- IEEEtran class, algorithmicx, booktabs

---

## File Relationships

```
copilot-instructions.md ─┬─► All agents read this for context
                         │
arsta.py ◄───────────────┼─► test_arsta.py (tests it)
    │                    │
    └───────────────────►│ arsta_algorithm.tex (LaTeX version)
                         │
energy_model.py ◄────────┼─► parse_results.py (uses EnergyModel)
                         │        │
                         │        ▼
                         │   stats.py ─► full_results_table.csv
                         │        │
                         │        ▼
                         │   plot_results.py ─► figures/*.pdf
                         │
5g-rrc-baseline.cc ──────┼─► 5g-rrc-arsta.cc (extends it)
                         │        │
                         │        ▼
                         │   run_exp*.sh ─► results/raw/
                         │
energy_analytical.m ─────┴─► validate_ns3.m (uses functions)

main.tex ◄─── references.bib + arsta_algorithm.tex
```

---

*Last updated: 2026-03-27*
