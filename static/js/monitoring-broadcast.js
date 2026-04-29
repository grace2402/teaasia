// ===== BESS Monitoring: BroadcastChannel - share site states with map page =====
var bc = new BroadcastChannel('bess_sites');

function getSiteState(primaryUuid) {
  var pctEl = document.getElementById('fc-pct-' + primaryUuid);
  var pct = pctEl ? parseFloat(pctEl.textContent) : NaN;
  var state = 'normal';
  if (pct >= 100) state = 'alert';
  else if (pct >= 85) state = 'warn';
  return state;
}

function broadcastSiteStates() {
  var states = {};
  SITES.forEach(function(s) {
    var uuids = Array.isArray(s.uuid) ? s.uuid : [s.uuid];
    var primaryUuid = uuids[0];
    states[primaryUuid] = {
      name: s.name,
      location: s.location || null,
      state: getSiteState(primaryUuid)
    };
  });
  bc.postMessage({ type: 'site_states', data: states });
}
