import can
import time
import sys
import struct
import statistics
import numpy as np
from collections import deque
from threading import Thread, Event
import datetime
import csv
from scipy.signal import savgol_filter

# Configuration
DEVICE = "/dev/ttyUSB0"  # Change this to your actual device
CAN_SPEED = 500000       # 500kbps
BAUDRATE = 2000000       # 2Mbps
MOTOR_ID = 1             # Motor ID
TORQUE_CONSTANT = 0.065  # Nm/A
POLLING_INTERVAL = 50    # Time between readings in milliseconds
FILTER_WINDOW = 11       # Window size for Savitzky-Golay filter
FILTER_ORDER = 3         # Polynomial order for Savitzky-Golay filter

# Commands for different readings
IQ_COMMAND = bytes([0xB4, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])  # Request Iq current

# Globals
stop_event = Event()
data_log = []

class RealTimeFilter:
    """Real-time signal filtering with multiple filter options"""
    
    def __init__(self, filter_type="savgol", window_size=11, poly_order=3, alpha=0.2):
        self.filter_type = filter_type
        self.window_size = window_size
        self.poly_order = poly_order
        self.alpha = alpha  # For EMA filter
        self.buffer = deque(maxlen=window_size)
        self.last_value = 0  # For IIR and EMA filters
    
    def update(self, new_value):
        """Add a new value and return the filtered result"""
        if self.filter_type == "savgol":
            # Savitzky-Golay filter
            self.buffer.append(new_value)
            
            # Need a full buffer before we can filter
            if len(self.buffer) < self.window_size:
                return new_value
                
            # Apply Savitzky-Golay filter
            return savgol_filter(np.array(self.buffer), 
                                window_length=self.window_size, 
                                polyorder=self.poly_order)[-1]
                                
        elif self.filter_type == "ema":
            # Exponential Moving Average
            self.last_value = self.alpha * new_value + (1 - self.alpha) * self.last_value
            return self.last_value
            
        elif self.filter_type == "iir":
            # Simple one-pole IIR filter (similar to EMA but different formulation)
            self.last_value = 0.8 * self.last_value + 0.2 * new_value
            return self.last_value
            
        else:
            # No filtering
            return new_value

def format_can_data(data):
    """Format CAN data as space-separated hex bytes"""
    return " ".join([f"{byte:02X}" for byte in data])

def setup_can_bus():
    """Initialize the CAN bus connection"""
    try:
        bus = can.interface.Bus(
            interface='seeedstudio',
            channel=DEVICE,
            bitrate=CAN_SPEED,
            baudrate=BAUDRATE
        )
        print(f"Connected to CAN bus on {DEVICE}")
        return bus
    except Exception as e:
        print(f"Error setting up CAN bus: {e}")
        sys.exit(1)

def send_message(bus, data, arbitration_id=MOTOR_ID):
    """Send a message with the specified data to the CAN bus"""
    if len(data) != 8:
        print("Error: Message must be exactly 8 bytes")
        return False
    
    message = can.Message(
        arbitration_id=arbitration_id,
        data=data,
        is_extended_id=False
    )
    
    try:
        bus.send(message)
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def parse_float_from_response(data):
    """Parse IEEE 754 float from bytes 4-7 of the response, little-endian"""
    try:
        # The float is in bytes 4-7 in little-endian format
        float_bytes = bytes(data[4:8])
        value = struct.unpack('<f', float_bytes)[0]
        return value
    except Exception as e:
        print(f"Error parsing float: {e}")
        return None

def read_torque_loop(bus):
    """Main loop to read current and calculate torque with real-time filtering"""
    start_time = time.time()
    
    # Initialize filters
    current_filter = RealTimeFilter(filter_type="savgol", window_size=FILTER_WINDOW)
    torque_filter = RealTimeFilter(filter_type="savgol", window_size=FILTER_WINDOW)
    
    while not stop_event.is_set():
        # Send request for Iq
        send_message(bus, IQ_COMMAND)
        
        # Wait for response
        message = bus.recv(0.2)  # 200ms timeout
        
        if message and message.data[0] == 0xB4:
            # Check if this is a response to our indicator request
            indicator_id = message.data[1]
            
            if indicator_id == 0x09:  # Iq
                current_raw = parse_float_from_response(message.data)
                if current_raw is not None:
                    # Filter the current value
                    current = current_filter.update(current_raw)
                    
                    # Calculate and filter torque
                    torque_raw = current_raw * TORQUE_CONSTANT
                    torque = torque_filter.update(torque_raw)
                    
                    elapsed = time.time() - start_time
                    
                    # Add to data log
                    data_log.append({
                        'time': elapsed,
                        'current_raw': current_raw,
                        'current': current,
                        'torque_raw': torque_raw,
                        'torque': torque
                    })
                    
                    # Display values
                    print(f"\rTime: {elapsed:.2f}s | Current: {current:.2f}A (raw: {current_raw:.2f}A) | Torque: {torque:.4f}Nm", end="")
        
        # Sleep until next polling interval
        time.sleep(POLLING_INTERVAL / 1000)

def save_data_to_file():
    """Save collected data to a CSV file"""
    if not data_log:
        print("No data to save")
        return None
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"filtered_motor_torque_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['time', 'current_raw', 'current', 'torque_raw', 'torque']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for data in data_log:
            writer.writerow(data)
    
    print(f"Data saved to {filename}")
    return filename

def main():
    """Main function"""
    print("Real-Time Filtered Motor Torque Monitor")
    print(f"Torque constant: {TORQUE_CONSTANT} Nm/A")
    print(f"Polling interval: {POLLING_INTERVAL}ms")
    print(f"Filter: Savitzky-Golay (window={FILTER_WINDOW}, order={FILTER_ORDER})")
    
    # Set up CAN bus
    bus = setup_can_bus()
    
    # Start data collection thread
    print("\nStarting data collection (Press Ctrl+C to stop)...")
    torque_thread = Thread(target=read_torque_loop, args=(bus,), daemon=True)
    torque_thread.start()
    
    try:
        # Keep main thread alive until user interrupts
        while torque_thread.is_alive():
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\nStopping data collection...")
    finally:
        stop_event.set()
        if torque_thread.is_alive():
            torque_thread.join(timeout=1.0)
        
        save_data_to_file()
        
        # Generate plot after the program ends
        try:
            import matplotlib.pyplot as plt
            if data_log:
                times = [entry['time'] for entry in data_log]
                currents_raw = [entry['current_raw'] for entry in data_log]
                currents = [entry['current'] for entry in data_log]
                torques_raw = [entry['torque_raw'] for entry in data_log]
                torques = [entry['torque'] for entry in data_log]
                
                plt.figure(figsize=(12, 10))
                
                plt.subplot(2, 1, 1)
                plt.plot(times, currents_raw, 'b-', alpha=0.5, label='Raw')
                plt.plot(times, currents, 'r-', label='Filtered')
                plt.title('Motor Current')
                plt.xlabel('Time (s)')
                plt.ylabel('Current (A)')
                plt.legend()
                plt.grid(True)
                
                plt.subplot(2, 1, 2)
                plt.plot(times, torques_raw, 'b-', alpha=0.5, label='Raw')
                plt.plot(times, torques, 'r-', label='Filtered')
                plt.title('Motor Torque')
                plt.xlabel('Time (s)')
                plt.ylabel('Torque (Nm)')
                plt.legend()
                plt.grid(True)
                
                plt.tight_layout()
                plot_filename = f"filtered_motor_plot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                plt.savefig(plot_filename)
                print(f"Plot saved to {plot_filename}")
                
                try:
                    plt.show()
                except:
                    print("Could not display plot (headless environment?)")
        except ImportError:
            print("Matplotlib not available - skipping plot generation")
        
        print("Closing CAN bus connection...")
        bus.shutdown()

if __name__ == "__main__":
    main()
