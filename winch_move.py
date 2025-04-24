import can
import time
import sys
from threading import Thread
from queue import Queue

# Configuration
DEVICE = "/dev/ttyUSB0"  # Change this to your actual device
CAN_SPEED = 500000       # 500kbps
BAUDRATE = 2000000       # 2Mbps
MOTOR_ID = 1             # Motor ID

# Queue for capturing responses
response_queue = Queue()
last_command = None
running = True

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
    global last_command
    
    if len(data) != 8:
        print("Error: Message must be exactly 8 bytes")
        return False
    
    message = can.Message(
        arbitration_id=arbitration_id,
        data=data,
        is_extended_id=False
    )
    
    try:
        last_command = data[:2]  # Store the first 2 bytes for response matching
        bus.send(message)
        print(f"Sent message to ID {arbitration_id}: {format_can_data(data)}")
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def receive_messages(bus):
    """Continuously receive messages from the CAN bus"""
    global running, last_command
    
    print("Listening for CAN messages...")
    try:
        while running:
            message = bus.recv(0.1)  # Use timeout to allow clean thread exit
            if message:
                print(f"Received from ID {message.arbitration_id}: {format_can_data(message.data)}")
                
                # Check if this is a response to our last command (based on first 2 bytes)
                if last_command and message.data[:2] == last_command:
                    response_queue.put(message)
    except Exception as e:
        print(f"Error in receiver thread: {e}")

def wait_for_response(timeout=2.0):
    """Wait for a response to the last command"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if not response_queue.empty():
                return response_queue.get(block=False)
            time.sleep(0.01)
        except:
            pass
    return None

def parse_byte_string(byte_string):
    """Parse a string of hex bytes like '00 FF 12 34 56 78 9A BC' into bytes"""
    try:
        # Remove any extra whitespace and split by spaces
        parts = byte_string.strip().split()
        
        # Check if we have exactly 8 parts
        if len(parts) != 8:
            print("Error: Please provide exactly 8 bytes")
            return None
        
        # Convert each part to an integer
        data = [int(part, 16) for part in parts]
        return bytes(data)
    except ValueError as e:
        print(f"Error parsing input: {e}")
        return None

def execute_command_sequence_up(bus):
    """Execute the sequence of commands"""
    # Step 1: Send command 94 00 00 A0 C1 D0 07 00
    print("\nStep 1: Sending initial command")
    data = parse_byte_string("94 00 00 A0 C1 D0 07 00")
    if data:
        send_message(bus, data)
        response1 = wait_for_response()
        if not response1:
            print("Warning: No response to command 1, continuing anyway")
    
    # Step 2: Send command 91 00 00 00 00 00 00 00
    print("\nStep 2: Sending second command")
    data = parse_byte_string("91 00 00 00 00 00 00 00")
    if data:
        send_message(bus, data)
        response2 = wait_for_response()
        if not response2:
            print("Warning: No response to command 2, continuing anyway")
    
    # Wait 2 seconds
    print("\nWaiting 2 seconds...")
    time.sleep(2)
    
    # Step 3: Send command B4 13 00 00 00 00 00 00
    print("\nStep 3: Sending command to get data")
    data = parse_byte_string("B4 13 00 00 00 00 00 00")
    if data:
        send_message(bus, data)
        response3 = wait_for_response()
        
        if response3:
            # Extract last 4 bytes from response
            last_four_bytes = response3.data[-4:]
            print(f"Extracted 4 bytes: {format_can_data(last_four_bytes)}")
            
            # Step 4: Send command 95 [4 bytes] 32 14 00
            print("\nStep 4: Sending final command with extracted bytes")
            final_command = bytes([0x95]) + last_four_bytes + bytes([0x32, 0x14, 0x00])
            
            # Ensure it's exactly 8 bytes
            if len(final_command) > 8:
                final_command = final_command[:8]
            elif len(final_command) < 8:
                final_command = final_command + bytes([0x00] * (8 - len(final_command)))
            
            print(f"Final command: {format_can_data(final_command)}")
            send_message(bus, final_command)
            response4 = wait_for_response()
            
            if response4:
                print("\nCommand sequence completed successfully")
            else:
                print("\nNo response to final command")
        else:
            print("\nError: No response to command B4, cannot proceed")

def execute_command_sequence_down(bus):
    """Execute the sequence of commands"""
    # Step 1: Send command 94 00 00 A0 C1 D0 07 00
    print("\nStep 1: Sending initial command")
    data = parse_byte_string("94 00 00 A0 41 D0 07 00")
    if data:
        send_message(bus, data)
        response1 = wait_for_response()
        if not response1:
            print("Warning: No response to command 1, continuing anyway")
    
    # Step 2: Send command 91 00 00 00 00 00 00 00
    print("\nStep 2: Sending second command")
    data = parse_byte_string("91 00 00 00 00 00 00 00")
    if data:
        send_message(bus, data)
        response2 = wait_for_response()
        if not response2:
            print("Warning: No response to command 2, continuing anyway")
    
    # Wait 2 seconds
    print("\nWaiting 2 seconds...")
    time.sleep(2)
    
    # Step 3: Send command B4 13 00 00 00 00 00 00
    print("\nStep 3: Sending command to get data")
    data = parse_byte_string("B4 13 00 00 00 00 00 00")
    if data:
        send_message(bus, data)
        response3 = wait_for_response()
        
        if response3:
            # Extract last 4 bytes from response
            last_four_bytes = response3.data[-4:]
            print(f"Extracted 4 bytes: {format_can_data(last_four_bytes)}")
            
            # Step 4: Send command 95 [4 bytes] 32 14 00
            print("\nStep 4: Sending final command with extracted bytes")
            final_command = bytes([0x95]) + last_four_bytes + bytes([0x32, 0x14, 0x00])
            
            # Ensure it's exactly 8 bytes
            if len(final_command) > 8:
                final_command = final_command[:8]
            elif len(final_command) < 8:
                final_command = final_command + bytes([0x00] * (8 - len(final_command)))
            
            print(f"Final command: {format_can_data(final_command)}")
            send_message(bus, final_command)
            response4 = wait_for_response()
            
            if response4:
                print("\nCommand sequence completed successfully")
            else:
                print("\nNo response to final command")
        else:
            print("\nError: No response to command B4, cannot proceed")

def main():
    global running
    
    # Set up CAN bus
    bus = setup_can_bus()
    
    # Start a thread for receiving messages
    receiver_thread = Thread(target=receive_messages, args=(bus,), daemon=True)
    receiver_thread.start()
    
    # Give the receiver thread a moment to start
    time.sleep(0.5)
    
    try:
        # Execute the command sequence
        execute_command_sequence_down(bus)
        
        # Keep the script running to see any additional responses
        print("\nCommand sequence complete. Press Ctrl+C to exit...")
        while True:
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    finally:
        running = False  # Signal receiver thread to stop
        time.sleep(0.2)  # Give thread time to exit cleanly
        print("Closing CAN bus connection...")
        bus.shutdown()

if __name__ == "__main__":
    main()
