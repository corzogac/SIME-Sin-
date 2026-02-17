"""Background task that periodically monitors flood conditions and
broadcasts alerts via WebSocket when risk levels change."""

import asyncio

from loguru import logger

from backend.app.models.schemas import RiskLevel

# Track previously known risk levels to detect changes
_previous_risks: dict[str, RiskLevel] = {}


async def monitor_loop(interval_seconds: int = 300):
    """Run the alert monitoring loop.

    Checks flood conditions every `interval_seconds` (default 5 minutes)
    and broadcasts WebSocket alerts when new high-risk zones are detected
    or when risk levels escalate.
    """
    from backend.app.api.websocket import broadcast_alert, broadcast_flood_update
    from backend.app.services.flood_service import get_active_alerts, get_current_flood_zones

    logger.info(f"Alert monitor started (interval: {interval_seconds}s)")

    while True:
        try:
            zones = await get_current_flood_zones()

            # Broadcast full zone update
            zones_data = [
                {
                    "zone_id": z.zone_id,
                    "name": z.name,
                    "risk_level": z.risk_level.value,
                    "coordinates": [{"lat": c.lat, "lon": c.lon} for c in z.coordinates],
                    "river_discharge_m3s": z.river_discharge_m3s,
                    "estimated_depth_m": z.estimated_depth_m,
                }
                for z in zones
            ]
            await broadcast_flood_update(zones_data)

            # Check for new or escalated alerts
            for zone in zones:
                prev_risk = _previous_risks.get(zone.zone_id, RiskLevel.LOW)
                risk_order = [
                    RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH,
                    RiskLevel.VERY_HIGH, RiskLevel.EXTREME,
                ]

                current_idx = risk_order.index(zone.risk_level)
                prev_idx = risk_order.index(prev_risk)

                # Alert if risk escalated to HIGH or above
                if current_idx >= 2 and current_idx > prev_idx:
                    alert_data = {
                        "zone_id": zone.zone_id,
                        "name": zone.name,
                        "risk_level": zone.risk_level.value,
                        "river_discharge_m3s": zone.river_discharge_m3s,
                        "message": (
                            f"Riesgo de inundacion escalado a "
                            f"{zone.risk_level.value.upper()} en {zone.name}"
                        ),
                    }
                    await broadcast_alert(alert_data)
                    logger.warning(
                        f"ALERT: {zone.name} escalated to {zone.risk_level.value}"
                    )

                _previous_risks[zone.zone_id] = zone.risk_level

        except Exception as e:
            logger.error(f"Alert monitor error: {e}")

        await asyncio.sleep(interval_seconds)
