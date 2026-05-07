// ===== BESS Monitoring: GW Tooltip (Click to show device status) =====
(function () {
  'use strict';

  var tooltipEl = null;
  var overlayEl = null;
  var currentSpotId = null;
  var refreshTimer = null;

  function createTooltip() {
    overlayEl = document.createElement('div');
    overlayEl.className = 'gw-tooltip-overlay';
    overlayEl.addEventListener('click', hideTooltip);

    tooltipEl = document.createElement('div');
    tooltipEl.className = 'click-gw-tooltip';
    tooltipEl.innerHTML = '<div class="click-gw-tooltip-header"><h3></h3><button class="click-gw-tooltip-close">&times;</button></div><div class="click-gw-tooltip-body"></div>';

    tooltipEl.querySelector('.click-gw-tooltip-close').addEventListener('click', hideTooltip);
    document.body.appendChild(overlayEl);
    document.body.appendChild(tooltipEl);
  }

  function showTooltip(spotId, siteName) {
    if (!tooltipEl) createTooltip();
    currentSpotId = spotId;

    tooltipEl.querySelector('h3').textContent = siteName + ' — GW 設備狀態';
    var body = tooltipEl.querySelector('.click-gw-tooltip-body');
    body.innerHTML = '<div class="gw-tooltip-loading"><div class="spinner"></div><br>載入中...</div>';

    positionTooltip();
    overlayEl.classList.add('active');
    tooltipEl.classList.add('active');

    fetchCachedStatus(spotId);
  }

  function hideTooltip() {
    if (tooltipEl) tooltipEl.classList.remove('active');
    if (overlayEl) overlayEl.classList.remove('active');
    currentSpotId = null;
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  }

  function positionTooltip() {
    var w = window.innerWidth;
    var h = window.innerHeight;
    tooltipEl.style.left = Math.max(20, (w - 480) / 2) + 'px';
    tooltipEl.style.top = Math.max(20, (h - 500) / 2) + 'px';
  }

  function fetchCachedStatus(spotId) {
    var body = tooltipEl.querySelector('.gw-tooltip-body');

    fetch('/gw_status_cache/' + spotId)
      .then(function (r) {
        if (!r.ok) throw new Error('No cached data');
        return r.json();
      })
      .then(renderTooltip)
      .catch(function () {
        body.innerHTML = '<div class="gw-tooltip-error">⚠️ 暫無快取資料<br><small>後端排程尚未更新此案場</small></div>';
      });
  }

  function renderTooltip(data) {
    var body = tooltipEl.querySelector('.click-gw-tooltip-body');
    if (!data || !data.gateways) {
      body.innerHTML = '<div class="gw-tooltip-error">無資料</div>';
      return;
    }

    var totalDevices = data.device_count || 0;
    var gwCount = data.gw_count || 0;
    var checkedAt = data.checked_at ? new Date(data.checked_at).toLocaleTimeString('zh-TW') : '--';

    var h = '';
    // Summary row
    h += '<div class="gw-tooltip-summary">';
    h += '  <div class="gw-tooltip-summary-item"><div class="label">GW 數量</div><div class="value" style="color:#00d4ff">' + gwCount + '</div></div>';
    h += '  <div class="gw-tooltip-summary-item"><div class="label">設備總數</div><div class="value" style="color:#4ade80">' + totalDevices + '</div></div>';
    h += '  <div class="gw-tooltip-summary-item"><div class="label">整體狀態</div><div class="value gw-tooltip-gw-status ' + data.status_color + '" style="width:16px;height:16px;display:inline-block"></div></div>';
    h += '</div>';

    // Each GW
    var gateways = Array.isArray(data.gateways) ? data.gateways : [];
    gateways.forEach(function (gw, idx) {
      var pid = gw.pid || ('GW-' + idx);
      var color = gw.status_color || 'blue';
      var devices = gw.devices || [];

      h += '<div class="gw-tooltip-gw">';
      h += '  <div class="gw-tooltip-gw-header" onclick="this.nextElementSibling.classList.toggle(\'expanded\')">';
      h += '    <span class="gw-tooltip-gw-name">' + pid.substring(0, 12) + '...</span>';
      h += '    <span class="gw-tooltip-gw-status ' + color + '" title="' + color + '"></span>';
      h += '  </div>';

      if (devices.length > 0) {
        h += '  <div class="gw-tooltip-devices">';
        devices.forEach(function (dev) {
          var devName = dev.name || dev.device_name || dev.product_id || 'Unknown';
          var devStatus = dev.status || dev.online_status || '--';
          h += '<div class="gw-tooltip-device">';
          h += '  <span class="gw-tooltip-device-name">' + devName.substring(0, 20) + '</span>';
          h += '  <span class="gw-tooltip-device-status">' + devStatus + '</span>';
          h += '</div>';
        });
        h += '  </div>';
      } else {
        h += '  <div class="gw-tooltip-devices"><div style="color:#667788;padding:8px;text-align:center">無設備</div></div>';
      }

      h += '</div>';
    });

    // Cached timestamp
    h += '<div class="gw-tooltip-cached">📋 快取時間：' + checkedAt + '</div>';

    body.innerHTML = h;

    // Auto-refresh every 30s
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(function () {
      if (currentSpotId === spotId) fetchCachedStatus(spotId);
    }, 30000);
  }

  // ===== Bind click events to site cards =====
  function bindTooltipEvents() {
    var cards = document.querySelectorAll('.site-card[data-has-gw]');
    cards.forEach(function (card) {
      card.addEventListener('click', function () {
        var spotId = this.getAttribute('data-spot-id');
        var name = this.querySelector('.site-name') ? this.querySelector('.site-name').textContent : '案場';
        showTooltip(spotId, name);
      });
    });
  }

  // Expose globally for init
  window.showGwTooltip = showTooltip;
  window.hideGwTooltip = hideTooltip;
  window.bindTooltipEvents = bindTooltipEvents;

  // ===== SSE: 接收 GW 狀態輕量推送，更新卡片上的小圓點 =====
  function connectSse() {
    var sse = new EventSource('/sse/gw_monitor');
    sse.addEventListener('gw_monitor', function (e) {
      try {
        var data = JSON.parse(e.data);
        if (data.type === 'gw_status_light' && Array.isArray(data.updates)) {
          data.updates.forEach(function (u) {
            var dot = document.getElementById('gw-dot-' + u.spot_id);
            if (dot) {
              dot.className = 'gw-status-dot ' + u.status_color;
              dot.title = 'GW 狀態: ' + u.status_color;
            }
          });
        }
      } catch (err) { /* ignore parse errors */ }
    });
    sse.onerror = function () {
      // EventSource auto-reconnects, no action needed
    };
  }

  connectSse();

})();
