/**
 * monitoring-mqtt.js — MQTT WebSocket 連線管理
 *
 * 職責：
 *  - 建立 / 關閉 MQTT over WebSocket 連線
 *  - 訂閱 topic
 *  - 收到訊息後呼叫 window.onMqttMessage(rawJson)
 *
 * 依賴：mqtt.js CDN (global `mqtt` namespace)
 *        monitoring-conn-ui.js (setConnected, setError — global functions)
 */

(function () {
  'use strict';

  var client = null;

  // ── DOM refs ──────────────────────────────────────────────
  var $host  = document.getElementById('cfg-host');
  var $port  = document.getElementById('cfg-port');
  var $topic = document.getElementById('cfg-topic');

  // ── 連線 ──────────────────────────────────────────────────
  function connect() {
    var host  = ($host && $host.value)   || '119.31.178.22';
    var port  = parseInt(($port && $port.value) || '8083', 10);
    var topic = ($topic && $topic.value) || 'ND_ScMaintenance';

    // 先斷舊連線
    if (client) { client.end(true); client = null; }

    setConnected(null);          // reset UI (from conn-ui.js)
    var labelEl = document.getElementById('conn-label');
    if (labelEl) labelEl.textContent = '連線中...';

    try {
      client = mqtt.connect({
        host: host,
        port: port,
        protocol: 'ws',
        path: '/mqtt'
      });
    } catch (e) {
      setError('建立連線失敗: ' + e.message);
      return;
    }

    client.on('connect', function () {
      setConnected(true);
      console.log('[MQTT] Connected, subscribing to:', topic);
      client.subscribe(topic, function (err) {
        if (err) {
          setError('Subscribe 失敗: ' + err.message);
        } else {
          console.log('[MQTT] Subscribed:', topic);
        }
      });
    });

    client.on('message', function (_topic, message) {
      var raw = message.toString();
      if (typeof window.onMqttMessage === 'function') {
        try {
          window.onMqttMessage(raw);
        } catch (e) {
          console.error('[MQTT] onMqttMessage error:', e);
        }
      } else {
        console.log('[MQTT] No handler registered. Raw:', raw.substring(0, 200));
      }
    });

    client.on('error', function (err) {
      console.error('[MQTT] Error:', err.message);
      setError(err.message);
    });

    client.on('close', function () {
      console.log('[MQTT] Connection closed');
      setConnected(false);
    });
  }

  // ── 斷線 ──────────────────────────────────────────────────
  function disconnect() {
    if (client) {
      client.end(true);
      client = null;
    }
    setConnected(false);
  }

  // ── 對外 API ──────────────────────────────────────────────
  window.MonitoringMQTT = {
    connect:    connect,
    disconnect: disconnect,
    getClient:  function () { return client; }
  };

})();
