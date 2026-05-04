// ===== BESS Monitoring: Site Configuration (Dynamic) =====
// Reads window.MONITORING_SITES injected by monitoring_system.html template
// Falls back to hardcoded SITES if no injection (for backward compatibility)

(function () {
  'use strict';

  var fallback = [
    { uuid: '4042479a-6648-4299-bdbb-cd0e55c08d30', name: '國泰八德' },
    { uuid: ['c3db1581-74dc-4c07-8ee5-580c77b3884d', 'fecaae3e-0d4a-4adb-a79c-59f05a0d1cf9'], name: '國泰烏日' },
    { uuid: ['66218d11-ab23-4a4b-ae75-2b47e220f27c', '07d00651-3c45-4129-a539-43099e95d168'], name: '中櫃台中' },
    { uuid: ['1ca897dc-bdc0-4f03-ba39-753d9b183a9e', '1d4f6d8e-259a-4a2f-8b37-5b2d31c6cfaf', '9da81f6e-9439-464e-ac16-cda42cdfb552'], name: '順益中壢' }
  ];

  // Build SITES from backend data or fallback
  var raw = window.MONITORING_SITES || [];

  if (Array.isArray(raw) && raw.length > 0) {
    // Backend data: each item has pcs_uuid (array), name, etc.
    // Group by backend item index — a site can have multiple UUIDs
    var uuidMap = {};
    raw.forEach(function (item, idx) {
      var uuid = item.pcs_uuid;
      if (!uuid) return;
      var uuids = Array.isArray(uuid) ? uuid : [uuid];

      // Use index as key so all UUIDs for one site stay together
      if (!uuidMap[idx]) {
        uuidMap[idx] = { primaryUuid: uuids[0], name: item.name || '未命名案場', allUuids: [] };
      }
      uuidMap[idx].allUuids.push.apply(uuidMap[idx].allUuids, uuids);
    });

    // Build SITES array — one entry per backend item
    var seen = {};
    window.SITES = [];
    Object.keys(uuidMap).forEach(function (idx) {
      var entry = uuidMap[idx];
      if (seen[entry.primaryUuid]) return;
      seen[entry.primaryUuid] = true;
      // Deduplicate within the site's own UUID list
      var uniqueUuids = [];
      entry.allUuids.forEach(function (uu) {
        if (uniqueUuids.indexOf(uu) === -1) uniqueUuids.push(uu);
      });
      window.SITES.push({ uuid: uniqueUuids, name: entry.name });
    });

    console.log('[Config] Loaded', window.SITES.length, 'sites from backend');
  } else {
    // Fallback to hardcoded
    window.SITES = fallback;
    console.log('[Config] Using hardcoded SITES (no backend data)');
  }

  // Build SITE_MAP: each uuid → primaryUuid
  window.SITE_MAP = {};
  window.SITES.forEach(function (s) {
    var uuids = Array.isArray(s.uuid) ? s.uuid : [s.uuid];
    var primaryUuid = uuids[0];
    uuids.forEach(function (u) { window.SITE_MAP[u] = primaryUuid; });
  });

  console.log('[Config] SITE_MAP keys:', Object.keys(window.SITE_MAP).length);
})();
