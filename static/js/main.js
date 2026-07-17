/**
 * LeaShop — Premium JavaScript Engine
 * Animations, micro-interactions, toasts, lightbox, counter-up
 */

(function () {
  'use strict';

  /* ─── Preloader ─────────────────────────────────────────────── */
  function initPreloader() {
    const loader = document.getElementById('page-preloader');
    if (!loader) return;
    window.addEventListener('load', () => {
      setTimeout(() => loader.classList.add('hide'), 300);
    });
    // Safety fallback
    setTimeout(() => loader.classList.add('hide'), 2500);
  }

  /* ─── Dark / Light Theme ────────────────────────────────────── */
  function initTheme() {
    const stored = localStorage.getItem('leashop-theme') || 'light';
    document.documentElement.setAttribute('data-theme', stored);
    updateThemeIcon(stored);

    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('leashop-theme', next);
      updateThemeIcon(next);
      btn.style.transform = 'rotate(360deg)';
      setTimeout(() => (btn.style.transform = ''), 400);
    });
  }

  function updateThemeIcon(theme) {
    const icon = document.querySelector('#themeToggle .theme-icon');
    if (icon) icon.textContent = theme === 'dark' ? '🌙' : '☀️';
  }

  /* ─── Navbar Scroll Effect ──────────────────────────────────── */
  function initNavbar() {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;
    const check = () => navbar.classList.toggle('scrolled', window.scrollY > 30);
    check();
    window.addEventListener('scroll', check, { passive: true });
  }

  /* ─── Reveal on Scroll ──────────────────────────────────────── */
  function initReveal() {
    const els = document.querySelectorAll('.reveal, .reveal-left, .reveal-right');
    if (!els.length) return;

    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('is-visible');
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    els.forEach((el) => obs.observe(el));
  }

  /* ─── Counter-Up Animation ──────────────────────────────────── */
  function animateCounter(el) {
    const target = parseFloat(el.dataset.countTarget || el.textContent.replace(/\D/g, '')) || 0;
    const duration = 1200;
    const start = performance.now();
    const isFloat = el.dataset.countDecimals === '2';

    const update = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out-cubic
      const value = eased * target;
      el.textContent = isFloat
        ? value.toFixed(2).replace('.', ',')
        : Math.floor(value).toLocaleString('fr-FR');
      if (progress < 1) requestAnimationFrame(update);
    };

    requestAnimationFrame(update);
  }

  function initCounters() {
    const counters = document.querySelectorAll('[data-count]');
    if (!counters.length) return;

    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          animateCounter(e.target);
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.5 });

    counters.forEach((c) => obs.observe(c));
  }

  /* ─── Toast Notifications ───────────────────────────────────── */
  window.LeaToast = {
    _container: null,

    _getContainer() {
      if (!this._container) {
        this._container = document.getElementById('toast-container');
        if (!this._container) {
          this._container = document.createElement('div');
          this._container.id = 'toast-container';
          document.body.appendChild(this._container);
        }
      }
      return this._container;
    },

    show(message, { title = '', type = 'info', icon = null, duration = 3500 } = {}) {
      const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
      const chosenIcon = icon || icons[type] || icons.info;
      const container = this._getContainer();

      const item = document.createElement('div');
      item.className = `toast-item toast-${type}`;
      item.innerHTML = `
        <span class="toast-icon">${chosenIcon}</span>
        <div class="toast-body">
          ${title ? `<div class="toast-title">${title}</div>` : ''}
          <div class="toast-msg">${message}</div>
        </div>
        <button onclick="this.closest('.toast-item').remove()" style="background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:1rem;margin-left:0.5rem;padding:0;line-height:1;">✕</button>
      `;
      container.appendChild(item);

      setTimeout(() => {
        item.classList.add('removing');
        setTimeout(() => item.remove(), 350);
      }, duration);
    },

    success(msg, opts) { this.show(msg, { ...opts, type: 'success' }); },
    error(msg, opts)   { this.show(msg, { ...opts, type: 'error' }); },
    warning(msg, opts) { this.show(msg, { ...opts, type: 'warning' }); },
  };

  /* ─── Product Gallery (Lightbox + Thumbnails) ───────────────── */
  function initProductGallery() {
    const mainImg = document.querySelector('.product-main-image');
    const thumbs  = document.querySelectorAll('.product-thumb');
    if (!mainImg || !thumbs.length) return;

    // Thumbnail switching
    thumbs.forEach((thumb) => {
      thumb.addEventListener('click', () => {
        mainImg.style.opacity = '0';
        mainImg.style.transform = 'scale(0.96)';
        setTimeout(() => {
          mainImg.src = thumb.src.replace(/w_70,h_70/, '');
          mainImg.style.opacity = '1';
          mainImg.style.transform = 'scale(1)';
        }, 200);
        thumbs.forEach((t) => t.classList.remove('active'));
        thumb.classList.add('active');
      });
    });

    mainImg.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
    if (thumbs[0]) thumbs[0].classList.add('active');

    // Lightbox
    const overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.innerHTML = `
      <img class="lightbox-img" src="" alt="Vue agrandie">
      <button class="lightbox-close" aria-label="Fermer">✕</button>
    `;
    document.body.appendChild(overlay);

    const lightboxImg = overlay.querySelector('.lightbox-img');
    const closeBtn    = overlay.querySelector('.lightbox-close');

    mainImg.addEventListener('click', () => {
      lightboxImg.src = mainImg.src;
      overlay.classList.add('open');
      document.body.style.overflow = 'hidden';
    });

    const closeLightbox = () => {
      overlay.classList.remove('open');
      document.body.style.overflow = '';
    };

    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeLightbox(); });
    closeBtn.addEventListener('click', closeLightbox);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeLightbox(); });
  }

  /* ─── Quantity Selector ─────────────────────────────────────── */
  function initQtySelectors() {
    document.querySelectorAll('.qty-selector').forEach((wrap) => {
      const input = wrap.querySelector('.qty-val');
      const dec   = wrap.querySelector('[data-qty-dec]');
      const inc   = wrap.querySelector('[data-qty-inc]');
      if (!input || !dec || !inc) return;

      dec.addEventListener('click', () => {
        const val = parseInt(input.value) || 1;
        if (val > 1) input.value = val - 1;
        input.dispatchEvent(new Event('change'));
      });

      inc.addEventListener('click', () => {
        const val = parseInt(input.value) || 1;
        const max = parseInt(input.max) || 999;
        if (val < max) input.value = val + 1;
        input.dispatchEvent(new Event('change'));
      });
    });
  }

  /* ─── Add to Cart Animation ─────────────────────────────────── */
  function initCartButtons() {
    document.querySelectorAll('.btn-add-to-cart').forEach((btn) => {
      const form = btn.closest('form');
      if (!form) return;
      
      form.addEventListener('submit', function (e) {
        // Visual loading state
        const originalHTML = btn.innerHTML;
        btn.classList.add('loading');
        btn.innerHTML = '<span style="display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,0.4);border-top-color:#fff;border-radius:50%;animation:spin 0.7s linear infinite;margin-right:0.4rem;vertical-align:middle;"></span>Ajout...';
        
        // Disable button asynchronously so the form submission isn't blocked
        setTimeout(() => { btn.disabled = true; }, 10);

        // This animation might be interrupted by the page reload (which is intended since it's a standard POST)
        setTimeout(() => {
          btn.classList.remove('loading');
          btn.innerHTML = '✓ Ajouté !';
          btn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
          setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.style.background = '';
            btn.disabled = false;
          }, 1500);
        }, 800);
      });
    });
  }

  /* ─── Variant Selector ──────────────────────────────────────── */
  function initVariantSelector() {
    const variantBtns = document.querySelectorAll('.variant-btn');
    const hiddenInput = document.getElementById('selected-variant-id');
    const cartForm    = document.getElementById('add-to-cart-form');
    if (!variantBtns.length) return;

    variantBtns.forEach((btn) => {
      btn.addEventListener('click', function () {
        variantBtns.forEach((b) => b.classList.remove('active'));
        this.classList.add('active');

        const variantId = this.dataset.variantId;
        if (hiddenInput) hiddenInput.value = variantId;
        if (cartForm) {
          cartForm.action = cartForm.dataset.baseUrl + variantId + '/';
        }

        // Update price display
        const price = this.dataset.price;
        const priceEl = document.querySelector('.product-detail-price');
        if (price && priceEl) {
          priceEl.style.transform = 'scale(1.1)';
          priceEl.textContent = price;
          setTimeout(() => (priceEl.style.transform = 'scale(1)'), 200);
          priceEl.style.transition = 'transform 0.2s ease';
        }

        // Update stock badge
        const inStock = this.dataset.inStock === 'true';
        const submitBtn = document.querySelector('.btn-add-to-cart-main');
        if (submitBtn) {
          submitBtn.disabled = !inStock;
          submitBtn.textContent = inStock ? 'Ajouter au panier' : 'Indisponible';
        }
      });
    });

    // Activate first available variant
    const firstAvailable = Array.from(variantBtns).find((b) => b.dataset.inStock === 'true');
    if (firstAvailable) firstAvailable.click();
  }

  /* ─── Checkout — Payment Panel Toggle ───────────────────────── */
  function initCheckout() {
    const cardOpt  = document.getElementById('payment-card');
    const mmOpt    = document.getElementById('payment-mobile-money');
    const mmPanel  = document.getElementById('mobile-money-panel');
    const fedaOpt  = document.getElementById('payment-fedapay');
    const fedaPanel= document.getElementById('fedapay-panel');

    function update() {
      if (mmPanel) mmPanel.classList.toggle('d-none', !(mmOpt && mmOpt.checked));
      if (fedaPanel) fedaPanel.classList.toggle('d-none', !(fedaOpt && fedaOpt.checked));
    }

    [cardOpt, mmOpt, fedaOpt].forEach((el) => el && el.addEventListener('change', update));
    update();

    // Address radio visual select
    document.querySelectorAll('input[name="address_id"]').forEach((radio) => {
      radio.addEventListener('change', () => {
        document.querySelectorAll('.address-option').forEach((opt) => {
          opt.style.borderColor = '';
          opt.style.background  = '';
        });
        const parent = radio.closest('.address-option');
        if (parent) {
          parent.style.borderColor = 'var(--brand-500)';
          parent.style.background  = 'rgba(99,102,241,0.05)';
        }
      });
    });
  }

  /* ─── Smooth Scroll ─────────────────────────────────────────── */
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach((a) => {
      a.addEventListener('click', (e) => {
        const target = document.querySelector(a.getAttribute('href'));
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });
  }

  /* ─── Google Translate ──────────────────────────────────────── */
  window.googleTranslateElementInit = function () {
    if (typeof google !== 'undefined' && google.translate) {
      new google.translate.TranslateElement(
        {
          pageLanguage: 'fr',
          includedLanguages: 'fr,en,es,ar,de,pt',
          layout: google.translate.TranslateElement.InlineLayout.SIMPLE,
        },
        'google_translate_element'
      );
    }
  };

  /* ─── Confetti for order success ────────────────────────────── */
  function initConfetti() {
    const hero = document.querySelector('.success-hero');
    if (!hero) return;

    const colors = ['#6366f1', '#14b8a6', '#fbbf24', '#f43f5e', '#10b981'];
    for (let i = 0; i < 40; i++) {
      const dot = document.createElement('div');
      const size = Math.random() * 8 + 4;
      dot.style.cssText = `
        position:absolute;
        width:${size}px;height:${size}px;
        border-radius:${Math.random() > 0.5 ? '50%' : '2px'};
        background:${colors[Math.floor(Math.random() * colors.length)]};
        left:${Math.random() * 100}%;
        top:${Math.random() * 50}%;
        animation:confetti-fall ${1.5 + Math.random() * 2}s ease forwards;
        animation-delay:${Math.random() * 0.8}s;
        opacity:0.85;
        pointer-events:none;
      `;
      hero.appendChild(dot);
    }
  }

  /* ─── Lazy Image Load ───────────────────────────────────────── */
  function initLazyImages() {
    const imgs = document.querySelectorAll('img[data-src]');
    if (!imgs.length) return;

    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          const img = e.target;
          img.src = img.dataset.src;
          img.removeAttribute('data-src');
          obs.unobserve(img);
        }
      });
    });

    imgs.forEach((img) => obs.observe(img));
  }

  /* ─── Active nav link ───────────────────────────────────────── */
  function initActiveNav() {
    const path = window.location.pathname;
    document.querySelectorAll('.navbar .nav-link').forEach((link) => {
      if (link.getAttribute('href') === path) {
        link.classList.add('active');
      }
    });
  }

  /* ─── Show/Hide password ─────────────────────────────────────── */
  function initPasswordToggle() {
    document.querySelectorAll('.password-toggle').forEach((btn) => {
      btn.addEventListener('click', () => {
        const input = btn.closest('.password-field-wrap')?.querySelector('input');
        if (!input) return;
        const isText = input.type === 'text';
        input.type = isText ? 'password' : 'text';
        btn.textContent = isText ? '👁️' : '🙈';
      });
    });
  }

  /* ─── Form auto-save address toggle ────────────────────────── */
  function initNewAddressToggle() {
    const radios    = document.querySelectorAll('input[type="radio"][name="address_id"]');
    const newPanel  = document.querySelector('.new-address-panel');
    if (!radios.length || !newPanel) return;

    const update = () => {
      const selected = document.querySelector('input[type="radio"][name="address_id"]:checked');
      const isNew = selected && selected.value === 'new';
      newPanel.style.display = isNew ? '' : 'none';
      newPanel.querySelectorAll('input, select, textarea').forEach(el => el.disabled = !isNew);
    };

    radios.forEach((r) => r.addEventListener('change', update));
    update();
  }

  /* ─── Mobile Money phone panel ──────────────────────────────── */
  function initMobileMoneyPanel() {
    const radios  = document.querySelectorAll('input[name="payment_method"]');
    const panel   = document.getElementById('mobile-money-panel');
    if (!radios.length || !panel) return;

    const update = () => {
      const sel = document.querySelector('input[name="payment_method"]:checked');
      const isMM = sel && sel.value === 'mobile_money';
      panel.classList.toggle('d-none', !isMM);
      panel.querySelectorAll('input, select, textarea').forEach(el => el.disabled = !isMM);
    };

    radios.forEach((r) => r.addEventListener('change', update));
    update();
  }

  /* ─── Bootstrap alert auto-dismiss ─────────────────────────── */
  function initAlertAutoDismiss() {
    document.querySelectorAll('.alert.auto-dismiss').forEach((alert) => {
      setTimeout(() => {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-8px)';
        setTimeout(() => alert.remove(), 400);
      }, 4000);
    });
  }

  /* ─── Sticky progress bar on page load ──────────────────────── */
  function initProgressBar() {
    const bar = document.getElementById('page-progress-bar');
    if (!bar) return;
    window.addEventListener('scroll', () => {
      const winScroll   = document.body.scrollTop || document.documentElement.scrollTop;
      const height      = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      const scrolled    = (winScroll / height) * 100;
      bar.style.width   = scrolled + '%';
    }, { passive: true });
  }

  /* ─── Init All ───────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    initPreloader();
    initTheme();
    initNavbar();
    initReveal();
    initCounters();
    initProductGallery();
    initQtySelectors();
    initCartButtons();
    initVariantSelector();
    initCheckout();
    initSmoothScroll();
    initLazyImages();
    initActiveNav();
    initPasswordToggle();
    initNewAddressToggle();
    initMobileMoneyPanel();
    initAlertAutoDismiss();
    initProgressBar();
    initConfetti();
  });

})();
