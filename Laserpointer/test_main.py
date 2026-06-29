"""Tests for the Laserpointer FastAPI service.

Runs entirely in simulation mode; no Arduino hardware is required.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from . import main


@pytest.fixture(autouse=True)
def force_simulation_mode(monkeypatch):
    """Keep tests independent of whatever hardware happens to be plugged in."""
    monkeypatch.setattr(main, "arduino", None)
    monkeypatch.setattr(main, "find_arduino_port", lambda: None)
    main.current_laser_status.update({"mode": "simulation", "connected_port": None})


@pytest.fixture
def client():
    return TestClient(main.app)


# --- map_to_servo_angles ---


def test_map_to_servo_angles_center():
    assert main.map_to_servo_angles(0.5, 0.5) == (90, 45)


def test_map_to_servo_angles_origin():
    assert main.map_to_servo_angles(0.0, 0.0) == (0, 90)


def test_map_to_servo_angles_max():
    assert main.map_to_servo_angles(1.0, 1.0) == (180, 0)


# --- build_servo_command ---


def test_build_servo_command_format():
    assert main.build_servo_command(90, 45) == "X90Y45\n"


# --- is_disable_request / validate_coordinates ---


def test_is_disable_request_true():
    req = main.LaserRequest(x=-1.0, y=-1.0, confidence=1.0)
    assert main.is_disable_request(req) is True


def test_is_disable_request_false():
    req = main.LaserRequest(x=0.5, y=0.5, confidence=1.0)
    assert main.is_disable_request(req) is False


def test_validate_coordinates_accepts_disable():
    req = main.LaserRequest(x=-1.0, y=-1.0, confidence=1.0)
    main.validate_coordinates(req)


def test_validate_coordinates_accepts_in_range():
    req = main.LaserRequest(x=0.2, y=0.8, confidence=0.5)
    main.validate_coordinates(req)


def test_validate_coordinates_rejects_partial_disable():
    req = main.LaserRequest(x=-1.0, y=0.4, confidence=1.0)
    with pytest.raises(HTTPException):
        main.validate_coordinates(req)


def test_validate_coordinates_rejects_out_of_range():
    req = main.LaserRequest(x=1.5, y=0.5, confidence=1.0)
    with pytest.raises(HTTPException):
        main.validate_coordinates(req)


# --- HTTP endpoints (simulation mode) ---


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["service"] == "laserpointer"
    assert body["connected"] is False


def test_laser_endpoint_simulated_targeting(client):
    response = client.post("/laser", json={"x": 0.5, "y": 0.5, "confidence": 1.0})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["servo"] == {"x": 90, "y": 45}
    assert "(simulated)" in body["message"]


def test_laser_endpoint_disable(client):
    response = client.post("/laser", json={"x": -1.0, "y": -1.0, "confidence": 1.0})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["servo"] == {"x": main.SERVO_CENTER_X, "y": main.SERVO_CENTER_Y}


def test_laser_endpoint_rejects_partial_disable(client):
    response = client.post("/laser", json={"x": -1.0, "y": 0.4, "confidence": 1.0})
    assert response.status_code == 400


def test_laser_endpoint_rejects_out_of_range(client):
    response = client.post("/laser", json={"x": 2.0, "y": 0.5, "confidence": 1.0})
    assert response.status_code == 400


def test_laser_health_endpoint(client):
    client.post("/laser", json={"x": 0.25, "y": 0.75, "confidence": 0.9})
    response = client.get("/laser/health")
    assert response.status_code == 200
    body = response.json()
    assert body["arduino_running"] is False
    assert body["status"]["target_x"] == 0.25
    assert body["status"]["target_y"] == 0.75
