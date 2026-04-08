import cv2
import os
import time
import math
import urllib.request
import pyautogui
import ctypes
import json
import queue

# ==============================================================================
# CONFIGURATION OPTIONS (Defaults, dynamically overridden by config.json)
# ==============================================================================
SMOOTHING_FACTOR = 0.15  # Cursor smoothing: Lower is smoother but adds more lag (0.0 to 1.0)
SENSITIVITY = 2.5				 # Cursor tracking sensitivity (multiplier for how much hand movement translates to cursor movement)
Y_OFFSET = 0.2           # Vertical offset for pointing coordinate mapping (0.0 to 1.0, where 0.0 is no offset and 1.0 is a full screen height offset)
DEADZONE = 0.05          # Normalized distance (0.0 to 1.0) of movement required to break deadzone
COMMAND_COOLDOWN = 1.0   # Cooldown between operations
SCROLLING_SENSITIVITY = 0.75 # Sensitivity multiplier for scrolling amount
EDGE_THRESHOLD = 0.15    # Margin at edge of camera view to invoke sticky scrolling (0.0 to 1.0)
STICKY_THRESHOLD = 150.0 # Additional velocity/distance required to break scrolling anchor when at the edge
# ==============================================================================

def reload_config():
    global SMOOTHING_FACTOR, SENSITIVITY, Y_OFFSET, DEADZONE, COMMAND_COOLDOWN, SCROLLING_SENSITIVITY, EDGE_THRESHOLD, STICKY_THRESHOLD
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            SMOOTHING_FACTOR = config.get("SMOOTHING_FACTOR", SMOOTHING_FACTOR)
            SENSITIVITY = config.get("SENSITIVITY", SENSITIVITY)
            Y_OFFSET = config.get("Y_OFFSET", Y_OFFSET)
            DEADZONE = config.get("DEADZONE", DEADZONE)
            COMMAND_COOLDOWN = config.get("COMMAND_COOLDOWN", COMMAND_COOLDOWN)
            SCROLLING_SENSITIVITY = config.get("SCROLLING_SENSITIVITY", SCROLLING_SENSITIVITY)
            EDGE_THRESHOLD = config.get("EDGE_THRESHOLD", EDGE_THRESHOLD)
            STICKY_THRESHOLD = config.get("STICKY_THRESHOLD", STICKY_THRESHOLD)
    except Exception as e:
        pass # Ignore errors on read (e.g. file lock during write)

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

# Queue for sending frames to feed.py
global_frame_queue = None

# Track enter key press state during dictation
is_pressing_enter = False

# Track dictation state
is_dictating = False
last_dictation_detected_time = 0
last_dictation_toggled_time = 0

# Track navigation state
last_nav_command_time = 0

# Track scrolling state
is_scrolling = False
scroll_anchor_x = None
scroll_anchor_y = None

def get_distance(p1, p2):
    z1 = getattr(p1, 'z', 0)
    z2 = getattr(p2, 'z', 0)
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (z1 - z2)**2)

# Scaffolded methods for each gesture
def on_open_palm():
    print("Action triggered: Open Palm")

def on_closed_palm():
    print("Action triggered: Closed Palm")

def on_pointing(mcp, tip):
    global smoothed_x, smoothed_y
    
    # Calculate Directional Vector (Raycast) from Knuckle (mcp) to Fingertip (tip)
    ray_dx = tip.x - mcp.x
    ray_dy = tip.y - mcp.y
    
    # The new target coordinate is where the mathematical "laser" points.
    # Instead of hardcoding a massive 4.0 multiplier, we let the SENSITIVITY from config.json govern this entirely.
    # This restores 0.05 vs 2.5 logical scaling for the user sliders.
    raw_x_norm = mcp.x + (ray_dx * SENSITIVITY)
    raw_y_norm = mcp.y + (ray_dy * SENSITIVITY)
    
    # Retrieve the full virtual screen bounding box across all connected monitors
    # This native Windows API considers primary monitor position (0,0), DPI, and relative secondary monitor layouts.
    user32 = ctypes.windll.user32
    v_x = user32.GetSystemMetrics(76) # SM_XVIRTUALSCREEN
    v_y = user32.GetSystemMetrics(77) # SM_YVIRTUALSCREEN
    v_w = user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
    v_h = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
    
    # -------------------------------------------------------------------------
    # Apply sensitivity and vertical offset
    # First, center coordinates around 0.5 (the middle of the camera feed)
    # We invert the X axis (1.0 - raw_x_norm) because webcams are mirrored by default
    centered_x = 1.0 - raw_x_norm
    centered_y = raw_y_norm
    
    # We now strictly map the sensitivity entirely by amplifying the calculated vector length
    # instead of stacking multiple multipliers. 
    # That means to hit corners faster, we just increase sensitivity.
    target_x_norm = ((centered_x - 0.5) * SENSITIVITY) + 0.5
    target_y_norm = ((centered_y - 0.5 - Y_OFFSET) * SENSITIVITY) + 0.5
    
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
    global last_gesture, smoothed_x, smoothed_y, is_clicking, is_dictating, is_pressing_enter, last_dictation_detected_time, last_dictation_toggled_time, last_nav_command_time, is_scrolling, scroll_anchor_x, scroll_anchor_y, global_frame_queue
    
    display_name = None
    track_index_tip = None
    track_index_mcp = None
    track_palm_center = None
    has_left_fist = False
    has_right_fist = False
    is_right_pointing = False
    is_right_open_palm = False
    is_left_pointing_up = False

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
                    elif is_right_hand:
                        has_right_fist = True

            # Extract necessary landmarks
            thumb_tip = landmarks[4]
            index_tip = landmarks[8]
            index_pip = landmarks[6]
            index_mcp = landmarks[5]
            wrist = landmarks[0]
            middle_tip = landmarks[12]
            middle_pip = landmarks[10]
            middle_mcp = landmarks[9]
            ring_tip = landmarks[16]
            ring_pip = landmarks[14]
            ring_mcp = landmarks[13]
            pinky_tip = landmarks[20]
            pinky_pip = landmarks[18]
            pinky_mcp = landmarks[17]

            # Common finger fold states
            # A finger is extended if its tip is further from the wrist than its PIP (middle) joint.
            # A finger is folded if its tip is curled back, making it closer to the wrist than its PIP joint.
            is_index_extended = get_distance(index_tip, wrist) > get_distance(index_pip, wrist)
            is_middle_folded = get_distance(middle_tip, wrist) < get_distance(middle_pip, wrist)
            is_ring_folded = get_distance(ring_tip, wrist) < get_distance(ring_pip, wrist)
            is_pinky_folded = get_distance(pinky_tip, wrist) < get_distance(pinky_pip, wrist)

            # Check if this hand is pointing (Only allow RIGHT hand to point)
            if is_right_hand:
                # We removed the z-axis forward constraint to allow pointing down towards bottom monitors
                
                # Prevent a recognized closed fist from accidentally being misclassified as pointing
                if current_hand_gesture != 'Closed Palm' and is_index_extended and is_middle_folded and is_ring_folded and is_pinky_folded:
                    current_hand_gesture = 'Pointing'
                    track_index_tip = index_tip
                    track_index_mcp = index_mcp
                    is_right_pointing = True
                elif current_hand_gesture == 'Open Palm':
                    is_right_open_palm = True
                    # Use center of the palm (midpoint between wrist and middle finger MCP) as a stable anchor
                    class PalmCenter:
                        def __init__(self, x, y):
                            self.x = x
                            self.y = y
                    track_palm_center = PalmCenter((wrist.x + middle_mcp.x) / 2.0, (wrist.y + middle_mcp.y) / 2.0)
                    
            elif is_left_hand:
                # Left hand uses "Pointing Up" for dictation
                is_index_forward = index_tip.z < -0.05 and index_tip.z < index_mcp.z
                # Pointing Up: y is smaller (higher in image), z is not deeply forward
                is_index_up = index_tip.y < index_mcp.y and not is_index_forward
                
                # Make sure dictation "Pointing Up" gesture is cleanly detected
                if current_hand_gesture != 'Closed Palm' and is_index_extended and is_index_up and is_middle_folded and is_ring_folded and is_pinky_folded:
                    current_hand_gesture = 'Pointing Up'
                    is_left_pointing_up = True
                
            # If we don't have a primary display name yet or we found pointing (which is highest priority), update it
            if current_hand_gesture == 'Pointing':
                display_name = 'Pointing'
            elif current_hand_gesture == 'Pointing Up' and display_name != 'Pointing':
                display_name = 'Pointing Up'
            elif not display_name and current_hand_gesture:
                display_name = current_hand_gesture

    # Process Cursor Movement
    if is_right_pointing and track_index_tip:
        on_pointing(track_index_mcp, track_index_tip)
        
        # Process Mouse Click logic: Ensure left hand is a fist while tracking right hand
        if has_left_fist and not is_clicking:
            pyautogui.click()
            is_clicking = True
            print("Action triggered: Left Click (Left Hand Fist)")
        elif not has_left_fist and is_clicking:
            is_clicking = False
            
    elif is_right_open_palm and track_palm_center:
        # Scrolling logic: Act like dragging a touchscreen
        if not is_scrolling:
            is_scrolling = True
            scroll_anchor_x = track_palm_center.x
            scroll_anchor_y = track_palm_center.y
            print("Action triggered: Omni-directional Scrolling Started")
        else:
            delta_x = track_palm_center.x - scroll_anchor_x
            delta_y = track_palm_center.y - scroll_anchor_y
            
            # Map physical movement back into touchscreen-style reversed scrolling
            # The SCROLLING_SENSITIVITY from config controls the scroll speed,
            # compounded with the baseline SENSITIVITY.
            SCROLL_MULTIPLIER = 5000 * SENSITIVITY * SCROLLING_SENSITIVITY
            
            scroll_amount_y = int(-delta_y * SCROLL_MULTIPLIER)
            scroll_amount_x = int(delta_x * SCROLL_MULTIPLIER)
            
            # Apply Vertical Scroll
            # Implement sticky edges to prevent scroll bouncing when exiting at extremes
            scaled_sticky_threshold = STICKY_THRESHOLD * SENSITIVITY * SCROLLING_SENSITIVITY
            
            threshold_y = 15
            # Apply sticky deadzone symmetrically when at the vertical edges to prevent ratcheting jitter
            if track_palm_center.y > (1.0 - EDGE_THRESHOLD) or track_palm_center.y < EDGE_THRESHOLD:
                threshold_y = scaled_sticky_threshold
                
            threshold_x = 15
            # Apply sticky deadzone symmetrically when at the horizontal edges
            if track_palm_center.x > (1.0 - EDGE_THRESHOLD) or track_palm_center.x < EDGE_THRESHOLD:
                threshold_x = scaled_sticky_threshold

            if abs(scroll_amount_y) > threshold_y:
                pyautogui.scroll(scroll_amount_y)
                # We update the anchor by the portion we actually "consumed" as scroll
                scroll_anchor_y = track_palm_center.y
                
            # Apply Horizontal Scroll (Note: not all Windows applications support hscroll equally)
            if abs(scroll_amount_x) > threshold_x:
                try:
                    pyautogui.hscroll(scroll_amount_x)
                except Exception:
                    pass
                scroll_anchor_x = track_palm_center.x

        if is_clicking:
            is_clicking = False
    else:
        # If we lost tracking or stopped pointing/scrolling, reset relevant states
        is_scrolling = False
        scroll_anchor_x = None
        scroll_anchor_y = None
        if is_clicking:
            is_clicking = False

    # Process Dictation logic: Ensure pointing up enables microphone
    current_time = time.time()
    if is_left_pointing_up:
        last_dictation_detected_time = current_time
        
        # Start dictation if not already dictating and at least 1s since last toggle to avoid OS spamming
        if not is_dictating and (current_time - last_dictation_toggled_time > 1.0):
            is_dictating = True
            last_dictation_toggled_time = current_time
            print("Action triggered: Dictation Started (Listening via Windows Native OS...)")
            # Toggles on Native Windows Dictation (Realtime, high accuracy, types as you speak)
            pyautogui.hotkey('win', 'h')
            
        # Process "Enter" logic: Ensure right hand is a fist while dictating
        if has_right_fist and not is_pressing_enter:
            is_pressing_enter = True
            print("Action triggered: Enter Key Pressed (Right Hand Fist during Dictation)")
            pyautogui.press('enter')
        elif not has_right_fist and is_pressing_enter:
            is_pressing_enter = False
            
    else:
        # Buffer for tracking loss: Wait 0.6 seconds of NO gesture before stopping
        if is_dictating and (current_time - last_dictation_detected_time > 0.6):
            # Also ensure we don't rapid-fire hotkeys faster than Windows can physically open/close the overlay
            if (current_time - last_dictation_toggled_time > 1.0):
                is_dictating = False
                last_dictation_toggled_time = current_time
                print("Action triggered: Dictation Stopped")
                # Turn it off again by re-toggling 
                pyautogui.hotkey('win', 'h')
            
        if is_pressing_enter:
            is_pressing_enter = False

    # Process Forward/Backward Navigation logic:
    # Only if dictation and cursor tracking are strictly NOT active
    if not is_dictating and not is_right_pointing:
        # Rate limit navigation to avoid rapidly skipping multiple pages
        if current_time - last_nav_command_time > COMMAND_COOLDOWN:
            if has_right_fist:
                print("Action triggered: Navigation Forward (Right Hand Fist)")
                pyautogui.hotkey('browserforward') # Equivalent to Alt+Right
                last_nav_command_time = current_time
            elif has_left_fist:
                print("Action triggered: Navigation Backward (Left Hand Fist)")
                pyautogui.hotkey('browserback') # Equivalent to Alt+Left
                last_nav_command_time = current_time

    # For general gesture console spam prevention 
    if display_name and display_name != last_gesture:
        if display_name == 'Open Palm':
            on_open_palm()
        elif display_name == 'Closed Palm':
            on_closed_palm()
        elif display_name == 'Pointing':
            print("Action triggered: Pointing (Cursor Tracking)")
        elif display_name == 'Pointing Up':
            pass # Handled continuously above
            
        last_gesture = display_name
    elif not display_name:
        last_gesture = None
        smoothed_x = None
        smoothed_y = None

    if global_frame_queue is not None:
        try:
            annotated_image = output_image.numpy_view().copy()
            import cv2
            
            # Map normalized coordinates back to pixel coordinates
            h, w, c = annotated_image.shape
            
            if result.hand_landmarks:
                for hand_landmarks in result.hand_landmarks:
                    # Draw a simplified skeleton (just the dots for joints and fingertips)
                    for landmark in hand_landmarks:
                        cx, cy = int(landmark.x * w), int(landmark.y * h)
                        if 0 <= cx < w and 0 <= cy < h:
                            cv2.circle(annotated_image, (cx, cy), 5, (0, 255, 0), -1)

            # Convert RGB back to BGR for OpenCV
            bgr_image = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)
            global_frame_queue.put_nowait(bgr_image)
        except queue.Full:
            pass
        except Exception as e:
            pass

# Create a gesture recognizer instance
options = GestureRecognizerOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    running_mode=VisionRunningMode.LIVE_STREAM,
    num_hands=2,
    result_callback=print_gesture
)

def main_loop(frame_queue=None):
    global is_dictating, last_dictation_detected_time, last_dictation_toggled_time, global_frame_queue
    global_frame_queue = frame_queue
    
    print("Starting webcam reader... (No UI will be shown. Press Ctrl+C in terminal to stop)")
    
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    timestamp = 0
    last_config_check_time = 0
    
    with GestureRecognizer.create_from_options(options) as recognizer:
        while True:
            # Regularly check if config.json has been updated by the API
            current_time = time.time()
            if current_time - last_config_check_time > 1.0:
                reload_config()
                last_config_check_time = current_time
                
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
            
            # Redundancy check: Ensure dictation is deactivated if the hand is out of frame
            current_time = time.time()
            if is_dictating and (current_time - last_dictation_detected_time > 1.5):
                # Only try to toggle off if we haven't recently tried
                if (current_time - last_dictation_toggled_time > 2.0):
                    is_dictating = False
                    last_dictation_toggled_time = current_time
                    print("Redundancy triggered: Dictation Stopped (Hand left view)")
                    pyautogui.hotkey('win', 'h')

    cap.release()

if __name__ == "__main__":
    main_loop()
