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
