import subprocess
import sys
import time

def main():
    print("Starting MediaPipe Spatial Mouse & Configuration API...")
    
    # sys.executable ensures we use the exact Python interpreter from the active venv
    
    # 1. Start the FastAPI server
    api_process = subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--port", "8000"])
    
    # 2. Start the main MediaPipe tracking daemon
    main_process = subprocess.Popen([sys.executable, "tracker.py"])

    try:
        # Keep the main thread alive waiting for user to send Ctrl+C
        while True:
            time.sleep(1)
            # If either process crashes, gracefully exit
            if api_process.poll() is not None or main_process.poll() is not None:
                raise KeyboardInterrupt
                
    except KeyboardInterrupt:
        print("\nShutting down both processes...")
        api_process.terminate()
        main_process.terminate()
        api_process.wait()
        main_process.wait()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
