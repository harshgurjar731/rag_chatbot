import phoenix as px
import time  # Import the time module

if __name__ == "__main__":
    print("🚀 Launching the Phoenix UI...")
    
    try:
        # Start the Phoenix server in the background
        px.launch_app()
        
        print("✅ Phoenix server is running. Visit http://localhost:6006/")
        print("   This script will keep running. Press Ctrl+C to shut down.")
        
        # This loop's only job is to keep the main script alive.
        # It does nothing but sleep, waking up once per second.
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        # This block catches Ctrl+C
        print("\nReceived shutdown signal from user.")
    finally:
        # This ensures a clean shutdown of the Phoenix server
        print("Attempting to shut down Phoenix server...")
        px.shutdown()
        print("✅ Phoenix server has been shut down.")