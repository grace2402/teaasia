/**
 * monitoring-parser.js — MQTT 訊息解析與資料分發
 *
 * 職責：
 *  - 接收 MQTT raw JSON string
 *  - 解析 data[] 陣列，按 deviceUuid 分組
 *  - 透過 SITE_MAP 映射到案場 primary UUID
 *  - 呼叫 updateSite(cardId, groupedItems) 更新卡片
 *  - 觸發 broadcastSiteStates() 廣播狀態
 *
 * 依賴：monitoring-config.js (SITES, SITE_MAP), monitoring-update.js (updateSite),
 *        monitoring-broadcast.js (broadcastSiteStates)
 */

(function () {
  'use strict';

  /**
   * 解析 MQTT payload 並分發到各案場卡片
   * @param {string} rawJson - MQTT message body
   */
  function parseAndDistribute(rawJson) {
    var json;
    try {
      json = JSON.parse(rawJson);
    } catch (e) {
      console.error('[Parser] JSON parse error:', e, '| Raw:', rawJson.substring(0, 200));
      return;
    }

    var arr = json.data || [];
    if (!arr.length) {
      console.log('[Parser] Empty data array');
      return;
    }

    // 按 deviceUuid 分組
    var grouped = {};
    arr.forEach(function (item) {
      var uuid = item.deviceUuid;
      if (!uuid) return;
      if (!grouped[uuid]) grouped[uuid] = [];
      grouped[uuid].push(item);
    });

    // 映射到案場 primary UUID，呼叫 updateSite
    Object.keys(grouped).forEach(function (uuid) {
      var cardId = window.SITE_MAP ? window.SITE_MAP[uuid] : null;
      if (!cardId) {
        console.warn('[Parser] Unknown deviceUuid:', uuid);
        return;
      }
      try {
        if (typeof window.updateSite === 'function') {
          window.updateSite(cardId, grouped[uuid]);
        } else {
          console.warn('[Parser] updateSite not defined');
        }
      } catch (e) {
        console.error('[Parser] updateSite error for', cardId, ':', e);
      }
    });

    // 廣播狀態（給 map page）
    try {
      if (typeof window.broadcastSiteStates === 'function') {
        window.broadcastSiteStates();
      }
    } catch (e) {
      console.error('[Parser] broadcastSiteStates error:', e);
    }
  }

  // 註冊為 MQTT 訊息回傳
  window.onMqttMessage = parseAndDistribute;

})();
