// ===== BESS Monitoring: Forecast UI Update =====
function updateForecast(uuid) {
  var dEl = document.getElementById('fc-demand-'   + uuid);
  var cEl = document.getElementById('fc-contract-' + uuid);
  if (!dEl || !cEl) return;

  var d = parseFloat(dEl.textContent.replace(/,/g, ''));
  var c = parseFloat(cEl.textContent.replace(/,/g, ''));
  if (isNaN(d) || isNaN(c) || c <= 0) return;

  var pct    = Math.min((d / c) * 100, 100);
  var pctRaw = (d / c * 100).toFixed(1);
  var state  = pct >= 100 ? 'alert' : pct >= 85 ? 'warn' : '';

  var fillEl   = document.getElementById('fc-fill-'   + uuid);
  var lineEl   = document.getElementById('fc-line-'   + uuid);
  var pctEl    = document.getElementById('fc-pct-'    + uuid);
  var statusEl = document.getElementById('fc-status-' + uuid);

  if (fillEl)   { fillEl.style.width = pct + '%'; fillEl.className = 'forecast-fill' + (state ? ' ' + state : ''); }
  if (lineEl)   { lineEl.style.left  = Math.min((c / Math.max(d, c)) * 100, 100) + '%'; }
  if (pctEl)    { pctEl.textContent  = pctRaw + '%'; pctEl.className = 'f-pct' + (state ? ' ' + state : ''); }
  if (statusEl) {
    if (state === 'alert')     { statusEl.textContent = '超標'; statusEl.className = 'forecast-status alert'; }
    else if (state === 'warn') { statusEl.textContent = '注意'; statusEl.className = 'forecast-status warn'; }
    else                       { statusEl.textContent = '正常'; statusEl.className = 'forecast-status'; }
  }
}
