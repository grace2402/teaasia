// ===== BESS Monitoring: Update Site Data from MQTT Message =====
function updateSite(uuid, items) {
  items.forEach(function(item) {
    var scope = item.scope;
    var val   = parseFloat(item.value);

    if (item.generatedTime) {
      var tEl = document.getElementById('time-' + uuid);
      if (tEl) tEl.textContent = new Date(item.generatedTime).toLocaleTimeString('zh-TW');
    }

    if (scope === 'storedElectricityPercent') {
      var pct   = Math.min(Math.max(val, 0), 100);
      var fill  = document.getElementById('soc-fill-'  + uuid);
      var label = document.getElementById('soc-label-' + uuid);
      if (fill)  fill.style.width = pct + '%';
      if (label) {
        label.textContent = 'SOC ' + val + '%';
        label.className = 'soc-label' + (pct < 30 ? ' dark' : '');
        flash(label);
      }
      return;
    }

    if (scope === 'realPower') {
      var rpEl    = document.getElementById('rp-'    + uuid);
      var badgeEl = document.getElementById('badge-' + uuid);
      if (!rpEl) return;
      rpEl.textContent = Math.abs(val).toLocaleString();
      flash(rpEl);
      if (val > 0) {
        rpEl.className = 'p-value discharging';
        if (badgeEl) { badgeEl.textContent = '放電'; badgeEl.className = 'badge dis'; badgeEl.style.display = ''; }
      } else if (val < 0) {
        rpEl.className = 'p-value charging';
        if (badgeEl) { badgeEl.textContent = '充電'; badgeEl.className = 'badge chg'; badgeEl.style.display = ''; }
      } else {
        rpEl.className = 'p-value idle';
        if (badgeEl) badgeEl.style.display = 'none';
      }
      return;
    }

    if (scope === 'soh') {
      console.log('[Update] SOH received for', uuid, ':', val);
      setVal('soh-' + uuid, val);
      return;
    }
    if (scope === 'cellHighestTemperature')     { setVal('temp-' + uuid, val); return; }

    if (scope === 'emsSetPoint') {
      var emsEl = document.getElementById('ems-' + uuid);
      if (emsEl) { emsEl.textContent = val.toLocaleString(); flash(emsEl); }
      return;
    }

    if (scope === 'cellHighestVoltage' || scope === 'cellLowestVoltage') {
      var prefix = scope === 'cellHighestVoltage' ? 'cellmax' : 'cellmin';
      setVal(prefix + '-' + uuid, val);
      var maxEl = document.getElementById('cellmax-' + uuid);
      var minEl = document.getElementById('cellmin-' + uuid);
      var dvEl  = document.getElementById('deltav-'  + uuid);
      if (maxEl && minEl && dvEl) {
        var maxV = parseFloat(maxEl.querySelector('.val').textContent);
        var minV = parseFloat(minEl.querySelector('.val').textContent);
        if (!isNaN(maxV) && !isNaN(minV)) {
          dvEl.textContent = (maxV - minV).toFixed(3) + ' V';
        }
      }
      return;
    }

    if (scope === 'forecastDemand') {
      var fdEl = document.getElementById('fc-demand-' + uuid);
      if (fdEl) { fdEl.textContent = val.toLocaleString(); updateForecast(uuid); }
      return;
    }

    if (scope === 'contractDemand') {
      var fcEl = document.getElementById('fc-contract-' + uuid);
      if (fcEl) { fcEl.textContent = val.toLocaleString(); updateForecast(uuid); }
      return;
    }

    if (scope === 'normalUsageGrid') {
      var ts = item.generatedTime || Date.now();
      processNormalUsage(uuid, val, ts);
      return;
    }
  });
}
