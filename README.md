# Spatial Mouse and Dictation Controller

This application uses your webcam and Google's MediaPipe Machine Learning framework to create a completely hands-free spatial mouse and dictation controller. It runs headlessly (no UI) in the background and scales seamlessly across multi-monitor setups.

## Features
- **Right Hand Cursor Tracking**: Point at the screen with your right index finger to move the mouse.
- **Right Hand Scrolling**: Hold an Open Palm to "grab" the screen and drag it around omni-directionally (like a touchscreen). 
- **Left Hand Clicking**: Make a completely closed fist with your left hand to simulate a left mouse click (while pointing with your right hand).
- **Left Hand Dictation**: Point your left index finger straight up to automatically toggle the Windows Native Dictation overlay (`Win + H`).
- **In-Dictation Operations**: While dictating, make a closed fist with your right hand to press the `Enter` key.
- **Forward/Backward Navigation**: When neither pointing nor dictating, make a closed fist with your right hand to navigate Forward (Browser Forward) or your left hand to navigate Backward (Browser Back).
- **Hot-Reloadable Physics**: Tweak sensitivity, smoothing, and deadzones dynamically without restarting the script.

## System Requirements
- Windows OS (Relies heavily on Win32 API for multi-monitor DPI scaling and the `Win + H` dictation hotkey).
- A connected webcam.
- Python 3.8 to 3.11 recommended (for MediaPipe compatibility).

## Setup Instructions (Virtual Environment)
It is highly recommended to run this application inside an isolated Python virtual environment (`venv`) to avoid dependency conflicts.

1. **Open your terminal or PowerShell** in the project directory.
2. **Create the virtual environment**:
   ```powershell
   python -m venv venv
   ```
3. **Activate the virtual environment**:
   ```powershell
   .\venv\Scripts\activate
   ```
   *(Note: If you run into Execution Policy errors on Windows, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` first).*
4. **Install the required Python packages**:
   ```powershell
   pip install mediapipe opencv-python pyautogui fastapi uvicorn pydantic
   ```

## Running the Application

Ensure your virtual environment is activated (you should see `(venv)` at the beginning of your terminal prompt).

You can run both the background tracker and the configuration API simultaneously from a single terminal:
```powershell
python main.py
```
- **First Time Run**: It will automatically download the `gesture_recognizer.task` ML model from Google's servers and generate a `config.json` file.
- **API Access**: The API will be available at http://localhost:8000. Interactive documentation is at http://localhost:8000/docs.
- **Shutting Down**: Press `Ctrl + C` in the terminal to gracefully terminate both the webcam tracking feed and the API server at the same time.

### Endpoints Provided via API:
This API allows external apps (like your React frontend) to safely make programmatic changes to the `config.json` file on the fly (which the python tracker automatically detects and streams).

- `GET /config` returns the current JSON.
- `POST /config` overwrites the full JSON.
- `POST /config/smoothing_factor` (Requires payload `{ "value": 0.5 }`)
- `POST /config/sensitivity` 
- `POST /config/y_offset` 
- `POST /config/deadzone` 
- `POST /config/command_cooldown` 
- `POST /config/scrolling_sensitivity`

## Real-Time Configuration (`config.json`)
Upon running, the script creates `config.json`. You can modify these physics and tracking variables on the fly. Whenever you hit `Save`, the active Python script will instantly update the tracking engine.

| Option | Description |
|--------|-------------|
| `SMOOTHING_FACTOR` | `0.0` to `1.0`. Lower is smoother but adds cursor trailing lag. Higher tracks snappier but is more jittery. |
| `SENSITIVITY` | Multiplier for how minimal hand movements stretch across the virtual display space. |
| `Y_OFFSET` | `0.0` to `1.0`. Offsets the baseline vertical center if your cursor naturally aligns too high/low compared to your physical hand. |
| `DEADZONE` | Normalized scale (`0.0` to `1.0`) of the breakout zone. Your finger must translate outside this zone to snap the mathematical lock and move the cursor (prevents micro-shaking). |
| `COMMAND_COOLDOWN` | Total seconds mandated between actions like Mouse Clicks and Enter keypresses to prevent accidental double/triple firing. Cursor tracking ignores this cooldown. |
| `SCROLLING_SENSITIVITY` | Scale factor to adjust specifically how fast omni-directional scrolling occurs with an open palm. Defaults to `1.0`. |