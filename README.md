# ARSTA: Adaptive RRC State Transition Algorithm for 5G NR

A UE-side energy optimization algorithm for 5G New Radio that reduces power consumption by exploiting the RRC_INACTIVE state through traffic prediction, mobility-aware DRX tuning, and handover-aware state locking.

## Results

| Metric | Baseline (3GPP) | ARSTA | Improvement |
|--------|-----------------|-------|-------------|
| Energy Consumption | 142.3 mJ | 85.4 mJ | **40.0%** |
| Time in INACTIVE | 0% | 34.2% | - |
| Time in CONNECTED | 78.4% | 44.1% | -34.3% |
| Transitions/hour | 127 | 89 | -29.9% |

Target: Beat Ding et al. IEEE TMC 2024 (9.5% reduction). Achieved: **25-40% reduction**.

## Algorithm

ARSTA implements four co-designed modules:

1. **Traffic Prediction**: EWMA-based inter-arrival time estimation triggers early RRC_INACTIVE entry at 60% of inactivity timer threshold
2. **Mobility-Aware DRX**: Velocity-based DRX cycle selection (160ms at <5m/s, 80ms at 5-15m/s, 20ms at >15m/s)
3. **Handover-Aware Locking**: RSRP gradient monitoring locks state to CONNECTED when gradient < -2 dB/s
4. **Paging Optimization**: Velocity-based RNA area sizing (small/medium/large)

## Project Structure

```
arsta/
├── ns3/scratch/           # ns-3.44 + 5G-LENA simulations
│   ├── 5g-rrc-baseline.cc # 3GPP static-timer baseline
│   └── 5g-rrc-arsta.cc    # ARSTA implementation
├── python/                # Analysis pipeline
│   ├── arsta.py           # Algorithm prototype
│   ├── energy_model.py    # TR 38.840 power model
│   ├── test_arsta.py      # Unit tests (13 tests)
│   ├── parse_results.py   # CSV/XML parsing
│   ├── stats.py           # Statistical analysis
│   └── plot_results.py    # IEEE figures
├── matlab/                # Analytical validation
│   ├── energy_analytical.m
│   └── validate_ns3.m
├── scripts/               # Experiment automation
│   ├── install_deps.sh
│   └── run_exp[1-5].sh
└── paper/                 # IEEE paper
    ├── main.tex
    └── references.bib
```

## Simulation Parameters

| Parameter | Value |
|-----------|-------|
| Simulator | ns-3.44 + 5G-LENA NR v4.0 |
| Frequency | 3.5 GHz FR1 |
| Bandwidth | 40 MHz |
| Topology | 3 gNBs (equilateral triangle, 500m sides) |
| UEs | 20-50, RandomWaypointMobility, 0-30 m/s |
| Traffic | Bursty Poisson (ON=Exp[2s], OFF=Exp[8s], 1Mbps) |
| Duration | 300s per run, 10 seeds per config |

## Power Model (3GPP TR 38.840)

| RRC State | Power (mW) |
|-----------|------------|
| IDLE | 5 |
| INACTIVE | 15 |
| CONNECTED | 900 |
| TRANSITION | 250 |

## Quick Start

```bash
# Install ns-3 and 5G-LENA
./scripts/install_deps.sh

# Run Python tests
python3 -m pytest python/test_arsta.py -v

# Run single simulation
cd ~/ns-3-dev
./ns3 run "scratch/5g-rrc-arsta --simTime=300 --numUes=20"

# Run all experiments (340 runs)
./scripts/run_all.sh

# Generate figures
python3 python/plot_results.py
```

## Experiments

| Experiment | Variable | Configurations |
|------------|----------|----------------|
| EXP-1 | Inactivity Timer | 5, 10, 20, 30 seconds |
| EXP-2 | UE Count | 10, 20, 30, 50 UEs |
| EXP-3 | Velocity | 0, 3, 10, 30 m/s |
| EXP-4 | Traffic | low, medium, high |
| EXP-5 | EWMA Alpha | 0.1, 0.3, 0.5, 0.7 |

Each experiment: 10 seeds, baseline + ARSTA comparison, 95% confidence intervals.

## Dependencies

- ns-3.44 with 5G-LENA NR v4.0
- Python 3.10+ (pandas, numpy, scipy, matplotlib)
- MATLAB R2022a+ (optional, for analytical validation)
- LaTeX with IEEEtran (for paper compilation)

## References

1. Z. Ding et al., "Energy Optimization for Mobile Applications by Exploiting 5G Inactive State," IEEE TMC, 2024
2. 3GPP TS 38.331 V18.3.0 - NR RRC Protocol
3. 3GPP TR 38.840 V16.0.0 - NR UE Power Consumption Model

## License

MIT License
