import cv2
import os
import time
import math
import urllib.request
import pyautogui

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

# Variables for cursor smoothing (Exponential Moving Average)
smoothed_x = None
smoothed_y = None
SMOOTHING_FACTOR = 0.15  # Lower is smoother but adds more lag (0.0 to 1.0)

# Cursor tracking calibration
SENSITIVITY = 2.5      
Y_OFFSET = 0.2

# Track mouse button click state
is_clicking = False

def get_distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

# Scaffolded methods for each gesture
def on_open_palm():
    print("Action triggered: Open Palm")

def on_closed_palm():
    print("Action triggered: Closed Palm")

def on_ok_sign():
    print("Action triggered: OK Sign")

def on_pointing(x_norm, y_norm):
    global smoothed_x, smoothed_y
    
    # Retrieve screen dimensions
    screen_w, screen_h = pyautogui.size()
    
    # Apply sensitivity and vertical offset
    # First, center coordinates around 0.5 (the middle of the camera feed)
    # We invert the X axis (1.0 - x) because webcams are mirrored by default
    centered_x = (1.0 - x_norm) - 0.5
    centered_y = (y_norm - Y_OFFSET) - 0.5
    
    # Multiply by sensitivity, then shift back to a 0.0-1.0 range mapped to screen pixels
    target_x = (centered_x * SENSITIVITY + 0.5) * screen_w
    target_y = (centered_y * SENSITIVITY + 0.5) * screen_h
    
    # Clamp coordinates to keep the cursor from crashing PyAutoGUI when going off-screen
    target_x = max(0, min(screen_w, target_x))
    target_y = max(0, min(screen_h, target_y))
    
    # Apply Exponential Moving Average (EMA) smoothing
    if smoothed_x is None or smoothed_y is None:
        smoothed_x = target_x
        smoothed_y = target_y
    else:
        smoothed_x = (smoothed_x * (1 - SMOOTHING_FACTOR)) + (target_x * SMOOTHING_FACTOR)
        smoothed_y = (smoothed_y * (1 - SMOOTHING_FACTOR)) + (target_y * SMOOTHING_FACTOR)
    
    # Move the cursor
    pyautogui.moveTo(int(smoothed_x), int(smoothed_y))

def print_gesture(result, output_image, timestamp_ms):
    global last_gesture, smoothed_x, smoothed_y, is_clicking
    
    display_name = None
    track_index_tip = None
    has_fist = False
    fist_hand_index = -1
    pointing_hand_index = -1

    if result.hand_landmarks:
        # Loop through all detected hands to identify states
        for index, landmarks in enumerate(result.hand_landmarks):
            current_hand_gesture = None
            
            # Read predefined gesture if available for this specific hand
            if result.gestures and len(result.gestures) > index:
                category = result.gestures[index][0].category_name
                if category == 'Open_Palm':
                    current_hand_gesture = 'Open Palm'
                elif category == 'Closed_Fist':
                    current_hand_gesture = 'Closed Palm'
                    has_fist = True
                    fist_hand_index = index

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

            thumb_index_distance = get_distance(thumb_tip, index_tip)
            middle_extended = get_distance(middle_tip, wrist) > get_distance(middle_mcp, wrist)

            if thumb_index_distance < 0.05 and middle_extended:
                current_hand_gesture = 'OK Sign'

            # Check if this hand is pointing
            is_index_forward = index_tip.z < -0.05 and index_tip.z < index_mcp.z
            is_middle_folded = get_distance(middle_tip, wrist) < get_distance(middle_mcp, wrist)
            is_ring_folded = get_distance(ring_tip, wrist) < get_distance(ring_mcp, wrist)
            is_pinky_folded = get_distance(pinky_tip, wrist) < get_distance(pinky_mcp, wrist)

            if is_index_forward and is_middle_folded and is_ring_folded and is_pinky_folded:
                # Only allow the first detected pointing hand to control the cursor
                if pointing_hand_index == -1:
                    current_hand_gesture = 'Pointing'
                    track_index_tip = index_tip
                    pointing_hand_index = index
                
            # If we don't have a primary display name yet or we found pointing (which is highest priority), update it
            if current_hand_gesture == 'Pointing':
                display_name = 'Pointing'
            elif not display_name and current_hand_gesture:
                display_name = current_hand_gesture

    # Process Cursor Movement
    if display_name == 'Pointing' and track_index_tip:
        on_pointing(track_index_tip.x, track_index_tip.y)
        
        # Process Mouse Click logic: Ensure fist is from a DIFFERENT hand than the pointing hand
        valid_fist_click = has_fist and (fist_hand_index != pointing_hand_index) and (fist_hand_index != -1)

        if valid_fist_click and not is_clicking:
            pyautogui.click()
            is_clicking = True
            print("Action triggered: Left Click")
        elif not valid_fist_click and is_clicking:
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
        elif display_name == 'OK Sign':
            on_ok_sign()
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
