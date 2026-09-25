"""Constant-velocity Kalman filter for image-plane boxes."""

from __future__ import annotations

import numpy as np


def box_to_measurement(box: np.ndarray) -> np.ndarray:
    x1, y1, x2, y2 = map(float, box)
    return np.array([(x1 + x2) / 2, (y1 + y2) / 2, max(1e-3, x2 - x1), max(1e-3, y2 - y1)], dtype=np.float64)


def measurement_to_box(measurement: np.ndarray) -> np.ndarray:
    cx, cy, width, height = measurement[:4]
    width, height = max(1e-3, float(width)), max(1e-3, float(height))
    return np.array([cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2], dtype=np.float32)


class KalmanBoxFilter:
    """State is [cx, cy, vx, vy, width, height]."""

    def __init__(self, box: np.ndarray, timestamp: float, process_noise: float = 1.0, measurement_noise: float = 4.0):
        self.state = np.zeros(6, dtype=np.float64)
        measurement = box_to_measurement(box)
        self.state[[0, 1, 4, 5]] = measurement
        self.covariance = np.diag([measurement_noise**2, measurement_noise**2, 100.0, 100.0, measurement_noise**2, measurement_noise**2])
        self.process_noise = float(process_noise)
        self.measurement_noise = float(measurement_noise)
        self.timestamp = float(timestamp)

    def _matrices(self, dt: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        transition = np.eye(6, dtype=np.float64)
        transition[0, 2] = dt
        transition[1, 3] = dt
        observation = np.zeros((4, 6), dtype=np.float64)
        observation[0, 0] = 1.0
        observation[1, 1] = 1.0
        observation[2, 4] = 1.0
        observation[3, 5] = 1.0
        q = max(dt, 1e-6) * self.process_noise
        process = np.diag([q, q, q * 4, q * 4, q, q])
        return transition, observation, process

    def predict(self, timestamp: float) -> tuple[np.ndarray, np.ndarray, float]:
        current = float(timestamp)
        dt = current - self.timestamp
        if not np.isfinite(dt) or dt < 0:
            raise ValueError(f"timestamp must be finite and monotonic, got dt={dt!r}")
        transition, _, process = self._matrices(dt)
        self.state = transition @ self.state
        self.covariance = transition @ self.covariance @ transition.T + process
        self.timestamp = current
        return measurement_to_box(np.array([self.state[0], self.state[1], self.state[4], self.state[5]])), self.covariance.copy(), dt

    def update(self, box: np.ndarray, timestamp: float) -> np.ndarray:
        if float(timestamp) < self.timestamp:
            raise ValueError("measurement timestamp precedes filter timestamp")
        if float(timestamp) > self.timestamp:
            self.predict(float(timestamp))
        _, observation, _ = self._matrices(0.0)
        measurement = box_to_measurement(box)
        noise = np.eye(4, dtype=np.float64) * self.measurement_noise**2
        innovation = measurement - observation @ self.state
        innovation_covariance = observation @ self.covariance @ observation.T + noise
        gain = self.covariance @ observation.T @ np.linalg.pinv(innovation_covariance)
        self.state = self.state + gain @ innovation
        identity = np.eye(6, dtype=np.float64)
        self.covariance = (identity - gain @ observation) @ self.covariance
        self.timestamp = float(timestamp)
        return measurement_to_box(np.array([self.state[0], self.state[1], self.state[4], self.state[5]]))

    def mahalanobis(self, box: np.ndarray) -> float:
        _, observation, _ = self._matrices(0.0)
        measurement = box_to_measurement(box)
        residual = measurement - observation @ self.state
        covariance = observation @ self.covariance @ observation.T + np.eye(4) * self.measurement_noise**2
        return float(residual.T @ np.linalg.pinv(covariance) @ residual)
