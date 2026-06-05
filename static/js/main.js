/* ═══════════════════════════════════════════════════
   BOOKHUB — main.js
   ═══════════════════════════════════════════════════ */

// ─── TOAST ───────────────────────────────────────────
window.showToast = function (msg, type = 'success') {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'toast toast--hidden';
  toast.textContent = msg;
  if (type === 'error') toast.style.borderColor = 'rgba(224,92,92,0.4)';
  document.body.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.remove('toast--hidden');
  });

  setTimeout(() => {
    toast.classList.add('toast--hidden');
    setTimeout(() => toast.remove(), 350);
  }, 2800);
};

// ─── MOBILE NAV ──────────────────────────────────────
const navToggle = document.getElementById('navToggle');
const navMobile = document.getElementById('navMobile');
if (navToggle && navMobile) {
  navToggle.addEventListener('click', () => {
    navMobile.classList.toggle('open');
    const isOpen = navMobile.classList.contains('open');
    navToggle.setAttribute('aria-expanded', isOpen);
  });
  document.addEventListener('click', (e) => {
    if (!navToggle.contains(e.target) && !navMobile.contains(e.target)) {
      navMobile.classList.remove('open');
    }
  });
}

// ─── PASSWORD TOGGLE ─────────────────────────────────
document.querySelectorAll('.toggle-password').forEach(btn => {
  btn.addEventListener('click', () => {
    const targetId = btn.dataset.target;
    const input = document.getElementById(targetId);
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
    btn.querySelector('svg')?.setAttribute('opacity', input.type === 'text' ? '0.5' : '1');
  });
});

// ─── FLASH AUTO-DISMISS ──────────────────────────────
document.querySelectorAll('.flash').forEach(flash => {
  setTimeout(() => {
    flash.style.transition = 'opacity 0.4s, transform 0.4s';
    flash.style.opacity = '0';
    flash.style.transform = 'translateX(20px)';
    setTimeout(() => flash.remove(), 400);
  }, 4000);
});

// ─── NAVBAR SCROLL SHADOW ────────────────────────────
const navbar = document.querySelector('.navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    navbar.style.boxShadow = window.scrollY > 20
      ? '0 4px 32px rgba(0,0,0,0.4)'
      : 'none';
  }, { passive: true });
}

// ─── SMOOTH SCROLL FOR ANCHOR LINKS ─────────────────
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', e => {
    const target = document.querySelector(anchor.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// ─── BOOK CARD ENTER ANIMATIONS ──────────────────────
const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -40px 0px' };
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
      observer.unobserve(entry.target);
    }
  });
}, observerOptions);

document.querySelectorAll('.book-card, .review-card, .search-result-card, .ranking-row').forEach((el, i) => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = `opacity 0.4s ${i * 0.05}s ease, transform 0.4s ${i * 0.05}s ease`;
  observer.observe(el);
});

// ─── SEARCH AUTOCOMPLETE (DEBOUNCE) ──────────────────
const navSearchInput = document.querySelector('.nav-search input');
if (navSearchInput) {
  let debounceTimer;
  navSearchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      // future: dropdown autocomplete
    }, 300);
  });
}

// ─── PROFILE TAB INDICATOR ───────────────────────────
document.querySelectorAll('.profile-tab').forEach(tab => {
  tab.addEventListener('click', e => {
    document.querySelectorAll('.profile-tab').forEach(t => t.classList.remove('profile-tab--active'));
    tab.classList.add('profile-tab--active');
  });
});
