import subprocess
import sys
import time
import os

def main():
    print("Starting MediaPipe Spatial Mouse & Configuration API...")
    
    # sys.executable ensures we use the exact Python interpreter from the active venv
    
    # 1. Start the FastAPI server
    api_process = subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--port", "8000"])
    
    # 2. Start the main MediaPipe tracking daemon
    main_process = subprocess.Popen([sys.executable, "tracker.py"])

    # 3. Start the React frontend application
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "my-app")
    
    # Use npm.cmd directly on Windows to avoid process-tree termination issues with shell=True
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_process = subprocess.Popen([npm_cmd, "run", "dev"], cwd=frontend_dir)

    try:
        # Keep the main thread alive waiting for user to send Ctrl+C
        while True:
            time.sleep(1)
            # If either backend process crashes, gracefully exit
            if api_process.poll() is not None or main_process.poll() is not None:
                raise KeyboardInterrupt
                
    except KeyboardInterrupt:
        print("\nShutting down all processes...")
        api_process.terminate()
        main_process.terminate()
        # npm processes started with shell=True on Windows can be tricky to kill cleanly,
        # but calling terminate on the shell process usually triggers child exits.
        frontend_process.terminate()
        api_process.wait()
        main_process.wait()
        try:
            frontend_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            frontend_process.kill()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
