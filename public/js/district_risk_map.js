frappe.ready(() => {
  const MAPBOX_TOKEN = 'pk.eyJ1IjoiYWxzYWJyaW1hamVkIiwiYSI6ImNtZWtoa3k0NjA1ZGkyaXF2amEzdHFlZWgifQ.QjUIQRz5P1aegoxnDRCCNA';

  // Load Mapbox
  const script = document.createElement('script');
  script.src = 'https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js';
  script.onload = () => initMap();
  document.head.appendChild(script);

  const link = document.createElement('link');
  link.href = 'https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css';
  link.rel = 'stylesheet';
  document.head.appendChild(link);

  function initMap() {
    mapboxgl.accessToken = MAPBOX_TOKEN;

    const map = new mapboxgl.Map({
      container: 'district-risk-map',
      style: 'mapbox://styles/mapbox/light-v11',
      center: [44.0, 15.5], // Yemen center
      zoom: 6
    });

    // Get risk data from backend
    frappe.call({
      method: 'red_crescent.api.get_district_risks',
      callback: function (res) {
        if (!res.message) return;

        res.message.forEach((district) => {
          const { latitude, longitude, district: name, risk_type, risk_level } = district;

          if (!latitude || !longitude) return;

          const marker = new mapboxgl.Marker({ color: getColor(risk_level) })
            .setLngLat([parseFloat(longitude), parseFloat(latitude)])
            .setPopup(new mapboxgl.Popup().setHTML(`
              <strong>${name}</strong><br>
              <b>Risk:</b> ${risk_type}<br>
              <b>Level:</b> ${risk_level}
            `))
            .addTo(map);
        });
      }
    });
  }

  // Color based on risk level
  function getColor(level) {
    const colors = {
      1: '#00ff00', // Low
      2: '#aaff00',
      3: '#ffaa00',
      4: '#ff5500',
      5: '#ff0000'  // High
    };
    return colors[level] || '#999';
  }
});
