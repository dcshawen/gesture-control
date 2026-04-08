import cv2
import queue

def main(frame_queue):
    print("Starting MediaPipe feed viewer...")
    cv2.namedWindow('MediaPipe Tracker Feed', cv2.WINDOW_NORMAL)
    
    while True:
        try:
            # Get the latest frame, timeout to check for exit
            frame = frame_queue.get(timeout=1.0)
            
            if frame is None:
                # Sentinel value to exit
                break
                
            cv2.imshow('MediaPipe Tracker Feed', frame)
            
            # Press 'q' to quit the viewer
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        except queue.Empty:
            continue
            
    cv2.destroyAllWindows()

if __name__ == "__main__":
    # Fallback if run directly
    print("Please run this through main.py")