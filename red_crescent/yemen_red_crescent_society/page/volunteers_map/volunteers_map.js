frappe.pages['volunteers-map'].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'Volunteers Map',
    single_column: true
  });

  // Filters
  page.add_field({
    label: 'Last Updated (Days)',
    fieldtype: 'Int',
    fieldname: 'last_days',
    default: 60,
    change: () => loadMapData()
  });

  page.add_field({
    label: 'Governorate',
    fieldtype: 'Link',
    fieldname: 'governorate',
    options: 'Governorate',
    change: () => loadMapData()
  });

  page.add_field({
    label: 'Gender',
    fieldtype: 'Select',
    fieldname: 'gender',
    options: ['', 'Male', 'Female'],
    change: () => loadMapData()
  });

  page.add_field({
    label: 'Role',
    fieldtype: 'Data',
    fieldname: 'role',
    change: () => loadMapData()
  });

  page.add_menu_item('Export CSV', () => exportToCSV(volData));

  $('<div id="volunteer-map" style="height: 600px; margin-top: 10px;"></div>').appendTo(page.body);

  let map = L.map('volunteer-map').setView([15.3694, 44.1910], 6); // Yemen center
  let markersLayer = L.markerClusterGroup();
  let volData = [];

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap'
  }).addTo(map);

  async function loadMapData() {
    map.eachLayer(layer => { if (layer instanceof L.MarkerClusterGroup) map.removeLayer(layer); });
    markersLayer = L.markerClusterGroup();
    volData = [];

    const args = {
      last_days: page.fields_dict.last_days.get_value(),
      governorate: page.fields_dict.governorate.get_value(),
      gender: page.fields_dict.gender.get_value(),
      role: page.fields_dict.role.get_value()
    };

    const res = await frappe.call({
      method: 'red_crescent.api.volunteer_map.get_volunteers_with_location',
      args
    });

    volData = res.message || [];

    volData.forEach(vol => {
      const icon = getGenderIcon(vol.gender);
      const marker = L.marker([vol.latitude, vol.longitude], { icon });

      const popup = `
        <div style="text-align:center">
          <img src="${vol.profile_image || '/assets/frappe/images/avatar.png'}" width="60" style="border-radius:50%"><br>
          <b>${vol.full_name}</b><br>
          ${vol.role || ''}<br>
          ${vol.home_address || ''}<br>
          <small>${vol.governorate || ''} - ${vol.village || ''}</small>
        </div>
      `;

      marker.bindPopup(popup);
      markersLayer.addLayer(marker);
    });

    map.addLayer(markersLayer);
  }

  function getGenderIcon(gender) {
    const iconUrl = gender === 'Female'
      ? '/files/map_icons/female.png'
      : '/files/map_icons/male.png';

    return L.icon({
      iconUrl,
      iconSize: [32, 32],
      iconAnchor: [16, 32],
      popupAnchor: [0, -32],
    });
  }

  function exportToCSV(data) {
    const csv = [
      ['Name', 'Role', 'Address', 'Latitude', 'Longitude'],
      ...data.map(d => [d.full_name, d.role, d.home_address, d.latitude, d.longitude])
    ].map(e => e.join(',')).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'volunteers_map.csv';
    link.click();
  }

  loadMapData();
};
