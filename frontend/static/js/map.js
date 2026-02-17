/**
 * SIME Map Module
 * Handles Leaflet map initialization and flood zone visualization.
 */

const SIME_MAP = (() => {
    // Colombia center coordinates
    const COLOMBIA_CENTER = [4.5, -74.0];
    const DEFAULT_ZOOM = 6;

    // Risk level colors
    const RISK_COLORS = {
        low: '#4caf50',
        moderate: '#ffeb3b',
        high: '#ff9800',
        very_high: '#f44336',
        extreme: '#d32f2f',
    };

    // Risk level radius (meters) for circle markers
    const RISK_RADIUS = {
        low: 15000,
        moderate: 25000,
        high: 35000,
        very_high: 45000,
        extreme: 55000,
    };

    let map = null;
    let floodLayer = null;
    let stationLayer = null;
    let routeLayer = null;

    function init() {
        map = L.map('map', {
            center: COLOMBIA_CENTER,
            zoom: DEFAULT_ZOOM,
            zoomControl: true,
        });

        // Dark tile layer
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 18,
        }).addTo(map);

        // Initialize layer groups
        floodLayer = L.layerGroup().addTo(map);
        stationLayer = L.layerGroup().addTo(map);
        routeLayer = L.layerGroup().addTo(map);

        // Layer control
        L.control.layers(null, {
            'Zonas de inundacion': floodLayer,
            'Estaciones': stationLayer,
            'Ruta segura': routeLayer,
        }).addTo(map);

        return map;
    }

    function clearFloodZones() {
        if (floodLayer) floodLayer.clearLayers();
    }

    function addFloodZone(zone) {
        const color = RISK_COLORS[zone.risk_level] || RISK_COLORS.low;
        const radius = RISK_RADIUS[zone.risk_level] || RISK_RADIUS.low;

        zone.coordinates.forEach(coord => {
            const circle = L.circle([coord.lat, coord.lon], {
                radius: radius,
                color: color,
                fillColor: color,
                fillOpacity: 0.25,
                weight: 2,
            });

            circle.bindPopup(`
                <div style="color:#333;">
                    <strong>${zone.name}</strong><br/>
                    Riesgo: <span style="color:${color};font-weight:bold;">${zone.risk_level.toUpperCase()}</span><br/>
                    ${zone.river_discharge_m3s ? `Caudal: ${zone.river_discharge_m3s.toFixed(1)} m&sup3;/s` : ''}
                </div>
            `);

            floodLayer.addLayer(circle);
        });
    }

    function clearStations() {
        if (stationLayer) stationLayer.clearLayers();
    }

    function addStation(station) {
        const marker = L.circleMarker([station.coordinates.lat, station.coordinates.lon], {
            radius: 6,
            color: '#4fc3f7',
            fillColor: '#4fc3f7',
            fillOpacity: 0.8,
            weight: 1,
        });

        marker.bindPopup(`
            <div style="color:#333;">
                <strong>${station.name}</strong><br/>
                Departamento: ${station.department}<br/>
                Rio: ${station.river_name || 'N/A'}<br/>
                Tipo: ${station.station_type}
            </div>
        `);

        stationLayer.addLayer(marker);
    }

    function clearRoute() {
        if (routeLayer) routeLayer.clearLayers();
    }

    function drawRoute(route) {
        clearRoute();

        if (!route.waypoints || route.waypoints.length === 0) return;

        // Draw the path line
        const latlngs = route.waypoints.map(wp => [wp.lat, wp.lon]);
        const polyline = L.polyline(latlngs, {
            color: '#00e5ff',
            weight: 4,
            opacity: 0.8,
            dashArray: '10, 10',
        });
        routeLayer.addLayer(polyline);

        // Origin marker
        const origin = route.waypoints[0];
        L.marker([origin.lat, origin.lon], {
            icon: L.divIcon({
                className: '',
                html: '<div style="background:#4caf50;width:14px;height:14px;border-radius:50%;border:2px solid #fff;"></div>',
                iconSize: [14, 14],
            }),
        }).bindPopup('Origen').addTo(routeLayer);

        // Destination marker
        const dest = route.waypoints[route.waypoints.length - 1];
        L.marker([dest.lat, dest.lon], {
            icon: L.divIcon({
                className: '',
                html: '<div style="background:#f44336;width:14px;height:14px;border-radius:50%;border:2px solid #fff;"></div>',
                iconSize: [14, 14],
            }),
        }).bindPopup('Destino').addTo(routeLayer);

        // Fit map to route
        map.fitBounds(polyline.getBounds(), { padding: [50, 50] });
    }

    function panTo(lat, lon, zoom) {
        if (map) map.setView([lat, lon], zoom || 10);
    }

    return {
        init,
        clearFloodZones,
        addFloodZone,
        clearStations,
        addStation,
        clearRoute,
        drawRoute,
        panTo,
    };
})();
