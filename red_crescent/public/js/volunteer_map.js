frappe.ready(() => {
  // Create map container dynamically
  const container = document.createElement("div");
  container.id = "volunteer-map";
  container.style = "height: 600px; border: 1px solid #ccc; margin-top: 20px;";
  document.querySelector(".web-page-content")?.appendChild(container);

  // Initialize map
  const map = L.map("volunteer-map").setView([15.3694, 44.1910], 6); // Yemen center

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  // Load data
  fetch("/api/method/red_crescent.api.get_volunteers_map_data")
    .then(res => res.json())
    .then(res => {
      const volunteers = res.message || [];

      volunteers.forEach(vol => {
        if (vol.latitude && vol.longitude) {
          const marker = L.marker([vol.latitude, vol.longitude]).addTo(map);
          marker.bindPopup(`
            <b>${vol.full_name || "Unknown"}</b><br>
            ${vol.status || ""}<br>
            ${vol.governorate || ""} - ${vol.district || ""}
          `);
        }
      });
    })
    .catch(err => {
      console.error("Error loading map data:", err);
    });
});
