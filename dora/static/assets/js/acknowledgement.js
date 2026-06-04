// Daily "no backup" acknowledgement banner.
// Shows the banner on the first page view of each calendar day. Once the user
// clicks "Yes, I acknowledge", a cookie stores today's date so the banner stays
// hidden until the next calendar day (when the stored date no longer matches).
(function () {
  function today() {
    var d = new Date();
    // Local YYYY-MM-DD
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  function getCookie(name) {
    var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  document.addEventListener('DOMContentLoaded', function () {
    var banner = document.getElementById('dora-ack-banner');
    if (!banner) { return; }

    if (getCookie('dora_ack') !== today()) {
      banner.style.display = '';
    }

    var btn = document.getElementById('dora-ack-btn');
    if (btn) {
      btn.addEventListener('click', function () {
        document.cookie = 'dora_ack=' + today() + '; path=/; max-age=31536000; SameSite=Lax';
        banner.style.display = 'none';
      });
    }
  });
})();
