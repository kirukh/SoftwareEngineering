@echo off

REM VISUAL
start cmd /k "cd /d %~dp0visual && python server.py"

REM LASER
start cmd /k "cd /d %~dp0Laserpointer && python -m uvicorn main:app --reload --port 8004"

REM INTERFACES CONTROLLER
start cmd /k "cd /d %~dp0Interfaces && python -m uvicorn controller:app --reload --port 7979"

REM AUDIO INTERFACE
start cmd /k "cd /d %~dp0Interfaces\FastAPI && python -m uvicorn audio_interface:app --reload --port 7980"

REM AUDIO CONTROLLER
start cmd /k "cd /d %~dp0Audio\Roboter_Code && python -m uvicorn audio_controller:app --reload --port 8011"

REM MICROPHONE
start cmd /k "cd /d %~dp0Audio\Microphone_Code && python audio_main.py"