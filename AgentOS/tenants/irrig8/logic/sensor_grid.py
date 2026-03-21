"""
sensor_grid.py — Irrig8 Virtual Sensor Grid

Converts sparse point-sensor data from the RQE into a continuous, 1m-resolution
virtual grid using spatial interpolation (or simple nearest-neighbor).
"""

import math
from typing import Any
from AgentOS.kernel.rqe import RQE

class VirtualGrid:
    """
    Manages a 1m resolution grid for a given field boundary.
    """

    def __init__(self, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> None:
        self.bounds = (lat_min, lat_max, lon_min, lon_max)
        # Simple estimation: 1m is approx 0.00001 degrees
        self.resolution = 0.00001
        self.rqe = RQE()

    async def interpolate_layer(self, layer_name: str, tenant_id: str) -> list[list[float]]:
        """
        Produce a 2D array of interpolated values for the requested layer.
        """
        lat_steps = int((self.bounds[1] - self.bounds[0]) / self.resolution)
        lon_steps = int((self.bounds[3] - self.bounds[2]) / self.resolution)

        grid = []
        for i in range(lat_steps):
            row = []
            for j in range(lon_steps):
                lat = self.bounds[0] + i * self.resolution
                lon = self.bounds[2] + j * self.resolution
                # Query RQE for nearest point
                res = await self.rqe.query(lat, lon, [layer_name], tenant_id)
                row.append(res.data.get(layer_name, 0.0))
            grid.append(row)
        return grid

if __name__ == "__main__":
    import asyncio
    grid = VirtualGrid(-37.8136, -37.8135, 144.9631, 144.9632)
    asyncio.run(grid.interpolate_layer("ndvi", "subsidiary_beta"))
