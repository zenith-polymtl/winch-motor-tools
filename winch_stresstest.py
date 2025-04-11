import can
import time
import sys
import statistics
import numpy as np
from threading import Thread, Event
from collections import deque

# Configuration
DEVICE = "/dev/ttyUSB0"  # Change this to your actual device
CAN_SPEED = 500000       # 500kbps
BAUDRATE = 2000000       # 2Mbps
MOTOR_ID = 1             # Motor ID (for sending)
RESPONSE_ID = None       # Set to None to listen for any response, or specify an ID if known
COMMAND = bytes([0xB4, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])  # Command to send
INTERVAL_MS = 10         # Send interval in milliseconds
TEST_DURATION_SEC = 10   # Test duration in seconds

# Globals for tracking responses
response_times = []
stop_event = Event()
last_sent_time = 0

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
    global last_sent_time
    
    if len(data) != 8:
        print("Error: Message must be exactly 8 bytes")
        return False
    
    message = can.Message(
        arbitration_id=arbitration_id,
        data=data,
        is_extended_id=False
    )
    
    try:
        # Record the current time before sending
        last_sent_time = time.time()
        bus.send(message)
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def receive_messages(bus):
    """Continuously receive messages and calculate response times"""
    global last_sent_time
    
    while not stop_event.is_set():
        message = bus.recv(0.1)  # Timeout of 100ms
        
        if message:
            # If RESPONSE_ID is None, accept any response, otherwise filter
            if RESPONSE_ID is None or message.arbitration_id == RESPONSE_ID:
                recv_time = time.time()
                
                # Check if this could be a response to our command
                # First 2 bytes should match our command
                if list(message.data[:2]) == list(COMMAND[:2]):
                    response_time_ms = (recv_time - last_sent_time) * 1000  # Convert to ms
                    response_times.append(response_time_ms)
                    print(f"Response time: {response_time_ms:.2f}ms | ID: {message.arbitration_id} | Data: {format_can_data(message.data)}")

def analyze_response_times():
    """Analyze the collected response times"""
    if not response_times:
        print("No response times collected!")
        return
    
    # Basic statistics
    avg_time = statistics.mean(response_times)
    min_time = min(response_times)
    max_time = max(response_times)
    std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
    
    # Calculate percentiles
    percentiles = {
        "50th": np.percentile(response_times, 50),
        "90th": np.percentile(response_times, 90),
        "95th": np.percentile(response_times, 95),
        "99th": np.percentile(response_times, 99)
    }
    
    print("\n===== Response Time Analysis =====")
    print(f"Total responses received: {len(response_times)}")
    print(f"Average response time: {avg_time:.2f}ms")
    print(f"Minimum response time: {min_time:.2f}ms")
    print(f"Maximum response time: {max_time:.2f}ms")
    print(f"Standard deviation: {std_dev:.2f}ms")
    print("\nPercentiles:")
    for percentile, value in percentiles.items():
        print(f"  {percentile}: {value:.2f}ms")
    
    # Calculate and print message rate
    duration = TEST_DURATION_SEC
    rate = len(response_times) / duration
    print(f"\nEffective response rate: {rate:.2f} msgs/sec")
    print(f"Expected rate: {1000/INTERVAL_MS:.2f} msgs/sec")

def main():
    print(f"Starting CAN response time test with command: {format_can_data(COMMAND)}")
    print(f"Sending every {INTERVAL_MS}ms for {TEST_DURATION_SEC} seconds")
    print(f"Looking for responses with " + 
          (f"ID: {RESPONSE_ID}" if RESPONSE_ID is not None else "any ID"))
    
    # Set up CAN bus
    bus = setup_can_bus()
    
    # Start a thread for receiving messages
    receiver_thread = Thread(target=receive_messages, args=(bus,), daemon=True)
    receiver_thread.start()
    
    # Send messages at the specified interval
    try:
        start_time = time.time()
        sent_count = 0
        
        while (time.time() - start_time) < TEST_DURATION_SEC:
            send_message(bus, COMMAND)
            sent_count += 1
            time.sleep(INTERVAL_MS / 1000)  # Convert ms to seconds
        
        # Wait for final responses to come in
        time.sleep(0.2)
        
        # Stop the receiver thread
        stop_event.set()
        receiver_thread.join(timeout=1.0)
        
        print(f"\nSent {sent_count} messages, received {len(response_times)} responses")
        print(f"Response rate: {(len(response_times)/sent_count)*100:.2f}%")
        
        # Analyze response times
        analyze_response_times()
    
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        stop_event.set()
        print("Closing CAN bus connection...")
        bus.shutdown()

if __name__ == "__main__":
    main()
