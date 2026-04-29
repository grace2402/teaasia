// ===== BESS Monitoring: Connection Bar UI =====
var dot       = document.getElementById('status-dot');
var connLabel = document.getElementById('conn-label');
var btnConn   = document.getElementById('btn-connect');
var btnDisc   = document.getElementById('btn-disconnect');

function setConnected(ok) {
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
