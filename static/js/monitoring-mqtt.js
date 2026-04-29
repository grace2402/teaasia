// ===== BESS Monitoring: MQTT Connection Handler =====
var mqttClient = null;

btnConn.addEventListener('click', function() {
  var host  = document.getElementById('cfg-host').value.trim();
  var port  = parseInt(document.getElementById('cfg-port').value.trim());
  var topic = document.getElementById('cfg-topic').value.trim();
  
  if (mqttClient) { mqttClient.end(true); }
  connLabel.textContent = '連線中...';
  dot.className = 'status-dot';
  
  mqttClient = mqtt.connect({ host: host, port: port, protocol: 'ws', path: '/mqtt' });
  
  mqttClient.on('connect', function() {
    setConnected(true);
    if (topic) { mqttClient.subscribe(topic, function(err) { if (err) setError('Subscribe 失敗'); }); }
  });
  
  mqttClient.on('message', function(t, msg) {
    try {
      var json    = JSON.parse(msg.toString());
      var arr     = json.data || [];
      var grouped = {};
      arr.forEach(function(item) {
        if (!grouped[item.deviceUuid]) grouped[item.deviceUuid] = [];
        grouped[item.deviceUuid].push(item);
      });
      Object.keys(grouped).forEach(function(uuid) {
        var cardId = SITE_MAP[uuid];
        if (cardId) updateSite(cardId, grouped[uuid]);
      });
      broadcastSiteStates();
    } catch(e) { console.error('JSON parse error', e); }
  });
  
  mqttClient.on('error', function(err) { setError(err.message); });
  mqttClient.on('close', function() { if (mqttClient) setConnected(false); });
});

btnDisc.addEventListener('click', function() {
  if (mqttClient) { mqttClient.end(); mqttClient = null; }
  setConnected(false);
});
