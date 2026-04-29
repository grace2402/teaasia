// ===== BESS Monitoring: Forecast Demand Engine =====
var USAGE_LS_PREFIX = 'bess_usage_';
var RETENTION_DAYS  = 30;

function getIntervalKey(date) {
  var y  = date.getFullYear();
  var mo = String(date.getMonth() + 1).padStart(2, '0');
  var d  = String(date.getDate()).padStart(2, '0');
  var h  = String(date.getHours()).padStart(2, '0');
  var q  = Math.floor(date.getMinutes() / 15); // 0,1,2,3
  return y + '-' + mo + '-' + d + '_' + h + '_' + q;
}

function loadUsageStore(uuid) {
  try {
    var raw = localStorage.getItem(USAGE_LS_PREFIX + uuid);
    return raw ? JSON.parse(raw) : {};
  } catch(e) { return {}; }
}

function saveUsageStore(uuid, store) {
  var cutoff = Date.now() - RETENTION_DAYS * 24 * 3600 * 1000;
  Object.keys(store).forEach(function(key) {
    var parts = key.split('_');
    var dateStr = parts[0];
    var keyTs = new Date(dateStr).getTime();
    if (keyTs < cutoff) delete store[key];
  });
  try {
    localStorage.setItem(USAGE_LS_PREFIX + uuid, JSON.stringify(store));
  } catch(e) { console.warn('localStorage write failed', e); }
}

function processNormalUsage(uuid, kWh, timestamp) {
  var date        = new Date(timestamp);
  var minute      = date.getMinutes();
  var intervalKey = getIntervalKey(date);

  var store = loadUsageStore(uuid);
  if (!store[intervalKey]) store[intervalKey] = {};
  store[intervalKey][minute] = kWh;
  saveUsageStore(uuid, store);

  var entries   = store[intervalKey];
  var minutes   = Object.keys(entries).map(Number);
  var count     = minutes.length;
  var sumKwh    = 0;
  minutes.forEach(function(m) { sumKwh += entries[m]; });
  var forecast  = count > 0 ? (sumKwh / count) * 60 : 0;

  var fdEl = document.getElementById('fc-demand-' + uuid);
  if (fdEl) {
    fdEl.textContent = Math.round(forecast).toLocaleString();
    updateForecast(uuid);
  }

  var q = Math.floor(minute / 15);
  var labels = ['00-15', '15-30', '30-45', '45-60'];
  console.log('[' + uuid.substring(0,8) + '] 區間 ' + labels[q] +
    ' | 已收 ' + count + ' 筆 | 需量預估 ' + Math.round(forecast) + ' kW');
}
