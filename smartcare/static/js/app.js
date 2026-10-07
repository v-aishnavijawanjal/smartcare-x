/* Shared JavaScript for common UI interactions. */

document.addEventListener('DOMContentLoaded', function () {
  injectSpinnerOverlay();
  wireLoadingSpinner();
  autoDismissAlerts();
  initTooltips();
});

function injectSpinnerOverlay() {
  if (document.querySelector('.sc-spinner-overlay')) return;
  const overlay = document.createElement('div');
  overlay.className = 'sc-spinner-overlay';
  overlay.innerHTML = '<div class="spinner-border" style="color: var(--sc-primary); width: 3rem; height: 3rem;" role="status"><span class="visually-hidden">Loading...</span></div>';
  document.body.appendChild(overlay);
}

function wireLoadingSpinner() {
  const overlay = document.querySelector('.sc-spinner-overlay');
  document.querySelectorAll('form:not([data-no-spinner])').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      // Do nothing if form submission is cancelled.
      if (event.defaultPrevented) return;

      // Show the loading spinner after a short delay.
      setTimeout(function () {
        overlay.classList.add('active');
      }, 300);
    });
  });
}

function autoDismissAlerts() {
  document.querySelectorAll('.alert.alert-dismissible').forEach(function (alertEl) {
    setTimeout(function () {
      const instance = bootstrap.Alert.getOrCreateInstance(alertEl);
      instance.close();
    }, 6000);
  });
}

function initTooltips() {
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el);
  });
}