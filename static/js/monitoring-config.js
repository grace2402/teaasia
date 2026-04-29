// ===== BESS Monitoring: Site Configuration =====
var SITES = [
  { uuid: '4042479a-6648-4299-bdbb-cd0e55c08d30',                                             name: '國泰八德', location: [24.9397, 121.3006] },
  { uuid: ['c3db1581-74dc-4c07-8ee5-580c77b3884d', 'fecaae3e-0d4a-4adb-a79c-59f05a0d1cf9'],   name: '國泰烏日', location: [24.1249, 120.6452] },
  { uuid: ['66218d11-ab23-4a4b-ae75-2b47e220f27c', '07d00651-3c45-4129-a539-43099e95d168'],   name: '中櫃台中', location: [24.1469, 120.6839] },
  { uuid: ['1ca897dc-bdc0-4f03-ba39-753d9b183a9e', '1d4f6d8e-259a-4a2f-8b37-5b2d31c6cfaf', '9da81f6e-9439-464e-ac16-cda42cdfb552'],   name: '順益中壢', location: [24.96827116905552, 121.23746621534256] }
];

// SITE_MAP: each uuid → primaryUuid (first uuid of the site)
var SITE_MAP = {};
SITES.forEach(function(s) {
  var uuids = Array.isArray(s.uuid) ? s.uuid : [s.uuid];
  var primaryUuid = uuids[0];
  uuids.forEach(function(u) { SITE_MAP[u] = primaryUuid; });
});
