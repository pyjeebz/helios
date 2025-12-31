"""
Load shape definitions for different traffic patterns.

These shapes control HOW users are spawned over time, creating
patterns that are useful for ML training:
- Ramp: Gradual growth (predictable trend)
- Wave: Periodic surges (seasonality)
- Spike: Flash-sale burst (shock event)
"""
import math
from locust import LoadTestShape


class RampLoadShape(LoadTestShape):
    """
    Gradual ramp-up pattern - simulates organic traffic growth.
    
    Perfect for testing:
    - Trend detection in time series
    - Gradual scaling behavior
    - Capacity planning predictions
    
    Pattern:
    - Linear increase from 0 to max_users over ramp_duration
    - Hold at max_users for hold_duration
    - Linear decrease back to 0
    """
    
    # Configuration (can be overridden via environment variables)
    max_users = 100          # Peak number of users
    ramp_duration = 300      # 5 minutes to ramp up
    hold_duration = 600      # 10 minutes at peak
    spawn_rate = 5           # Users per second during ramp
    
    def tick(self):
        run_time = self.get_run_time()
        
        total_duration = self.ramp_duration * 2 + self.hold_duration
        
        if run_time > total_duration:
            return None  # Stop the test
        
        if run_time < self.ramp_duration:
            # Ramp up phase
            current_users = int(self.max_users * (run_time / self.ramp_duration))
            return (max(1, current_users), self.spawn_rate)
        
        elif run_time < self.ramp_duration + self.hold_duration:
            # Hold phase
            return (self.max_users, self.spawn_rate)
        
        else:
            # Ramp down phase
            ramp_down_time = run_time - self.ramp_duration - self.hold_duration
            current_users = int(self.max_users * (1 - ramp_down_time / self.ramp_duration))
            return (max(1, current_users), self.spawn_rate)


class WaveLoadShape(LoadTestShape):
    """
    Sinusoidal wave pattern - simulates daily/weekly traffic cycles.
    
    Perfect for testing:
    - Seasonality detection
    - Periodic scaling patterns
    - Time-based capacity adjustments
    
    Pattern:
    - Sine wave oscillation between min_users and max_users
    - Period controls the cycle length
    - Multiple cycles for better pattern learning
    """
    
    min_users = 10           # Valley (low traffic)
    max_users = 100          # Peak (high traffic)
    period = 300             # 5 minutes per cycle
    num_cycles = 6           # Number of complete cycles
    spawn_rate = 10          # Users per second
    
    def tick(self):
        run_time = self.get_run_time()
        total_duration = self.period * self.num_cycles
        
        if run_time > total_duration:
            return None
        
        # Sine wave: oscillates between -1 and 1
        # Scale to oscillate between min_users and max_users
        amplitude = (self.max_users - self.min_users) / 2
        midpoint = self.min_users + amplitude
        
        current_users = int(midpoint + amplitude * math.sin(2 * math.pi * run_time / self.period))
        current_users = max(self.min_users, min(self.max_users, current_users))
        
        return (current_users, self.spawn_rate)


class SpikeLoadShape(LoadTestShape):
    """
    Spike/burst pattern - simulates flash sales or viral events.
    
    Perfect for testing:
    - Anomaly detection
    - Burst handling capacity
    - Recovery behavior
    
    Pattern:
    - Baseline traffic
    - Sudden spike to peak
    - Gradual recovery
    - Multiple spikes possible
    """
    
    baseline_users = 20      # Normal traffic
    spike_users = 200        # Spike peak
    baseline_duration = 120  # 2 minutes baseline before spike
    spike_duration = 60      # 1 minute spike
    recovery_duration = 180  # 3 minutes recovery
    num_spikes = 3           # Number of spikes
    spawn_rate = 50          # Fast spawn during spike
    
    def tick(self):
        run_time = self.get_run_time()
        cycle_duration = self.baseline_duration + self.spike_duration + self.recovery_duration
        total_duration = cycle_duration * self.num_spikes
        
        if run_time > total_duration:
            return None
        
        # Determine which phase we're in within the current cycle
        cycle_time = run_time % cycle_duration
        
        if cycle_time < self.baseline_duration:
            # Baseline phase
            return (self.baseline_users, self.spawn_rate // 5)
        
        elif cycle_time < self.baseline_duration + self.spike_duration:
            # Spike phase - rapid increase
            spike_progress = (cycle_time - self.baseline_duration) / self.spike_duration
            if spike_progress < 0.3:
                # Rapid rise (30% of spike duration)
                current_users = int(self.baseline_users + (self.spike_users - self.baseline_users) * (spike_progress / 0.3))
            else:
                # Hold at peak (70% of spike duration)
                current_users = self.spike_users
            return (current_users, self.spawn_rate)
        
        else:
            # Recovery phase - gradual decrease
            recovery_progress = (cycle_time - self.baseline_duration - self.spike_duration) / self.recovery_duration
            current_users = int(self.spike_users - (self.spike_users - self.baseline_users) * recovery_progress)
            return (max(self.baseline_users, current_users), self.spawn_rate // 2)


class StepLoadShape(LoadTestShape):
    """
    Step function pattern - discrete load levels.
    
    Perfect for testing:
    - Finding breaking points
    - Capacity thresholds
    - Step-change behavior
    """
    
    step_users = [10, 25, 50, 75, 100, 150, 200]  # User levels
    step_duration = 180      # 3 minutes per step
    spawn_rate = 20
    
    def tick(self):
        run_time = self.get_run_time()
        total_duration = self.step_duration * len(self.step_users)
        
        if run_time > total_duration:
            return None
        
        current_step = int(run_time // self.step_duration)
        current_step = min(current_step, len(self.step_users) - 1)
        
        return (self.step_users[current_step], self.spawn_rate)


class ChaosLoadShape(LoadTestShape):
    """
    Chaotic/random pattern - unpredictable traffic.
    
    Perfect for testing:
    - Robustness to noise
    - Model generalization
    - Real-world unpredictability
    """
    
    min_users = 10
    max_users = 150
    change_interval = 30     # Change every 30 seconds
    duration = 1800          # 30 minutes total
    spawn_rate = 20
    
    import random
    _random = random.Random(42)  # Seeded for reproducibility
    
    def tick(self):
        run_time = self.get_run_time()
        
        if run_time > self.duration:
            return None
        
        # Seed based on time interval for reproducibility
        interval = int(run_time // self.change_interval)
        self._random.seed(42 + interval)
        
        current_users = self._random.randint(self.min_users, self.max_users)
        
        return (current_users, self.spawn_rate)
