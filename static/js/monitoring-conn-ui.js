// ===== BESS Monitoring: Connection Bar UI =====
var dot       = document.getElementById('status-dot');
var connLabel = document.getElementById('conn-label');
var btnConn   = document.getElementById('btn-connect');
var btnDisc   = document.getElementById('btn-disconnect');

function setConnected(ok) {
  if (ok === null || ok === undefined) {
    // reset state (connecting...)
    dot.className = 'status-dot';
    connLabel.textContent = '連線中...';
    return;
  }
  dot.className = 'status-dot ' + (ok ? 'connected' : '');
  connLabel.textContent = ok ? '已連線' : '未連線';
  btnConn.style.display = ok ? 'none' : '';
  btnDisc.style.display = ok ? '' : 'none';
}

function setError(msg) {
  dot.className = 'status-dot error';
  connLabel.textContent = '錯誤: ' + msg;
  btnConn.style.display = '';
  btnDisc.style.display = 'none';
}

// ── Wire up button clicks ────────────────────────────────
if (btnConn) {
  btnConn.addEventListener('click', function () {
    if (typeof window.MonitoringMQTT !== 'undefined') {
      window.MonitoringMQTT.connect();
    } else {
      console.error('[ConnUI] MonitoringMQTT not loaded yet!');
    }
  });
}

if (btnDisc) {
  btnDisc.addEventListener('click', function () {
    if (typeof window.MonitoringMQTT !== 'undefined') {
      window.MonitoringMQTT.disconnect();
    } else {
      console.error('[ConnUI] MonitoringMQTT not loaded yet!');
    }
  });
}
