import cv2
import os
import time
import math
import urllib.request
import pyautogui
import ctypes

# ==============================================================================
# CONFIGURATION OPTIONS
# ==============================================================================
SMOOTHING_FACTOR = 0.15  # Cursor smoothing: Lower is smoother but adds more lag (0.0 to 1.0)
SENSITIVITY = 1.75       # Cursor tracking sensitivity
Y_OFFSET = 0.2           # Vertical offset for pointing coordinate mapping
DEADZONE = 0.05          # Normalized distance (0.0 to 1.0) of movement required to break deadzone
# ==============================================================================

# Make the process DPI aware to get true multi-monitor resolution
try:
    ctypes.windll.user32.SetProcessDPIAware()
except AttributeError:
    pass

# Adjust pyautogui settings for smoother tracking
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# Suppress MediaPipe/TensorFlow C++ logs
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import mediapipe as mp

# Download the MediaPipe gesture recognition model if it doesn't exist
model_path = 'gesture_recognizer.task'
if not os.path.exists(model_path):
    print("Downloading gesture recognition model...")
    url = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"
    urllib.request.urlretrieve(url, model_path)
    print("Download complete.")

BaseOptions = mp.tasks.BaseOptions
GestureRecognizer = mp.tasks.vision.GestureRecognizer
GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

# Keep track of the last detected gesture to avoid spamming the console
last_gesture = None

# Variables for cursor smoothing state
smoothed_x = None
smoothed_y = None

# Track mouse button click state
is_clicking = False

def get_distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

# Scaffolded methods for each gesture
def on_open_palm():
    print("Action triggered: Open Palm")

def on_closed_palm():
    print("Action triggered: Closed Palm")

def on_pointing(x_norm, y_norm):
    global smoothed_x, smoothed_y
    
    # Retrieve the full virtual screen bounding box across all connected monitors
    # This native Windows API considers primary monitor position (0,0), DPI, and relative secondary monitor layouts.
    user32 = ctypes.windll.user32
    v_x = user32.GetSystemMetrics(76) # SM_XVIRTUALSCREEN
    v_y = user32.GetSystemMetrics(77) # SM_YVIRTUALSCREEN
    v_w = user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
    v_h = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
    
    # Apply sensitivity and vertical offset
    # First, center coordinates around 0.5 (the middle of the camera feed)
    # We invert the X axis (1.0 - x) because webcams are mirrored by default
    centered_x = (1.0 - x_norm) - 0.5
    centered_y = (y_norm - Y_OFFSET) - 0.5
    
    # Multiply by sensitivity to get normalized target coordinates.
    # The camera's normalized space (0.0 to 1.0) is spanned across the entire multi-monitor setup.
    target_x_norm = centered_x * SENSITIVITY + 0.5
    target_y_norm = centered_y * SENSITIVITY + 0.5
    
    # Apply Exponential Moving Average (EMA) smoothing and Deadzone on the normalized coordinates
    if smoothed_x is None or smoothed_y is None:
        smoothed_x = target_x_norm
        smoothed_y = target_y_norm
        
        target_x_px = v_x + smoothed_x * v_w
        target_y_px = v_y + smoothed_y * v_h
        
        # Clamp coordinates
        target_x_px = max(v_x, min(v_x + v_w - 1, target_x_px))
        target_y_px = max(v_y, min(v_y + v_h - 1, target_y_px))
        
        pyautogui.moveTo(int(target_x_px), int(target_y_px))
    else:
        # Calculate raw distance in normalized space
        dist = math.sqrt((target_x_norm - smoothed_x)**2 + (target_y_norm - smoothed_y)**2)
        
        # Only update the mouse if the new position is outside the DEADZONE
        if dist > DEADZONE:
            scale = min((dist - DEADZONE) / DEADZONE, 1.0)
            adjusted_smoothing = SMOOTHING_FACTOR * scale
            
            smoothed_x = (smoothed_x * (1 - adjusted_smoothing)) + (target_x_norm * adjusted_smoothing)
            smoothed_y = (smoothed_y * (1 - adjusted_smoothing)) + (target_y_norm * adjusted_smoothing)
            
            target_x_px = v_x + smoothed_x * v_w
            target_y_px = v_y + smoothed_y * v_h
            
            # Clamp coordinates to keep the cursor within the virtual screen boundary
            target_x_px = max(v_x, min(v_x + v_w - 1, target_x_px))
            target_y_px = max(v_y, min(v_y + v_h - 1, target_y_px))
            
            pyautogui.moveTo(int(target_x_px), int(target_y_px))
            
            # Re-sync internal tracker with actual OS cursor position to prevent getting stuck in dead space.
            real_x, real_y = pyautogui.position()
            
            # Map back to normalized coordinates to keep the math consistent regardless of resolution
            smoothed_x = (real_x - v_x) / v_w
            smoothed_y = (real_y - v_y) / v_h

def print_gesture(result, output_image, timestamp_ms):
    global last_gesture, smoothed_x, smoothed_y, is_clicking
    
    display_name = None
    track_index_tip = None
    has_left_fist = False
    is_right_pointing = False

    if result.hand_landmarks and result.handedness:
        # Loop through all detected hands to identify states
        for index, landmarks in enumerate(result.hand_landmarks):
            # Assign handedness based on MediaPipe's classification
            handedness_label = result.handedness[index][0].category_name
            is_right_hand = (handedness_label == 'Right')
            is_left_hand = (handedness_label == 'Left')
            
            current_hand_gesture = None
            
            # Read predefined gesture if available for this specific hand
            if result.gestures and len(result.gestures) > index:
                category = result.gestures[index][0].category_name
                if category == 'Open_Palm':
                    current_hand_gesture = 'Open Palm'
                elif category == 'Closed_Fist':
                    current_hand_gesture = 'Closed Palm'
                    if is_left_hand:
                        has_left_fist = True

            # Extract necessary landmarks
            thumb_tip = landmarks[4]
            index_tip = landmarks[8]
            index_mcp = landmarks[5]
            wrist = landmarks[0]
            middle_tip = landmarks[12]
            middle_mcp = landmarks[9]
            ring_tip = landmarks[16]
            ring_mcp = landmarks[13]
            pinky_tip = landmarks[20]
            pinky_mcp = landmarks[17]

            # Check if this hand is pointing (Only allow RIGHT hand to point)
            if is_right_hand:
                # We verify the index finger is physically extended (tip is further from wrist than the knuckle)
                is_index_extended = get_distance(index_tip, wrist) > get_distance(index_mcp, wrist)
                is_index_forward = index_tip.z < -0.05 and index_tip.z < index_mcp.z
                is_middle_folded = get_distance(middle_tip, wrist) < get_distance(middle_mcp, wrist)
                is_ring_folded = get_distance(ring_tip, wrist) < get_distance(ring_mcp, wrist)
                is_pinky_folded = get_distance(pinky_tip, wrist) < get_distance(pinky_mcp, wrist)

                # Prevent a recognized closed fist from accidentally being misclassified as pointing
                if current_hand_gesture != 'Closed Palm' and is_index_extended and is_index_forward and is_middle_folded and is_ring_folded and is_pinky_folded:
                    current_hand_gesture = 'Pointing'
                    track_index_tip = index_tip
                    is_right_pointing = True
                
            # If we don't have a primary display name yet or we found pointing (which is highest priority), update it
            if current_hand_gesture == 'Pointing':
                display_name = 'Pointing'
            elif not display_name and current_hand_gesture:
                display_name = current_hand_gesture

    # Process Cursor Movement
    if is_right_pointing and track_index_tip:
        on_pointing(track_index_tip.x, track_index_tip.y)
        
        # Process Mouse Click logic: Ensure left hand is a fist while tracking right hand
        if has_left_fist and not is_clicking:
            pyautogui.click()
            is_clicking = True
            print("Action triggered: Left Click (Left Hand Fist)")
        elif not has_left_fist and is_clicking:
            is_clicking = False
            
    else:
        # If we lost tracking or stopped pointing, reset click state
        if is_clicking:
            is_clicking = False

    # For general gesture console spam prevention 
    if display_name and display_name != last_gesture:
        if display_name == 'Open Palm':
            on_open_palm()
        elif display_name == 'Closed Palm':
            on_closed_palm()
        elif display_name == 'Pointing':
            print("Action triggered: Pointing (Cursor Tracking)")
            
        last_gesture = display_name
    elif not display_name:
        last_gesture = None
        smoothed_x = None
        smoothed_y = None

# Create a gesture recognizer instance
options = GestureRecognizerOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    running_mode=VisionRunningMode.LIVE_STREAM,
    num_hands=2,
    result_callback=print_gesture
)

def main():
    print("Starting webcam reader... (No UI will be shown. Press Ctrl+C in terminal to stop)")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    timestamp = 0
    with GestureRecognizer.create_from_options(options) as recognizer:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame")
                break
            
            # Convert the frame to RGB as required by MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            
            # Recognize gestures asynchronously
            timestamp += 1
            recognizer.recognize_async(mp_image, timestamp)
            
            # Sleep briefly to reduce CPU load and allow callback to process
            time.sleep(0.03)

    cap.release()

if __name__ == "__main__":
    main()
