frappe.provide('frappe.pages');

frappe.pages['vehicle-summary-map'] = {
  _route: 'vehicle-summary-map',
  on_page_load(wrapper) {
    const getWrapper = () =>
      cur_page?.page?.wrapper ||
      document.querySelector('.page-container') ||
      document.querySelector('.layout-main-section');

    wrapper = wrapper || getWrapper();

    if (!wrapper) {
      console.warn("[vehicle-summary-map] wrapper not ready, retrying...");
      return setTimeout(() => frappe.pages['vehicle-summary-map'].on_page_load(), 100);
    }

    console.log("[vehicle-summary-map] wrapper ready:", wrapper);

    // Clear wrapper and add map container
    wrapper.innerHTML = '<div id="vehicle-map" style="height:600px;"></div>';

    // Load Leaflet if needed
    const ensureLeaflet = (cb) => {
      if (window.L) return cb();
      frappe.require('https://unpkg.com/leaflet/dist/leaflet.js', cb);
      $('<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">').appendTo('head');
    };

    ensureLeaflet(() => {
      const map = L.map('vehicle-map').setView([15.5, 45], 6);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);

      // 🔎 Debug: test the API
      frappe.call('get_grouped_vehicle_locations').then(res => {
        const data = res.message || [];
        console.groupCollapsed("🚚 Vehicle API Debug");
        console.log("Raw response:", res);
        console.table(data);
        console.groupEnd();

        if (!data.length) {
          console.warn("⚠️ API returned no rows. Map will be empty.");
          return;
        }

        const bounds = [];

        data.forEach(loc => {
          const lat = Number(loc.latitude), lng = Number(loc.longitude);
          if (!isFinite(lat) || !isFinite(lng)) return;

          const count = Number(loc.vehicle_count || 0);
          const label = loc.location || 'Unknown';

          const icon = L.divIcon({
            className: 'veh-count-icon',
            html: `<div class="veh-badge">${count}</div>`,
            iconSize: [28, 28], iconAnchor: [14, 14]
          });

          L.marker([lat, lng], { icon })
            .addTo(map)
            .bindPopup(`<b>${label}</b><br/>Vehicles: ${count}`);

          bounds.push([lat, lng]);
        });

        if (bounds.length) map.fitBounds(bounds, { padding: [40, 40] });
      });

      // Badge CSS
      const style = document.createElement('style');
      style.textContent = `
        .veh-count-icon .veh-badge{
          width:28px;height:28px;border-radius:50%;
          display:flex;align-items:center;justify-content:center;
          font:600 12px/1 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
          background:#fff;border:2px solid #333;box-shadow:0 2px 6px rgba(0,0,0,.2);
        }`;
      document.head.appendChild(style);
    });
  }
};
