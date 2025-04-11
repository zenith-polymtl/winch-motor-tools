import can
import time
import sys
import struct
import statistics
import numpy as np
from threading import Thread, Event
import datetime
import csv

# Configuration
DEVICE = "/dev/ttyUSB0"  # Change this to your actual device
CAN_SPEED = 500000       # 500kbps
BAUDRATE = 2000000       # 2Mbps
MOTOR_ID = 1             # Motor ID
TORQUE_CONSTANT = 0.065  # Nm/A
POLLING_INTERVAL = 50    # Time between readings in milliseconds

# Commands for different readings
IQ_COMMAND = bytes([0xB4, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])  # Request Iq current

# Globals
stop_event = Event()
data_log = []

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
    """Main loop to read current and calculate torque"""
    start_time = time.time()
    
    while not stop_event.is_set():
        # Send request for Iq
        send_message(bus, IQ_COMMAND)
        
        # Wait for response
        message = bus.recv(0.2)  # 200ms timeout
        
        if message and message.data[0] == 0xB4:
            # Check if this is a response to our indicator request
            indicator_id = message.data[1]
            
            if indicator_id == 0x09:  # Iq
                current = parse_float_from_response(message.data)
                if current is not None:
                    torque = current * TORQUE_CONSTANT
                    elapsed = time.time() - start_time
                    
                    # Add to data log - log every reading
                    data_log.append({
                        'time': elapsed,
                        'current': current,
                        'torque': torque
                    })
                    
                    # Display current value
                    print(f"\rTime: {elapsed:.2f}s | Current: {current:.2f}A | Torque: {torque:.4f}Nm", end="")
        
        # Sleep until next polling interval
        time.sleep(POLLING_INTERVAL / 1000)

def analyze_data():
    """Analyze collected data"""
    if not data_log:
        print("No data collected!")
        return
    
    currents = [entry['current'] for entry in data_log]
    torques = [entry['torque'] for entry in data_log]
    
    print("\n\n===== Data Analysis =====")
    print(f"Total readings: {len(data_log)}")
    print(f"Duration: {data_log[-1]['time'] - data_log[0]['time']:.2f} seconds")
    
    print("\nCurrent (A):")
    print(f"  Min: {min(currents):.2f}")
    print(f"  Max: {max(currents):.2f}")
    print(f"  Avg: {statistics.mean(currents):.2f}")
    if len(currents) > 1:
        print(f"  Std: {statistics.stdev(currents):.2f}")
    
    print("\nTorque (Nm):")
    print(f"  Min: {min(torques):.4f}")
    print(f"  Max: {max(torques):.4f}")
    print(f"  Avg: {statistics.mean(torques):.4f}")
    if len(torques) > 1:
        print(f"  Std: {statistics.stdev(torques):.4f}")

def save_data_to_file():
    """Save collected data to a CSV file"""
    if not data_log:
        print("No data to save")
        return None
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"motor_torque_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['time', 'current', 'torque']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for data in data_log:
            writer.writerow(data)
    
    print(f"Data saved to {filename}")
    return filename

def main():
    """Main function"""
    print("Motor Torque Monitor")
    print(f"Torque constant: {TORQUE_CONSTANT} Nm/A")
    print(f"Polling interval: {POLLING_INTERVAL}ms")
    
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
        
        analyze_data()
        save_data_to_file()
        
        # Generate plot after the program ends (if matplotlib is available)
        try:
            import matplotlib.pyplot as plt
            if data_log:
                times = [entry['time'] for entry in data_log]
                currents = [entry['current'] for entry in data_log]
                torques = [entry['torque'] for entry in data_log]
                
                plt.figure(figsize=(12, 8))
                plt.subplot(2, 1, 1)
                plt.plot(times, currents, 'b-')
                plt.title('Motor Current')
                plt.xlabel('Time (s)')
                plt.ylabel('Current (A)')
                plt.grid(True)
                
                plt.subplot(2, 1, 2)
                plt.plot(times, torques, 'r-')
                plt.title('Motor Torque')
                plt.xlabel('Time (s)')
                plt.ylabel('Torque (Nm)')
                plt.grid(True)
                
                plt.tight_layout()
                plot_filename = f"motor_torque_plot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
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
