from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from pydantic import BaseModel, Field

app = FastAPI(title="MediaPipe Config API")

# Allow React to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your React app's URL
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = "config.json"

# Models for validation
class ConfigModel(BaseModel):
    SMOOTHING_FACTOR: float
    SENSITIVITY: float
    Y_OFFSET: float
    DEADZONE: float
    COMMAND_COOLDOWN: float

class SingleValueModel(BaseModel):
    value: float

def read_config():
    if not os.path.exists(CONFIG_PATH):
        raise HTTPException(status_code=404, detail="Configuration file not found. Run main.py first.")
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {str(e)}")

def write_config(config_dict):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config_dict, f, indent=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {str(e)}")


# 1. Global Config Endpoints
@app.get("/config", response_model=ConfigModel)
def get_config():
    """Retrieve the entire configuration."""
    return read_config()

@app.post("/config")
def update_config(config: ConfigModel):
    """Overwrite the entire configuration."""
    write_config(config.dict())
    return {"status": "success", "config": config}


# 2. Individual Config Endpoints
def update_single_config(key: str, value: float):
    config = read_config()
    if key not in config:
        raise HTTPException(status_code=400, detail=f"Invalid configuration key: {key}")
    config[key] = value
    write_config(config)
    return {"status": "success", key: value}

@app.post("/config/smoothing_factor")
def update_smoothing_factor(data: SingleValueModel):
    return update_single_config("SMOOTHING_FACTOR", data.value)

@app.post("/config/sensitivity")
def update_sensitivity(data: SingleValueModel):
    return update_single_config("SENSITIVITY", data.value)

@app.post("/config/y_offset")
def update_y_offset(data: SingleValueModel):
    return update_single_config("Y_OFFSET", data.value)

@app.post("/config/deadzone")
def update_deadzone(data: SingleValueModel):
    return update_single_config("DEADZONE", data.value)

@app.post("/config/command_cooldown")
def update_command_cooldown(data: SingleValueModel):
    return update_single_config("COMMAND_COOLDOWN", data.value)
