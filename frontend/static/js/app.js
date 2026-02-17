/**
 * SIME Application Controller
 * Coordinates API calls, WebSocket connections, and UI updates.
 */

const SIME_APP = (() => {
    const API_BASE = '/api/v1';
    let ws = null;
    let wsReconnectTimer = null;

    async function fetchJSON(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        return response.json();
    }

    // --- WebSocket for real-time alerts ---
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/alerts`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket connected');
            const indicator = document.getElementById('ws-status');
            if (indicator) {
                indicator.textContent = 'EN VIVO';
                indicator.classList.add('ws-connected');
            }
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleWSMessage(msg);
            } catch (err) {
                console.error('WebSocket message parse error:', err);
            }
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected, reconnecting in 5s...');
            const indicator = document.getElementById('ws-status');
            if (indicator) {
                indicator.textContent = 'DESCONECTADO';
                indicator.classList.remove('ws-connected');
            }
            wsReconnectTimer = setTimeout(connectWebSocket, 5000);
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };

        // Keep-alive ping every 30s
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 30000);
    }

    function handleWSMessage(msg) {
        switch (msg.type) {
            case 'alert':
                showRealtimeAlert(msg.data);
                break;
            case 'flood_update':
                updateFloodZonesFromWS(msg.data);
                break;
            case 'connected':
                console.log('SIME real-time:', msg.message);
                break;
        }
    }

    function showRealtimeAlert(alertData) {
        // Show a toast notification for real-time alerts
        const toast = document.createElement('div');
        toast.className = `toast-alert toast-${alertData.risk_level}`;
        toast.innerHTML = `
            <strong>${alertData.name}</strong><br/>
            <span>${alertData.message}</span>
        `;
        document.body.appendChild(toast);

        // Auto-remove after 10 seconds
        setTimeout(() => toast.remove(), 10000);

        // Also refresh the alerts sidebar
        loadAlerts();
    }

    function updateFloodZonesFromWS(zonesData) {
        SIME_MAP.clearFloodZones();
        zonesData.forEach(zone => SIME_MAP.addFloodZone(zone));

        const now = new Date();
        document.getElementById('last-update').textContent =
            `Ultima actualizacion: ${now.toLocaleTimeString('es-CO')}`;
    }

    // --- Flood zones ---
    async function loadFloodZones() {
        try {
            const zones = await fetchJSON(`${API_BASE}/flood/current`);
            SIME_MAP.clearFloodZones();
            zones.forEach(zone => SIME_MAP.addFloodZone(zone));
        } catch (err) {
            console.error('Failed to load flood zones:', err);
        }
    }

    // --- Alerts ---
    async function loadAlerts() {
        const container = document.getElementById('alerts-list');
        try {
            const alerts = await fetchJSON(`${API_BASE}/alerts`);
            if (alerts.length === 0) {
                container.innerHTML = '<p class="no-alerts">Sin alertas activas</p>';
                return;
            }
            container.innerHTML = alerts.map(alert => {
                const cssClass = {
                    high: 'alert-high',
                    very_high: 'alert-very-high',
                    extreme: 'alert-extreme',
                }[alert.risk_level] || 'alert-high';

                return `
                    <div class="alert-card ${cssClass}"
                         onclick="SIME_APP.panToAlert(${alert.coordinates.lat}, ${alert.coordinates.lon})">
                        <div class="alert-title">${alert.title}</div>
                        <div class="alert-detail">${alert.description}</div>
                    </div>
                `;
            }).join('');
        } catch (err) {
            container.innerHTML = '<p class="loading">Error cargando alertas</p>';
            console.error('Failed to load alerts:', err);
        }
    }

    // --- Stations ---
    async function loadStations() {
        const container = document.getElementById('stations-list');
        try {
            const stations = await fetchJSON(`${API_BASE}/stations`);
            SIME_MAP.clearStations();
            stations.forEach(station => SIME_MAP.addStation(station));

            container.innerHTML = stations.map(st => `
                <div class="station-item"
                     onclick="SIME_APP.panToStation(${st.coordinates.lat}, ${st.coordinates.lon})">
                    <span class="station-name">${st.name}</span>
                    <span class="station-river">${st.river_name || ''}</span>
                </div>
            `).join('');
        } catch (err) {
            container.innerHTML = '<p class="loading">Error cargando estaciones</p>';
            console.error('Failed to load stations:', err);
        }
    }

    // --- Safe route ---
    async function calculateRoute() {
        const originInput = document.getElementById('route-origin').value.trim();
        const destInput = document.getElementById('route-dest').value.trim();
        const infoDiv = document.getElementById('route-info');

        if (!originInput || !destInput) {
            infoDiv.textContent = 'Ingrese origen y destino';
            infoDiv.classList.remove('hidden');
            return;
        }

        const [originLat, originLon] = originInput.split(',').map(s => parseFloat(s.trim()));
        const [destLat, destLon] = destInput.split(',').map(s => parseFloat(s.trim()));

        if ([originLat, originLon, destLat, destLon].some(isNaN)) {
            infoDiv.textContent = 'Formato invalido. Use: lat, lon';
            infoDiv.classList.remove('hidden');
            return;
        }

        infoDiv.textContent = 'Calculando ruta segura...';
        infoDiv.classList.remove('hidden');

        try {
            const url = `${API_BASE}/route/safe?origin_lat=${originLat}&origin_lon=${originLon}&dest_lat=${destLat}&dest_lon=${destLon}`;
            const route = await fetchJSON(url);
            SIME_MAP.drawRoute(route);

            const riskLabel = {
                low: 'Bajo',
                moderate: 'Moderado',
                high: 'Alto',
                very_high: 'Muy Alto',
                extreme: 'Extremo',
            };

            infoDiv.innerHTML = `
                <strong>Ruta calculada</strong><br/>
                Distancia: ${route.total_distance_km} km<br/>
                Tiempo est.: ${route.estimated_time_min} min<br/>
                Riesgo max: ${riskLabel[route.max_risk_level] || route.max_risk_level}<br/>
                ${route.avoids_flood_zones
                    ? '<span style="color:#4caf50;">Evita zonas de inundacion</span>'
                    : '<span style="color:#f44336;">PASA por zonas de riesgo</span>'}
            `;
        } catch (err) {
            infoDiv.textContent = 'Error calculando ruta';
            console.error('Route error:', err);
        }
    }

    // --- Navigation helpers ---
    function panToAlert(lat, lon) {
        SIME_MAP.panTo(lat, lon, 10);
    }

    function panToStation(lat, lon) {
        SIME_MAP.panTo(lat, lon, 12);
    }

    // --- Refresh all data ---
    async function refreshAll() {
        const updateLabel = document.getElementById('last-update');
        updateLabel.textContent = 'Actualizando...';

        await Promise.all([
            loadFloodZones(),
            loadAlerts(),
            loadStations(),
        ]);

        const now = new Date();
        updateLabel.textContent = `Ultima actualizacion: ${now.toLocaleTimeString('es-CO')}`;
    }

    // --- Init ---
    function init() {
        SIME_MAP.init();

        // Wire up buttons
        document.getElementById('btn-refresh').addEventListener('click', refreshAll);
        document.getElementById('btn-route').addEventListener('click', calculateRoute);

        // Initial data load
        refreshAll();

        // Connect WebSocket for real-time updates
        connectWebSocket();

        // Fallback: auto-refresh every 15 minutes if WebSocket fails
        setInterval(refreshAll, 15 * 60 * 1000);
    }

    // Start when DOM is ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        panToAlert,
        panToStation,
        refreshAll,
    };
})();
