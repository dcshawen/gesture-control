import subprocess
import sys
import time
import os
import multiprocessing

def main():
    print("Starting MediaPipe Spatial Mouse & Configuration API...")
    
    # sys.executable ensures we use the exact Python interpreter from the active venv
    
    # 1. Start the FastAPI server
    api_process = subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--port", "8000"])
    
    # 2. Start the main MediaPipe tracking daemon + feed via multiprocessing
    # This allows tracker to hand off frames to the feed viewer without blocking MediaPipe inference
    frame_queue = multiprocessing.Queue(maxsize=1)
    
    # We must import inside the function to avoid circular imports / double loading in spawned processes
    from tracker import main_loop as tracker_main
    from feed import main as feed_main
    
    tracker_process = multiprocessing.Process(target=tracker_main, args=(frame_queue,))
    tracker_process.start()
    
    feed_process = multiprocessing.Process(target=feed_main, args=(frame_queue,))
    feed_process.start()

    # 3. Start the React frontend application
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "my-app")
    
    # Use npm.cmd directly on Windows to avoid process-tree termination issues with shell=True
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_process = subprocess.Popen([npm_cmd, "run", "dev"], cwd=frontend_dir)

    try:
        # Keep the main thread alive waiting for user to send Ctrl+C
        while True:
            time.sleep(1)
            # If backend processes crash, gracefully exit
            if api_process.poll() is not None or not tracker_process.is_alive() or not feed_process.is_alive():
                raise KeyboardInterrupt
                
    except KeyboardInterrupt:
        print("\nShutting down all processes...")
        api_process.terminate()
        if tracker_process.is_alive():
            tracker_process.terminate()
        if feed_process.is_alive():
            feed_process.terminate()
        # npm processes started with shell=True on Windows can be tricky to kill cleanly,
        # but calling terminate on the shell process usually triggers child exits.
        frontend_process.terminate()
        api_process.wait()
        tracker_process.join()
        feed_process.join()
        try:
            frontend_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            frontend_process.kill()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
