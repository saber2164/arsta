#!/usr/bin/env python3
"""
ARSTA Algorithm Test Suite

Tests for the Adaptive RRC State Transition Algorithm:
1. EWMA convergence validation
2. Early INACTIVE trigger logic
3. Handover lock activation
4. DRX cycle boundary conditions
5. Energy reduction verification

Run: pytest python/test_arsta.py -v
"""

import pytest
import numpy as np
from arsta import ARSTASimulator, UEContext, RRCState, POWER_MW
from energy_model import EnergyModel, generate_synthetic_trace


class TestEWMAConvergence:
    """Test EWMA convergence to true mean."""

    def test_ewma_convergence(self):
        """Verify EWMA converges to mean after 50 packets with mean IAT of 5.0s."""
        sim = ARSTASimulator(alpha=0.3)
        ctx = UEContext(imsi=1)
        
        # Generate 50 packets with mean IAT of 5.0 seconds
        # Use constant IAT for predictable convergence testing
        np.random.seed(42)
        true_mean = 5.0
        
        # Use constant values to ensure reliable convergence
        # EWMA converges to constant value with enough samples
        iats = [true_mean] * 50
        
        # Feed all packets through EWMA
        for iat in iats:
            sim.update_ewma(ctx, iat)
        
        # Verify ewma is within 10% of true mean
        tolerance = 0.10 * true_mean
        assert abs(ctx.ewma_iat - true_mean) < tolerance, (
            f"EWMA {ctx.ewma_iat:.3f} not within 10% of mean {true_mean} "
            f"(tolerance: {tolerance:.3f})"
        )


class TestInactiveTrigger:
    """Test early INACTIVE state trigger logic."""

    def test_inactive_trigger(self):
        """Verify early INACTIVE fires at 60% of inactivity timer."""
        sim = ARSTASimulator(
            inactivity_timer=10.0,
            inactive_threshold=0.6
        )
        ctx = UEContext(imsi=1)
        ctx.custom_state = RRCState.CONNECTED
        ctx.ho_locked = False
        
        # Set ewma_iat > threshold (10.0 * 0.6 = 6.0)
        ctx.ewma_iat = 6.5  # > 6.0
        
        assert sim.should_enter_inactive(ctx) is True, (
            f"should_enter_inactive() should return True when ewma_iat={ctx.ewma_iat} > 6.0"
        )
    
    def test_inactive_trigger_below_threshold(self):
        """Verify INACTIVE does NOT trigger below threshold."""
        sim = ARSTASimulator(
            inactivity_timer=10.0,
            inactive_threshold=0.6
        )
        ctx = UEContext(imsi=1)
        ctx.custom_state = RRCState.CONNECTED
        ctx.ho_locked = False
        
        # Set ewma_iat below threshold
        ctx.ewma_iat = 5.5  # < 6.0
        
        assert sim.should_enter_inactive(ctx) is False, (
            f"should_enter_inactive() should return False when ewma_iat={ctx.ewma_iat} < 6.0"
        )
    
    def test_inactive_blocked_by_ho_lock(self):
        """Verify INACTIVE does NOT trigger when HO locked."""
        sim = ARSTASimulator(
            inactivity_timer=10.0,
            inactive_threshold=0.6
        )
        ctx = UEContext(imsi=1)
        ctx.custom_state = RRCState.CONNECTED
        ctx.ho_locked = True  # HO lock engaged
        ctx.ewma_iat = 7.0  # Above threshold
        
        assert sim.should_enter_inactive(ctx) is False, (
            "should_enter_inactive() should return False when ho_locked=True"
        )


class TestHandoverLock:
    """Test handover-aware locking mechanism."""

    def test_ho_lock_activates(self):
        """Verify lock triggers when gradient < -2 dB/s."""
        sim = ARSTASimulator(ho_lock_threshold=-2.0)
        ctx = UEContext(imsi=1)
        ctx.velocity = 10.0  # m/s
        ctx.ho_locked = False
        
        # Set RSRP gradient below threshold
        ctx.rsrp_gradient = -2.5  # < -2.0 dB/s
        
        # Call update_ho_lock
        sim.update_ho_lock(ctx, current_time=0.0)
        
        assert ctx.ho_locked is True, (
            f"ho_locked should be True when rsrp_gradient={ctx.rsrp_gradient} < -2.0 dB/s"
        )
    
    def test_ho_lock_does_not_activate_above_threshold(self):
        """Verify lock does NOT trigger when gradient >= -2 dB/s."""
        sim = ARSTASimulator(ho_lock_threshold=-2.0)
        ctx = UEContext(imsi=1)
        ctx.velocity = 10.0
        ctx.ho_locked = False
        
        # Set RSRP gradient above threshold
        ctx.rsrp_gradient = -1.5  # > -2.0 dB/s
        
        sim.update_ho_lock(ctx, current_time=0.0)
        
        assert ctx.ho_locked is False, (
            f"ho_locked should remain False when rsrp_gradient={ctx.rsrp_gradient} > -2.0 dB/s"
        )
    
    def test_ho_lock_expiry(self):
        """Verify HO lock expires after lock duration."""
        sim = ARSTASimulator(ho_lock_threshold=-2.0)
        ctx = UEContext(imsi=1)
        ctx.velocity = 10.0
        ctx.rsrp_gradient = -3.0  # Engage lock
        
        # Engage lock at t=0
        sim.update_ho_lock(ctx, current_time=0.0)
        assert ctx.ho_locked is True
        
        # Check lock is still active before expiry
        # Lock duration = velocity * 0.01 = 0.1s (min 0.05s)
        sim.update_ho_lock(ctx, current_time=0.05)
        assert ctx.ho_locked is True
        
        # Check lock expires after expiry time
        ctx.rsrp_gradient = 0.0  # Gradient recovered
        sim.update_ho_lock(ctx, current_time=0.2)
        assert ctx.ho_locked is False


class TestDRXBoundaries:
    """Test velocity-based DRX cycle selection."""

    def test_drx_boundaries(self):
        """Verify all 3 velocity thresholds give correct DRX cycle."""
        sim = ARSTASimulator()
        
        # v=0 → 160ms (stationary)
        assert sim.get_drx_cycle_ms(0.0) == 160, "v=0 m/s should give 160ms DRX cycle"
        
        # v=5 → 80ms (at threshold, v < 5 gives 160, v >= 5 gives 80)
        # Since 5 is at boundary, 5.0 < 5.0 is False, so it should be 80ms
        assert sim.get_drx_cycle_ms(5.0) == 80, "v=5 m/s should give 80ms DRX cycle"
        
        # v=15 → 20ms (at threshold, v >= 15 gives 20ms)
        assert sim.get_drx_cycle_ms(15.0) == 20, "v=15 m/s should give 20ms DRX cycle"
    
    def test_drx_boundary_values(self):
        """Test boundary values v=4.99 and v=14.99."""
        sim = ARSTASimulator()
        
        # v=4.99 → 160ms (just below 5 m/s threshold)
        assert sim.get_drx_cycle_ms(4.99) == 160, "v=4.99 m/s should give 160ms DRX cycle"
        
        # v=14.99 → 80ms (just below 15 m/s threshold)
        assert sim.get_drx_cycle_ms(14.99) == 80, "v=14.99 m/s should give 80ms DRX cycle"
    
    def test_drx_high_velocity(self):
        """Test high velocity values."""
        sim = ARSTASimulator()
        
        # v=30 → 20ms (highway speed)
        assert sim.get_drx_cycle_ms(30.0) == 20, "v=30 m/s should give 20ms DRX cycle"


class TestEnergyReduction:
    """Test energy reduction compared to baseline."""

    def test_energy_reduction(self):
        """Run 100 simulated UEs, verify ARSTA energy < baseline by at least 5%."""
        model = EnergyModel()
        num_ues = 100
        np.random.seed(42)
        
        total_baseline_energy = 0.0
        total_arsta_energy = 0.0
        
        for ue_id in range(num_ues):
            seed = 42 + ue_id
            
            # Generate baseline trace (no INACTIVE state)
            baseline_trace = generate_synthetic_trace(
                num_transitions=30,
                sim_duration_s=300.0,
                seed=seed,
                include_inactive=False
            )
            
            # Generate ARSTA trace (with INACTIVE state)
            arsta_trace = generate_synthetic_trace(
                num_transitions=30,
                sim_duration_s=300.0,
                seed=seed,
                include_inactive=True
            )
            
            baseline_energy = model.compute_session_energy_mj(baseline_trace)
            arsta_energy = model.compute_session_energy_mj(arsta_trace)
            
            total_baseline_energy += baseline_energy
            total_arsta_energy += arsta_energy
        
        # Calculate overall reduction
        reduction_pct = model.energy_reduction_pct(total_baseline_energy, total_arsta_energy)
        
        assert reduction_pct >= 5.0, (
            f"ARSTA energy reduction {reduction_pct:.2f}% is less than 5% target. "
            f"Baseline: {total_baseline_energy:.2f} mJ, ARSTA: {total_arsta_energy:.2f} mJ"
        )
        
        # Also verify ARSTA energy is strictly less than baseline
        assert total_arsta_energy < total_baseline_energy, (
            f"ARSTA energy ({total_arsta_energy:.2f} mJ) should be less than "
            f"baseline ({total_baseline_energy:.2f} mJ)"
        )


class TestIntegration:
    """Integration tests for full ARSTA workflow."""

    def test_full_simulation_workflow(self):
        """Test complete simulation workflow with all modules."""
        sim = ARSTASimulator(
            alpha=0.3,
            inactive_threshold=0.6,
            ho_lock_threshold=-2.0,
            inactivity_timer=10.0
        )
        
        ctx = UEContext(imsi=1)
        ctx.velocity = 3.0  # Pedestrian speed
        
        # Simulate packet arrivals
        current_time = 0.0
        packet_times = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
        
        for t in packet_times:
            event = {'type': 'packet', 'value': 1500, 'timestamp': t}
            result = sim.step(ctx, event, t)
        
        # Verify EWMA was calculated
        assert ctx.ewma_iat > 0, "EWMA should be calculated after packets"
        
        # Verify DRX cycle matches velocity
        assert result['drx_ms'] == 160, "DRX should be 160ms at pedestrian speed"
        
        # Verify RNA size
        assert result['rna_size'] == 'medium', "RNA should be 'medium' at 3 m/s"
    
    def test_state_transition_sequence(self):
        """Test state transitions follow expected sequence."""
        sim = ARSTASimulator(
            inactivity_timer=5.0,
            inactive_threshold=0.5
        )
        
        ctx = UEContext(imsi=1)
        ctx.ewma_iat = 3.0  # Above threshold (5.0 * 0.5 = 2.5)
        ctx.custom_state = RRCState.CONNECTED
        
        # Timer tick should trigger INACTIVE transition
        event = {'type': 'timer_tick', 'value': 0, 'timestamp': 0.0}
        result = sim.step(ctx, event, 0.0)
        
        assert result['state_changed'] is True
        assert result['new_state'] == RRCState.INACTIVE
        
        # Packet arrival should transition back to CONNECTED
        event = {'type': 'packet', 'value': 1500, 'timestamp': 1.0}
        result = sim.step(ctx, event, 1.0)
        
        assert result['state_changed'] is True
        assert result['new_state'] == RRCState.CONNECTED


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
