// ===== BESS Monitoring: Build Site Card HTML =====
function buildCard(uuid, name) {
  var h = '';
  h += '<div class="site-card" id="card-' + uuid + '">';
  h +=   '<div class="site-header">';
  h +=     '<div>';
  h +=       '<div class="site-name">' + name + '</div>';
  h +=       '<div class="site-uuid">' + uuid.substring(0, 8) + '...</div>';
  h +=     '</div>';
  h +=     '<div class="site-time" id="time-' + uuid + '">--</div>';
  h +=   '</div>';
  h +=   '<div class="soc-wrap">';
  h +=     '<div class="soc-track">';
  h +=       '<div class="soc-fill" id="soc-fill-' + uuid + '"></div>';
  h +=       '<div class="soc-label" id="soc-label-' + uuid + '">SOC --</div>';
  h +=     '</div>';
  h +=   '</div>';
  h +=   '<div class="metrics">';
  h +=     '<div class="metric purple"><div class="m-label">SOH</div><div class="m-value" id="soh-' + uuid + '"><span class="val">--</span><span class="m-unit">%</span></div></div>';
  h +=     '<div class="metric yellow"><div class="m-label">溫度</div><div class="m-value" id="temp-' + uuid + '"><span class="val">--</span><span class="m-unit">°C</span></div></div>';
  h +=     '<div class="metric red"><div class="m-label">Cell 最高</div><div class="m-value" id="cellmax-' + uuid + '"><span class="val">--</span><span class="m-unit">V</span></div></div>';
  h +=     '<div class="metric blue"><div class="m-label">Cell 最低</div><div class="m-value" id="cellmin-' + uuid + '"><span class="val">--</span><span class="m-unit">V</span></div></div>';
  h +=   '</div>';
  h +=   '<div class="delta-row">&#x394;V = <strong id="deltav-' + uuid + '">-- mV</strong></div>';
  h +=   '<div class="power-row">';
  h +=     '<div class="power-card">';
  h +=       '<div class="p-label">即時功率</div>';
  h +=       '<div><span class="p-value idle" id="rp-' + uuid + '">--</span><span class="p-unit">kW</span><span class="badge" id="badge-' + uuid + '" style="display:none"></span></div>';
  h +=     '</div>';
  h +=     '<div class="power-card">';
  h +=       '<div class="p-label">EMS 設定</div>';
  h +=       '<div><span class="ems-val" id="ems-' + uuid + '">--</span><span class="p-unit">kW</span></div>';
  h +=     '</div>';
  h +=   '</div>';
  h +=   '<div class="forecast-wrap">';
  h +=     '<div class="forecast-header">';
  h +=       '<span class="forecast-title">15 分鐘預測需量 vs 契約</span>';
  h +=       '<span class="forecast-status" id="fc-status-' + uuid + '">--</span>';
  h +=     '</div>';
  h +=     '<div class="forecast-track">';
  h +=       '<div class="forecast-fill" id="fc-fill-' + uuid + '"></div>';
  h +=       '<div class="forecast-contract-line" id="fc-line-' + uuid + '" style="left:100%"></div>';
  h +=     '</div>';
  h +=     '<div class="forecast-nums">';
  h +=       '<span>需量 <span class="f-val" id="fc-demand-' + uuid + '">--</span> kW</span>';
  h +=       '<span>契約 <span class="f-val" id="fc-contract-' + uuid + '">--</span> kW</span>';
  h +=       '<span class="f-pct" id="fc-pct-' + uuid + '">--%</span>';
  h +=     '</div>';
  h +=   '</div>';
  h += '</div>';
  return h;
}

// Initialize cards on page load
function initCards() {
  var grid = document.getElementById('sites-grid');
  if (!grid) return;
  SITES.forEach(function(s) {
    var uuids = Array.isArray(s.uuid) ? s.uuid : [s.uuid];
    var primaryUuid = uuids[0];
    grid.insertAdjacentHTML('beforeend', buildCard(primaryUuid, s.name));
  });
}
