#!/usr/bin/env python3
"""
ARSTA Energy Model - TR 38.840 UE Power Model Implementation

This module implements the 3GPP TR 38.840 UE power consumption model
for analyzing RRC state transitions and computing energy metrics.

Power levels (mW):
    - RRC_IDLE: 5 mW
    - RRC_INACTIVE: 15 mW
    - RRC_CONNECTED: 900 mW
    - TRANSITION: 250 mW

Author: ARSTA Project
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple


class EnergyModel:
    """
    TR 38.840 UE Power Model for 5G NR energy analysis.
    
    This class provides methods to compute energy consumption based on
    RRC state traces, calculate state ratios, and analyze transition counts.
    
    Attributes:
        POWER_MW: Dictionary mapping RRC states to power consumption in milliwatts.
        STATE_MAP: Dictionary mapping ns-3 state integers to state names.
    """
    
    # Power consumption values from 3GPP TR 38.840 (in milliwatts)
    POWER_MW: Dict[str, float] = {
        'RRC_IDLE': 5.0,
        'RRC_INACTIVE': 15.0,
        'RRC_CONNECTED': 900.0,
        'TRANSITION': 250.0
    }
    
    # ns-3 state integer to state name mapping
    STATE_MAP: Dict[int, str] = {
        5: 'RRC_IDLE',        # IDLE_CAMPED_NORMALLY
        9: 'RRC_CONNECTED',   # CONNECTED_NORMALLY
        99: 'RRC_INACTIVE',   # Custom INACTIVE state
    }
    
    def _map_state(self, state_int: int) -> str:
        """
        Map ns-3 state integer to power state name.
        
        Args:
            state_int: ns-3 RRC state integer value.
            
        Returns:
            State name string ('RRC_IDLE', 'RRC_INACTIVE', 'RRC_CONNECTED', or 'TRANSITION').
        """
        return self.STATE_MAP.get(state_int, 'TRANSITION')
    
    def _get_power(self, state_int: int) -> float:
        """
        Get power consumption for a given ns-3 state integer.
        
        Args:
            state_int: ns-3 RRC state integer value.
            
        Returns:
            Power consumption in milliwatts.
        """
        state_name = self._map_state(state_int)
        return self.POWER_MW[state_name]
    
    def compute_session_energy_mj(self, state_trace_df: pd.DataFrame) -> float:
        """
        Compute total energy consumption for a UE session.
        
        This method calculates energy by summing the product of dwell time
        and power consumption for each state transition in the trace.
        
        Energy = Σ (dwell_time_s × power_mW) = mJ
        
        Args:
            state_trace_df: DataFrame with columns:
                - time_s: Timestamp in seconds
                - imsi: UE identifier
                - old_state: Previous RRC state (ns-3 integer)
                - new_state: New RRC state (ns-3 integer)
                - dwell_ms: Time spent in old_state (milliseconds)
                
        Returns:
            Total energy consumption in millijoules (mJ).
            
        Raises:
            ValueError: If required columns are missing from the DataFrame.
        """
        required_cols = {'time_s', 'imsi', 'old_state', 'new_state', 'dwell_ms'}
        if not required_cols.issubset(state_trace_df.columns):
            missing = required_cols - set(state_trace_df.columns)
            raise ValueError(f"Missing required columns: {missing}")
        
        if state_trace_df.empty:
            return 0.0
        
        total_energy_mj = 0.0
        
        for _, row in state_trace_df.iterrows():
            # Get power for the old_state (the state we dwelled in)
            power_mw = self._get_power(int(row['old_state']))
            dwell_s = row['dwell_ms'] / 1000.0  # Convert ms to seconds
            
            # Energy (mJ) = Power (mW) × Time (s)
            energy_mj = power_mw * dwell_s
            total_energy_mj += energy_mj
        
        return total_energy_mj
    
    def compute_state_ratios(self, state_trace_df: pd.DataFrame) -> Dict[str, float]:
        """
        Compute the fraction of time spent in each RRC state.
        
        Args:
            state_trace_df: DataFrame with columns:
                - time_s: Timestamp in seconds
                - imsi: UE identifier
                - old_state: Previous RRC state (ns-3 integer)
                - new_state: New RRC state (ns-3 integer)
                - dwell_ms: Time spent in old_state (milliseconds)
                
        Returns:
            Dictionary mapping state names to percentage of total time.
            Keys: 'RRC_IDLE', 'RRC_INACTIVE', 'RRC_CONNECTED', 'TRANSITION'
            Values: Percentages (0-100)
        """
        # Initialize time accumulator for each state
        state_times: Dict[str, float] = {
            'RRC_IDLE': 0.0,
            'RRC_INACTIVE': 0.0,
            'RRC_CONNECTED': 0.0,
            'TRANSITION': 0.0
        }
        
        if state_trace_df.empty:
            return state_times
        
        # Accumulate dwell time for each state
        for _, row in state_trace_df.iterrows():
            state_name = self._map_state(int(row['old_state']))
            state_times[state_name] += row['dwell_ms']
        
        # Calculate total time
        total_time = sum(state_times.values())
        
        if total_time == 0:
            return state_times
        
        # Convert to percentages
        state_ratios: Dict[str, float] = {
            state: (time_ms / total_time) * 100.0
            for state, time_ms in state_times.items()
        }
        
        return state_ratios
    
    def energy_reduction_pct(self, baseline_mj: float, arsta_mj: float) -> float:
        """
        Calculate energy reduction percentage between baseline and ARSTA.
        
        Args:
            baseline_mj: Baseline energy consumption in millijoules.
            arsta_mj: ARSTA-optimized energy consumption in millijoules.
            
        Returns:
            Energy reduction as a percentage.
            Positive value indicates ARSTA uses less energy.
            
        Raises:
            ValueError: If baseline_mj is zero or negative.
        """
        if baseline_mj <= 0:
            raise ValueError("Baseline energy must be positive")
        
        reduction_pct = ((baseline_mj - arsta_mj) / baseline_mj) * 100.0
        return reduction_pct
    
    def transition_count(self, state_trace_df: pd.DataFrame) -> int:
        """
        Count significant RRC state transitions.
        
        Counts transitions between:
        - IDLE ↔ CONNECTED
        - INACTIVE ↔ CONNECTED
        
        These are the most energy-significant transitions in 5G NR.
        
        Args:
            state_trace_df: DataFrame with columns:
                - time_s: Timestamp in seconds
                - imsi: UE identifier
                - old_state: Previous RRC state (ns-3 integer)
                - new_state: New RRC state (ns-3 integer)
                - dwell_ms: Time spent in old_state (milliseconds)
                
        Returns:
            Total count of significant transitions.
        """
        if state_trace_df.empty:
            return 0
        
        count = 0
        
        # Define significant state pairs (ns-3 integers)
        idle_state = 5       # IDLE_CAMPED_NORMALLY
        connected_state = 9  # CONNECTED_NORMALLY
        inactive_state = 99  # Custom INACTIVE
        
        for _, row in state_trace_df.iterrows():
            old_state = int(row['old_state'])
            new_state = int(row['new_state'])
            
            # IDLE ↔ CONNECTED transitions
            if (old_state == idle_state and new_state == connected_state) or \
               (old_state == connected_state and new_state == idle_state):
                count += 1
            
            # INACTIVE ↔ CONNECTED transitions
            elif (old_state == inactive_state and new_state == connected_state) or \
                 (old_state == connected_state and new_state == inactive_state):
                count += 1
        
        return count


def generate_synthetic_trace(
    num_transitions: int = 50,
    sim_duration_s: float = 300.0,
    seed: int = 42,
    include_inactive: bool = True
) -> pd.DataFrame:
    """
    Generate synthetic state trace data for testing.
    
    Args:
        num_transitions: Number of state transitions to generate.
        sim_duration_s: Total simulation duration in seconds.
        seed: Random seed for reproducibility.
        include_inactive: Whether to include RRC_INACTIVE states.
        
    Returns:
        DataFrame with synthetic state trace data.
    """
    np.random.seed(seed)
    
    # Define possible states
    if include_inactive:
        states = [5, 9, 99]  # IDLE, CONNECTED, INACTIVE
    else:
        states = [5, 9]  # IDLE, CONNECTED only (baseline)
    
    # Generate random transitions
    transitions = []
    current_time = 0.0
    current_state = 5  # Start in IDLE
    
    for i in range(num_transitions):
        # Choose next state (different from current)
        next_state = current_state
        while next_state == current_state:
            next_state = np.random.choice(states)
        
        # Random dwell time (exponential distribution, mean ~6s)
        dwell_ms = np.random.exponential(6000)
        
        transitions.append({
            'time_s': current_time,
            'imsi': 1001,
            'old_state': current_state,
            'new_state': next_state,
            'dwell_ms': dwell_ms
        })
        
        current_time += dwell_ms / 1000.0
        current_state = next_state
        
        if current_time >= sim_duration_s:
            break
    
    return pd.DataFrame(transitions)


def main() -> None:
    """Main function demonstrating the EnergyModel usage."""
    print("=" * 60)
    print("ARSTA Energy Model - TR 38.840 UE Power Model Demo")
    print("=" * 60)
    
    # Create model instance
    model = EnergyModel()
    
    # Display power model parameters
    print("\n📊 Power Model Parameters (3GPP TR 38.840):")
    print("-" * 40)
    for state, power in model.POWER_MW.items():
        print(f"  {state:15s}: {power:6.1f} mW")
    
    # Generate baseline trace (no INACTIVE state)
    print("\n🔄 Generating synthetic traces...")
    baseline_trace = generate_synthetic_trace(
        num_transitions=50,
        sim_duration_s=300.0,
        seed=42,
        include_inactive=False
    )
    
    # Generate ARSTA trace (with INACTIVE state)
    arsta_trace = generate_synthetic_trace(
        num_transitions=50,
        sim_duration_s=300.0,
        seed=42,
        include_inactive=True
    )
    
    # Compute energy for baseline
    print("\n📈 Baseline Results (no RRC_INACTIVE):")
    print("-" * 40)
    baseline_energy = model.compute_session_energy_mj(baseline_trace)
    baseline_ratios = model.compute_state_ratios(baseline_trace)
    baseline_transitions = model.transition_count(baseline_trace)
    
    print(f"  Total Energy:      {baseline_energy:,.2f} mJ")
    print(f"  Transitions:       {baseline_transitions}")
    print("  State Ratios:")
    for state, ratio in baseline_ratios.items():
        print(f"    {state:15s}: {ratio:5.1f}%")
    
    # Compute energy for ARSTA
    print("\n📉 ARSTA Results (with RRC_INACTIVE):")
    print("-" * 40)
    arsta_energy = model.compute_session_energy_mj(arsta_trace)
    arsta_ratios = model.compute_state_ratios(arsta_trace)
    arsta_transitions = model.transition_count(arsta_trace)
    
    print(f"  Total Energy:      {arsta_energy:,.2f} mJ")
    print(f"  Transitions:       {arsta_transitions}")
    print("  State Ratios:")
    for state, ratio in arsta_ratios.items():
        print(f"    {state:15s}: {ratio:5.1f}%")
    
    # Compute improvement
    print("\n✅ Energy Reduction Analysis:")
    print("-" * 40)
    reduction = model.energy_reduction_pct(baseline_energy, arsta_energy)
    print(f"  Baseline Energy:   {baseline_energy:,.2f} mJ")
    print(f"  ARSTA Energy:      {arsta_energy:,.2f} mJ")
    print(f"  Reduction:         {reduction:+.2f}%")
    
    if reduction > 0:
        print(f"\n  🎯 ARSTA achieved {reduction:.1f}% energy reduction!")
    else:
        print(f"\n  ⚠️  ARSTA used {-reduction:.1f}% more energy (unexpected)")
    
    # Show sample trace data
    print("\n📋 Sample Trace Data (first 5 rows):")
    print("-" * 40)
    print(arsta_trace.head().to_string(index=False))
    
    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
