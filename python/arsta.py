#!/usr/bin/env python3
"""
ARSTA: Adaptive RRC State Transition Algorithm for 5G NR UE Energy Optimization

This Python implementation validates algorithm logic before C++ integration
and enables parameter sensitivity analysis without recompiling.

Modules:
1. Traffic Prediction: EWMA of inter-packet arrival times
2. Mobility-Aware DRX: velocity-based DRX cycle selection
3. Handover-Aware Locking: RSRP gradient monitoring
4. Paging Optimization: velocity-based RNA sizing
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import IntEnum


class RRCState(IntEnum):
    """RRC states with power consumption (mW) from 3GPP TR 38.840"""
    IDLE = 0        # 5 mW
    INACTIVE = 1    # 15 mW
    CONNECTED = 2   # 900 mW


# Power consumption in mW for each state
POWER_MW = {
    RRCState.IDLE: 5.0,
    RRCState.INACTIVE: 15.0,
    RRCState.CONNECTED: 900.0,
}
TRANSITION_POWER_MW = 250.0


@dataclass
class UEContext:
    """UE state context for ARSTA algorithm"""
    imsi: int
    ewma_iat: float = 0.0           # seconds (EWMA of inter-arrival times)
    velocity: float = 0.0           # m/s
    rsrp_history: List[float] = field(default_factory=list)  # last 5 RSRP readings (dBm)
    rsrp_gradient: float = 0.0      # dB/s
    custom_state: int = RRCState.CONNECTED
    ho_locked: bool = False
    ho_lock_expiry: float = 0.0     # simulation time when lock expires
    last_packet_time: float = 0.0   # timestamp of last packet


class ARSTASimulator:
    """
    ARSTA Algorithm Simulator
    
    Implements the Adaptive RRC State Transition Algorithm with:
    - Traffic prediction via EWMA
    - Mobility-aware DRX cycle selection
    - Handover-aware state locking
    - Velocity-based RNA sizing
    """
    
    def __init__(self, alpha: float = 0.3, inactive_threshold: float = 0.6,
                 ho_lock_threshold: float = -2.0, inactivity_timer: float = 10.0):
        """
        Initialize ARSTA simulator.
        
        Args:
            alpha: EWMA smoothing factor (0 < alpha < 1)
            inactive_threshold: Fraction of inactivity_timer to trigger INACTIVE
            ho_lock_threshold: RSRP gradient threshold (dB/s) to lock handover
            inactivity_timer: Standard 3GPP inactivity timer (seconds)
        """
        self.alpha = alpha
        self.inactive_threshold = inactive_threshold
        self.ho_lock_threshold = ho_lock_threshold
        self.inactivity_timer = inactivity_timer
    
    def update_ewma(self, ctx: UEContext, iat_seconds: float) -> float:
        """
        Update Exponentially Weighted Moving Average of inter-arrival times.
        
        Formula: ewma = alpha * iat + (1 - alpha) * ewma
        
        Args:
            ctx: UE context to update
            iat_seconds: Current inter-arrival time in seconds
            
        Returns:
            Updated EWMA value
        """
        if ctx.ewma_iat == 0.0:
            # Initialize with first sample
            ctx.ewma_iat = iat_seconds
        else:
            ctx.ewma_iat = self.alpha * iat_seconds + (1 - self.alpha) * ctx.ewma_iat
        return ctx.ewma_iat
    
    def should_enter_inactive(self, ctx: UEContext) -> bool:
        """
        Determine if UE should transition to RRC_INACTIVE.
        
        Conditions:
        1. ewma_iat > inactivity_timer * inactive_threshold
        2. Not handover locked
        3. Currently in CONNECTED state
        
        Args:
            ctx: UE context
            
        Returns:
            True if UE should enter INACTIVE state
        """
        threshold = self.inactivity_timer * self.inactive_threshold
        return (ctx.ewma_iat > threshold and 
                not ctx.ho_locked and 
                ctx.custom_state == RRCState.CONNECTED)
    
    def get_drx_cycle_ms(self, velocity: float) -> int:
        """
        Get DRX cycle based on UE velocity.
        
        Mobility-aware DRX selection:
        - v < 5 m/s (stationary/pedestrian): 160 ms (long cycle, max savings)
        - 5 <= v < 15 m/s (urban vehicle): 80 ms (medium cycle)
        - v >= 15 m/s (highway): 20 ms (short cycle, quick response)
        
        Args:
            velocity: UE velocity in m/s
            
        Returns:
            DRX cycle in milliseconds
        """
        if velocity < 5.0:
            return 160
        elif velocity < 15.0:
            return 80
        else:
            return 20
    
    def update_ho_lock(self, ctx: UEContext, current_time: float) -> None:
        """
        Update handover lock status based on RSRP gradient.
        
        If RSRP is degrading rapidly (gradient < threshold), lock UE in
        CONNECTED state for a duration proportional to velocity.
        
        Lock duration: velocity * 10 ms
        
        Args:
            ctx: UE context to update
            current_time: Current simulation time
        """
        # Check if lock has expired
        if ctx.ho_locked and current_time >= ctx.ho_lock_expiry:
            ctx.ho_locked = False
            ctx.ho_lock_expiry = 0.0
        
        # Check if we should engage handover lock
        if ctx.rsrp_gradient < self.ho_lock_threshold and not ctx.ho_locked:
            ctx.ho_locked = True
            # Lock duration: velocity * 10ms (convert to seconds)
            lock_duration = ctx.velocity * 0.01  # 10ms per m/s
            ctx.ho_lock_expiry = current_time + max(lock_duration, 0.05)  # min 50ms
    
    def update_rsrp_gradient(self, ctx: UEContext, rsrp: float, 
                             timestamp: float, prev_timestamp: float) -> float:
        """
        Update RSRP history and compute gradient.
        
        Args:
            ctx: UE context
            rsrp: New RSRP reading in dBm
            timestamp: Current time
            prev_timestamp: Previous measurement time
            
        Returns:
            RSRP gradient in dB/s
        """
        ctx.rsrp_history.append(rsrp)
        if len(ctx.rsrp_history) > 5:
            ctx.rsrp_history.pop(0)
        
        if len(ctx.rsrp_history) >= 2:
            dt = timestamp - prev_timestamp
            if dt > 0:
                ctx.rsrp_gradient = (ctx.rsrp_history[-1] - ctx.rsrp_history[-2]) / dt
        
        return ctx.rsrp_gradient
    
    def get_rna_size(self, velocity: float) -> str:
        """
        Get RNA (RAN Notification Area) size based on velocity.
        
        Paging optimization:
        - v < 3 m/s (stationary): small RNA (fewer cells, less paging load)
        - 3 <= v < 15 m/s (mobile): medium RNA
        - v >= 15 m/s (fast): large RNA (reduce frequent RNA updates)
        
        Args:
            velocity: UE velocity in m/s
            
        Returns:
            RNA size category ('small', 'medium', 'large')
        """
        if velocity < 3.0:
            return 'small'
        elif velocity < 15.0:
            return 'medium'
        else:
            return 'large'
    
    def step(self, ctx: UEContext, event: dict, current_time: float) -> dict:
        """
        Process one simulation event.
        
        Args:
            ctx: UE context
            event: Event dictionary with keys:
                   - type: 'packet', 'rsrp_update', or 'velocity_update'
                   - value: float (packet size, RSRP dBm, or velocity m/s)
                   - timestamp: float (event time)
            current_time: Current simulation time
            
        Returns:
            Result dictionary with:
            - state_changed: bool
            - new_state: int
            - drx_ms: int
            - ho_locked: bool
            - rna_size: str
            - reason: str
        """
        result = {
            'state_changed': False,
            'new_state': ctx.custom_state,
            'drx_ms': self.get_drx_cycle_ms(ctx.velocity),
            'ho_locked': ctx.ho_locked,
            'rna_size': self.get_rna_size(ctx.velocity),
            'reason': ''
        }
        
        event_type = event.get('type', '')
        event_value = event.get('value', 0.0)
        event_time = event.get('timestamp', current_time)
        
        if event_type == 'packet':
            # Traffic prediction: update EWMA and check state transition
            if ctx.last_packet_time > 0:
                iat = event_time - ctx.last_packet_time
                self.update_ewma(ctx, iat)
            ctx.last_packet_time = event_time
            
            # Packet arrival: transition to CONNECTED if not already
            if ctx.custom_state != RRCState.CONNECTED:
                ctx.custom_state = RRCState.CONNECTED
                result['state_changed'] = True
                result['new_state'] = RRCState.CONNECTED
                result['reason'] = 'Packet arrival: INACTIVE/IDLE -> CONNECTED'
            else:
                result['reason'] = f'Packet processed, EWMA IAT={ctx.ewma_iat:.3f}s'
        
        elif event_type == 'rsrp_update':
            # Handover-aware locking: update RSRP and check gradient
            prev_time = ctx.rsrp_history[-1] if ctx.rsrp_history else event_time
            self.update_rsrp_gradient(ctx, event_value, event_time, 
                                      event_time - 0.1)  # Assume 100ms measurement interval
            self.update_ho_lock(ctx, current_time)
            
            result['ho_locked'] = ctx.ho_locked
            if ctx.ho_locked:
                result['reason'] = f'HO lock engaged (gradient={ctx.rsrp_gradient:.2f} dB/s)'
            else:
                result['reason'] = f'RSRP updated: {event_value:.1f} dBm'
        
        elif event_type == 'velocity_update':
            # Mobility-aware DRX: update velocity and recalculate parameters
            ctx.velocity = event_value
            result['drx_ms'] = self.get_drx_cycle_ms(ctx.velocity)
            result['rna_size'] = self.get_rna_size(ctx.velocity)
            result['reason'] = f'Velocity={ctx.velocity:.1f} m/s, DRX={result["drx_ms"]}ms'
        
        elif event_type == 'timer_tick':
            # Check if we should transition to INACTIVE based on traffic prediction
            self.update_ho_lock(ctx, current_time)  # Check HO lock expiry
            
            if self.should_enter_inactive(ctx):
                ctx.custom_state = RRCState.INACTIVE
                result['state_changed'] = True
                result['new_state'] = RRCState.INACTIVE
                result['reason'] = f'Early INACTIVE (EWMA={ctx.ewma_iat:.2f}s > threshold)'
        
        result['ho_locked'] = ctx.ho_locked
        return result
    
    def run_trace(self, events: list, ue_count: int = 20) -> pd.DataFrame:
        """
        Run full simulation from event list.
        
        Args:
            events: List of event dicts with 'ue_id', 'type', 'value', 'timestamp'
            ue_count: Number of UEs to simulate
            
        Returns:
            DataFrame with columns: timestamp, ue_id, state, drx_ms, ho_locked, 
                                   rna_size, ewma_iat, velocity, power_mw
        """
        # Initialize UE contexts
        contexts = {i: UEContext(imsi=i) for i in range(ue_count)}
        
        results = []
        
        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e.get('timestamp', 0))
        
        for event in sorted_events:
            ue_id = event.get('ue_id', 0)
            if ue_id not in contexts:
                continue
            
            ctx = contexts[ue_id]
            current_time = event.get('timestamp', 0)
            
            step_result = self.step(ctx, event, current_time)
            
            # Record state
            results.append({
                'timestamp': current_time,
                'ue_id': ue_id,
                'state': ctx.custom_state,
                'state_name': RRCState(ctx.custom_state).name,
                'drx_ms': step_result['drx_ms'],
                'ho_locked': ctx.ho_locked,
                'rna_size': step_result['rna_size'],
                'ewma_iat': ctx.ewma_iat,
                'velocity': ctx.velocity,
                'power_mw': POWER_MW[RRCState(ctx.custom_state)],
                'reason': step_result['reason']
            })
        
        return pd.DataFrame(results)


def generate_demo_trace(duration: float = 60.0, ue_count: int = 5, 
                        seed: int = 42) -> list:
    """
    Generate a demo event trace for testing.
    
    Args:
        duration: Simulation duration in seconds
        ue_count: Number of UEs
        seed: Random seed for reproducibility
        
    Returns:
        List of event dictionaries
    """
    np.random.seed(seed)
    events = []
    
    for ue_id in range(ue_count):
        # Generate bursty traffic (Poisson with ON/OFF periods)
        t = 0.0
        in_burst = True
        velocity = np.random.uniform(0, 20)  # Initial velocity
        rsrp = np.random.uniform(-90, -70)   # Initial RSRP
        
        while t < duration:
            if in_burst:
                # ON period: packets with small inter-arrival
                iat = np.random.exponential(0.5)  # Mean 500ms
                burst_duration = np.random.exponential(2.0)  # Mean 2s ON
                burst_end = t + burst_duration
                
                while t < burst_end and t < duration:
                    events.append({
                        'ue_id': ue_id,
                        'type': 'packet',
                        'value': 1500,  # Packet size
                        'timestamp': t
                    })
                    t += iat
                
                in_burst = False
            else:
                # OFF period: no packets
                off_duration = np.random.exponential(8.0)  # Mean 8s OFF
                t += off_duration
                in_burst = True
            
            # Periodic velocity updates (every 1s)
            velocity += np.random.uniform(-2, 2)
            velocity = max(0, min(30, velocity))
            events.append({
                'ue_id': ue_id,
                'type': 'velocity_update',
                'value': velocity,
                'timestamp': t
            })
            
            # Periodic RSRP updates (every 100ms simulated as per event)
            rsrp += np.random.uniform(-3, 3)
            rsrp = max(-120, min(-50, rsrp))
            events.append({
                'ue_id': ue_id,
                'type': 'rsrp_update',
                'value': rsrp,
                'timestamp': t
            })
            
            # Timer ticks to check inactive transition
            events.append({
                'ue_id': ue_id,
                'type': 'timer_tick',
                'value': 0,
                'timestamp': t
            })
    
    return events


def compute_energy_stats(df: pd.DataFrame, duration: float) -> dict:
    """
    Compute energy consumption statistics from trace.
    
    Args:
        df: Trace DataFrame from run_trace()
        duration: Total simulation duration
        
    Returns:
        Dictionary with energy statistics
    """
    stats = {}
    
    for ue_id in df['ue_id'].unique():
        ue_df = df[df['ue_id'] == ue_id].sort_values('timestamp')
        
        # Compute time in each state
        time_in_state = {s: 0.0 for s in RRCState}
        
        for i in range(len(ue_df) - 1):
            state = RRCState(ue_df.iloc[i]['state'])
            dt = ue_df.iloc[i + 1]['timestamp'] - ue_df.iloc[i]['timestamp']
            time_in_state[state] += dt
        
        # Energy = sum(time_in_state * power)
        energy_mj = sum(time_in_state[s] * POWER_MW[s] for s in RRCState)
        
        # Baseline: all time in CONNECTED
        baseline_mj = duration * POWER_MW[RRCState.CONNECTED]
        
        stats[ue_id] = {
            'energy_mj': energy_mj,
            'baseline_mj': baseline_mj,
            'reduction_pct': (1 - energy_mj / baseline_mj) * 100 if baseline_mj > 0 else 0,
            'time_connected': time_in_state[RRCState.CONNECTED],
            'time_inactive': time_in_state[RRCState.INACTIVE],
            'time_idle': time_in_state[RRCState.IDLE],
        }
    
    return stats


def main():
    """Demo simulation of ARSTA algorithm."""
    print("=" * 60)
    print("ARSTA: Adaptive RRC State Transition Algorithm")
    print("Demo Simulation")
    print("=" * 60)
    
    # Initialize simulator with default parameters
    sim = ARSTASimulator(
        alpha=0.3,
        inactive_threshold=0.6,
        ho_lock_threshold=-2.0,
        inactivity_timer=10.0
    )
    
    print(f"\nParameters:")
    print(f"  EWMA alpha: {sim.alpha}")
    print(f"  Inactive threshold: {sim.inactive_threshold}")
    print(f"  HO lock threshold: {sim.ho_lock_threshold} dB/s")
    print(f"  Inactivity timer: {sim.inactivity_timer} s")
    
    # Generate demo trace
    duration = 60.0
    ue_count = 5
    print(f"\nGenerating trace: {ue_count} UEs, {duration}s duration...")
    events = generate_demo_trace(duration=duration, ue_count=ue_count, seed=42)
    print(f"  Generated {len(events)} events")
    
    # Run simulation
    print("\nRunning simulation...")
    df = sim.run_trace(events, ue_count=ue_count)
    print(f"  Processed {len(df)} state transitions")
    
    # Compute energy statistics
    print("\nEnergy Statistics:")
    print("-" * 60)
    stats = compute_energy_stats(df, duration)
    
    total_energy = 0
    total_baseline = 0
    
    for ue_id, s in stats.items():
        print(f"UE {ue_id}: Energy={s['energy_mj']:.1f} mJ, "
              f"Baseline={s['baseline_mj']:.1f} mJ, "
              f"Reduction={s['reduction_pct']:.1f}%")
        total_energy += s['energy_mj']
        total_baseline += s['baseline_mj']
    
    print("-" * 60)
    overall_reduction = (1 - total_energy / total_baseline) * 100 if total_baseline > 0 else 0
    print(f"TOTAL: Energy={total_energy:.1f} mJ, Reduction={overall_reduction:.1f}%")
    
    # State distribution
    print("\nState Distribution:")
    print("-" * 60)
    state_counts = df['state_name'].value_counts()
    for state, count in state_counts.items():
        print(f"  {state}: {count} transitions ({count/len(df)*100:.1f}%)")
    
    # DRX cycle distribution
    print("\nDRX Cycle Distribution:")
    drx_counts = df['drx_ms'].value_counts().sort_index()
    for drx, count in drx_counts.items():
        print(f"  {drx}ms: {count} ({count/len(df)*100:.1f}%)")
    
    # Sample trace output
    print("\nSample Trace (first 10 events):")
    print("-" * 60)
    sample = df.head(10)[['timestamp', 'ue_id', 'state_name', 'drx_ms', 
                          'ho_locked', 'ewma_iat', 'velocity']]
    print(sample.to_string(index=False))
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
    
    return df, stats


if __name__ == '__main__':
    df, stats = main()
