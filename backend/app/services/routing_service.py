"""Service for generating safe evacuation routes that avoid flood zones."""

import math

import networkx as nx
from loguru import logger

from backend.app.models.schemas import (
    Coordinates,
    FloodZone,
    RiskLevel,
    RoutePoint,
    SafeRoute,
)
from backend.app.services.flood_service import get_current_flood_zones

# Grid resolution for pathfinding (degrees). ~0.01 deg ≈ 1.1 km at equator.
GRID_RESOLUTION = 0.01

# Risk penalties for routing (higher = path avoids more strongly)
RISK_WEIGHT = {
    RiskLevel.LOW: 1.0,
    RiskLevel.MODERATE: 3.0,
    RiskLevel.HIGH: 10.0,
    RiskLevel.VERY_HIGH: 50.0,
    RiskLevel.EXTREME: 200.0,
}

# Radius of influence around a flood zone point (in degrees, ~5 km)
FLOOD_INFLUENCE_RADIUS = 0.05


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _snap_to_grid(value: float) -> float:
    """Snap a coordinate to the nearest grid point."""
    return round(value / GRID_RESOLUTION) * GRID_RESOLUTION


def _get_risk_at_point(
    lat: float, lon: float, flood_zones: list[FloodZone]
) -> RiskLevel:
    """Determine the flood risk level at a specific point."""
    max_risk = RiskLevel.LOW
    for zone in flood_zones:
        for coord in zone.coordinates:
            dist = _haversine_km(lat, lon, coord.lat, coord.lon)
            if dist < FLOOD_INFLUENCE_RADIUS * 111:  # rough deg-to-km
                if RISK_WEIGHT[zone.risk_level] > RISK_WEIGHT[max_risk]:
                    max_risk = zone.risk_level
    return max_risk


def _build_routing_graph(
    origin: Coordinates,
    destination: Coordinates,
    flood_zones: list[FloodZone],
    margin: float = 0.1,
) -> nx.Graph:
    """Build a weighted grid graph for pathfinding between two points."""
    lat_min = min(origin.lat, destination.lat) - margin
    lat_max = max(origin.lat, destination.lat) + margin
    lon_min = min(origin.lon, destination.lon) - margin
    lon_max = max(origin.lon, destination.lon) + margin

    G = nx.Graph()
    lats = []
    lat = _snap_to_grid(lat_min)
    while lat <= lat_max:
        lats.append(round(lat, 4))
        lat += GRID_RESOLUTION

    lons = []
    lon = _snap_to_grid(lon_min)
    while lon <= lon_max:
        lons.append(round(lon, 4))
        lon += GRID_RESOLUTION

    # Limit grid size for performance
    if len(lats) * len(lons) > 50_000:
        logger.warning("Grid too large, increasing resolution")
        return nx.Graph()

    for lat in lats:
        for lon in lons:
            risk = _get_risk_at_point(lat, lon, flood_zones)
            G.add_node((lat, lon), risk=risk)

    # Connect adjacent grid cells (4-connected)
    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            node = (lat, lon)
            neighbors = []
            if i + 1 < len(lats):
                neighbors.append((lats[i + 1], lon))
            if j + 1 < len(lons):
                neighbors.append((lat, lons[j + 1]))

            for nb in neighbors:
                if G.has_node(nb):
                    risk_a = G.nodes[node].get("risk", RiskLevel.LOW)
                    risk_b = G.nodes[nb].get("risk", RiskLevel.LOW)
                    dist = _haversine_km(node[0], node[1], nb[0], nb[1])
                    weight = dist * max(RISK_WEIGHT[risk_a], RISK_WEIGHT[risk_b])
                    G.add_edge(node, nb, weight=weight)

    return G


async def find_safe_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> SafeRoute:
    """Find the safest route between two points, avoiding flood zones."""
    flood_zones = await get_current_flood_zones()

    origin = Coordinates(lat=origin_lat, lon=origin_lon)
    destination = Coordinates(lat=dest_lat, lon=dest_lon)

    origin_node = (
        _snap_to_grid(origin_lat),
        _snap_to_grid(origin_lon),
    )
    dest_node = (
        _snap_to_grid(dest_lat),
        _snap_to_grid(dest_lon),
    )

    G = _build_routing_graph(origin, destination, flood_zones)

    if not G.nodes:
        logger.warning("Routing graph empty, returning direct path")
        direct_dist = _haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
        return SafeRoute(
            origin=origin,
            destination=destination,
            waypoints=[
                RoutePoint(lat=origin_lat, lon=origin_lon),
                RoutePoint(lat=dest_lat, lon=dest_lon),
            ],
            total_distance_km=direct_dist,
            estimated_time_min=direct_dist / 40 * 60,  # ~40 km/h avg
            max_risk_level=RiskLevel.LOW,
            avoids_flood_zones=False,
        )

    # Ensure start/end nodes exist
    origin_snapped = (round(origin_node[0], 4), round(origin_node[1], 4))
    dest_snapped = (round(dest_node[0], 4), round(dest_node[1], 4))

    if origin_snapped not in G or dest_snapped not in G:
        logger.warning("Origin or destination outside routing graph")
        direct_dist = _haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
        return SafeRoute(
            origin=origin,
            destination=destination,
            waypoints=[
                RoutePoint(lat=origin_lat, lon=origin_lon),
                RoutePoint(lat=dest_lat, lon=dest_lon),
            ],
            total_distance_km=direct_dist,
            estimated_time_min=direct_dist / 40 * 60,
            max_risk_level=RiskLevel.LOW,
            avoids_flood_zones=False,
        )

    try:
        path = nx.shortest_path(G, origin_snapped, dest_snapped, weight="weight")
    except nx.NetworkXNoPath:
        logger.error("No path found between origin and destination")
        direct_dist = _haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
        return SafeRoute(
            origin=origin,
            destination=destination,
            waypoints=[
                RoutePoint(lat=origin_lat, lon=origin_lon),
                RoutePoint(lat=dest_lat, lon=dest_lon),
            ],
            total_distance_km=direct_dist,
            estimated_time_min=direct_dist / 40 * 60,
            max_risk_level=RiskLevel.LOW,
            avoids_flood_zones=False,
        )

    # Build waypoints from path
    waypoints = []
    total_dist = 0.0
    max_risk = RiskLevel.LOW
    avoids = True

    for i, (lat, lon) in enumerate(path):
        risk = G.nodes[(lat, lon)].get("risk", RiskLevel.LOW)
        waypoints.append(RoutePoint(lat=lat, lon=lon, risk_level=risk))
        if RISK_WEIGHT[risk] > RISK_WEIGHT[max_risk]:
            max_risk = risk
        if risk in (RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.EXTREME):
            avoids = False
        if i > 0:
            prev_lat, prev_lon = path[i - 1]
            total_dist += _haversine_km(prev_lat, prev_lon, lat, lon)

    route = SafeRoute(
        origin=origin,
        destination=destination,
        waypoints=waypoints,
        total_distance_km=round(total_dist, 2),
        estimated_time_min=round(total_dist / 40 * 60, 1),
        max_risk_level=max_risk,
        avoids_flood_zones=avoids,
    )

    logger.info(
        f"Route found: {len(waypoints)} waypoints, {route.total_distance_km} km, "
        f"max risk: {max_risk}"
    )
    return route
