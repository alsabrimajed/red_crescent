 frappe.pages['vehicle-summary-map'] = {
    on_page_load(wrapper) {
        let page = frappe.ui.make_app_page({
            parent: wrapper,
            title: 'Vehicle Summary Map',
            single_column: true
        });

        $(wrapper).html(`<div id="vehicle-map" style="height: 600px;"></div>`);

        // Load Leaflet
        frappe.require("https://unpkg.com/leaflet/dist/leaflet.js", () => {
            $('<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css">').appendTo("head");

            // Show test map
            const map = L.map('vehicle-map').setView([15.5, 45], 6);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);

            // Test Marker
            L.marker([15.5, 45])
                .addTo(map)
                .bindPopup("🚗 Test Vehicle")
                .openPopup();
        });
    }
};
