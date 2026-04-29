// ===== BESS Monitoring: DOM Helpers =====
function flash(el) {
  if (!el) return;
  el.classList.remove('flash');
  void el.offsetWidth;
  el.classList.add('flash');
}

function setVal(elId, value) {
  var el = document.getElementById(elId);
  if (!el) return;
  var span = el.querySelector('.val');
  if (span) { span.textContent = value; flash(el); }
}
