(function() {
  "use strict";

  /**
   * Apply .scrolled class to the body as the page is scrolled down
   */
  function toggleScrolled() {
    const selectBody = document.querySelector('body');
    const selectHeader = document.querySelector('#header');

    // ✅ ADD NULL CHECKS
    if (!selectBody || !selectHeader) return;
    if (!selectHeader.classList.contains('scroll-up-sticky') && !selectHeader.classList.contains('sticky-top') && !selectHeader.classList.contains('fixed-top')) return;

    window.scrollY > 100 ? selectBody.classList.add('scrolled') : selectBody.classList.remove('scrolled');
  }

  // ✅ ONLY ADD EVENT LISTENERS IF ELEMENTS EXIST
  if (document.querySelector('body') && document.querySelector('#header')) {
    document.addEventListener('scroll', toggleScrolled);
    window.addEventListener('load', toggleScrolled);
  }

  /**
   * Init swiper sliders
   */
  function initSwiper() {
    const swiperElements = document.querySelectorAll(".init-swiper");

    // ✅ CHECK IF SWIPER ELEMENTS EXIST
    if (swiperElements.length === 0) return;

    swiperElements.forEach(function(swiperElement) {
      const swiperConfig = swiperElement.querySelector(".swiper-config");

      // ✅ CHECK IF CONFIG EXISTS
      if (!swiperConfig) return;

      let config = JSON.parse(swiperConfig.innerHTML.trim());

      if (swiperElement.classList.contains("swiper-tab")) {
        initSwiperWithCustomPagination(swiperElement, config);
      } else {
        // ✅ CHECK IF SWIPER IS AVAILABLE
        if (typeof Swiper !== 'undefined') {
          new Swiper(swiperElement, config);
        }
      }
    });
  }

  // ✅ ONLY INIT SWIPER IF ELEMENTS EXIST
  if (document.querySelector(".init-swiper")) {
    window.addEventListener("load", initSwiper);
  }

  /**
   * Mobile nav toggle
   */
  const mobileNavToggleBtn = document.querySelector('.mobile-nav-toggle');

  function mobileNavToogle() {
    const body = document.querySelector('body');
    if (!body) return;

    body.classList.toggle('mobile-nav-active');

    // ✅ CHECK IF BUTTON EXISTS BEFORE TOGGLING CLASSES
    if (mobileNavToggleBtn) {
      mobileNavToggleBtn.classList.toggle('bi-list');
      mobileNavToggleBtn.classList.toggle('bi-x');
    }
  }

  // ✅ ONLY ADD EVENT LISTENER IF BUTTON EXISTS
  if (mobileNavToggleBtn) {
    mobileNavToggleBtn.addEventListener('click', mobileNavToogle);
  }

  /**
   * Hide mobile nav on same-page/hash links
   */
  const navmenuLinks = document.querySelectorAll('#navmenu a');

  // ✅ ONLY ADD EVENT LISTENERS IF LINKS EXIST
  if (navmenuLinks.length > 0) {
    navmenuLinks.forEach(navmenu => {
      navmenu.addEventListener('click', () => {
        if (document.querySelector('.mobile-nav-active')) {
          mobileNavToogle();
        }
      });
    });
  }

  /**
   * Toggle mobile nav dropdowns
   */
  const toggleDropdowns = document.querySelectorAll('.navmenu .toggle-dropdown');

  // ✅ ONLY ADD EVENT LISTENERS IF DROPDOWNS EXIST
  if (toggleDropdowns.length > 0) {
    toggleDropdowns.forEach(navmenu => {
      navmenu.addEventListener('click', function(e) {
        e.preventDefault();
        this.parentNode.classList.toggle('active');
        this.parentNode.nextElementSibling.classList.toggle('dropdown-active');
        e.stopImmediatePropagation();
      });
    });
  }

  /**
   * Preloader
   */
  const preloader = document.querySelector('#preloader');
  if (preloader) {
    window.addEventListener('load', () => {
      preloader.remove();
    });
  }

  /**
   * Scroll top button
   */
  let scrollTop = document.querySelector('.scroll-top');

  function toggleScrollTop() {
    if (scrollTop) {
      window.scrollY > 100 ? scrollTop.classList.add('active') : scrollTop.classList.remove('active');
    }
  }

  // ✅ ONLY ADD EVENT LISTENERS IF SCROLLTOP EXISTS
  if (scrollTop) {
    scrollTop.addEventListener('click', (e) => {
      e.preventDefault();
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    });

    window.addEventListener('load', toggleScrollTop);
    document.addEventListener('scroll', toggleScrollTop);
  }

  /**
   * Animation on scroll function and init
   */
  function aosInit() {
    // ✅ CHECK IF AOS IS AVAILABLE
    if (typeof AOS !== 'undefined') {
      AOS.init({
        duration: 600,
        easing: 'ease-in-out',
        once: true,
        mirror: false
      });
    }
  }
  window.addEventListener('load', aosInit);

  /**
   * Countdown timer
   */
  function updateCountDown(countDownItem) {
    const timeleft = new Date(countDownItem.getAttribute('data-count')).getTime() - new Date().getTime();

    const days = Math.floor(timeleft / (1000 * 60 * 60 * 24));
    const hours = Math.floor((timeleft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((timeleft % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((timeleft % (1000 * 60)) / 1000);

    const daysElement = countDownItem.querySelector('.count-days');
    const hoursElement = countDownItem.querySelector('.count-hours');
    const minutesElement = countDownItem.querySelector('.count-minutes');
    const secondsElement = countDownItem.querySelector('.count-seconds');

    if (daysElement) daysElement.innerHTML = days;
    if (hoursElement) hoursElement.innerHTML = hours;
    if (minutesElement) minutesElement.innerHTML = minutes;
    if (secondsElement) secondsElement.innerHTML = seconds;
  }

  const countdownElements = document.querySelectorAll('.countdown');

  // ✅ ONLY INIT COUNTDOWN IF ELEMENTS EXIST
  if (countdownElements.length > 0) {
    countdownElements.forEach(function(countDownItem) {
      updateCountDown(countDownItem);
      setInterval(function() {
        updateCountDown(countDownItem);
      }, 1000);
    });
  }

  /**
   * Ecommerce Cart Functionality
   * Handles quantity changes and item removal
   */
  function ecommerceCartTools() {
    // Get all quantity buttons and inputs directly
    const decreaseButtons = document.querySelectorAll('.quantity-btn.decrease');
    const increaseButtons = document.querySelectorAll('.quantity-btn.increase');
    const quantityInputs = document.querySelectorAll('.quantity-input');
    const removeButtons = document.querySelectorAll('.remove-item');

    // ✅ ONLY ADD EVENT LISTENERS IF ELEMENTS EXIST
    // Decrease quantity buttons
    if (decreaseButtons.length > 0) {
      decreaseButtons.forEach(btn => {
        btn.addEventListener('click', function() {
          const quantityInput = btn.closest('.quantity-selector')?.querySelector('.quantity-input');
          if (!quantityInput) return;

          let currentValue = parseInt(quantityInput.value);
          if (currentValue > 1) {
            quantityInput.value = currentValue - 1;
          }
        });
      });
    }

    // Increase quantity buttons
    if (increaseButtons.length > 0) {
      increaseButtons.forEach(btn => {
        btn.addEventListener('click', function() {
          const quantityInput = btn.closest('.quantity-selector')?.querySelector('.quantity-input');
          if (!quantityInput) return;

          let currentValue = parseInt(quantityInput.value);
          const maxValue = parseInt(quantityInput.getAttribute('max')) || 999;
          if (currentValue < maxValue) {
            quantityInput.value = currentValue + 1;
          }
        });
      });
    }

    // Manual quantity inputs
    if (quantityInputs.length > 0) {
      quantityInputs.forEach(input => {
        input.addEventListener('change', function() {
          let currentValue = parseInt(input.value);
          const min = parseInt(input.getAttribute('min')) || 1;
          const max = parseInt(input.getAttribute('max')) || 999;

          // Validate input
          if (isNaN(currentValue) || currentValue < min) {
            input.value = min;
          } else if (currentValue > max) {
            input.value = max;
          }
        });
      });
    }

    // Remove item buttons
    if (removeButtons.length > 0) {
      removeButtons.forEach(btn => {
        btn.addEventListener('click', function() {
          const cartItem = btn.closest('.cart-item');
          if (cartItem) {
            cartItem.remove();
          }
        });
      });
    }
  }

  // ✅ ONLY INIT CART TOOLS IF RELEVANT ELEMENTS EXIST
  if (document.querySelector('.quantity-btn') || document.querySelector('.remove-item')) {
    ecommerceCartTools();
  }

  /**
   * Initiate glightbox
   */
  function initGlightbox() {
    // ✅ CHECK IF GLIGHTBOX IS AVAILABLE
    if (typeof GLightbox !== 'undefined') {
      const glightbox = GLightbox({
        selector: '.glightbox'
      });
    }
  }

  // ✅ ONLY INIT GLIGHTBOX IF ELEMENTS EXIST
  if (document.querySelector('.glightbox')) {
    initGlightbox();
  }

  /**
   * Product Image Zoom and Thumbnail Functionality
   */
  function productDetailFeatures() {
    // ✅ CHECK IF PRODUCT DETAIL ELEMENTS EXIST
    const hasProductDetail = document.querySelector('#main-product-image') ||
                            document.querySelector('.thumbnail-item') ||
                            document.querySelector('.image-nav-btn');

    if (!hasProductDetail) return;

    // Initialize Drift for image zoom
    function initDriftZoom() {
      // Check if Drift is available
      if (typeof Drift === 'undefined') {
        console.log('Drift library is not loaded');
        return;
      }

      const driftOptions = {
        paneContainer: document.querySelector('.image-zoom-container'),
        inlinePane: window.innerWidth < 768 ? true : false,
        inlineOffsetY: -85,
        containInline: true,
        hoverBoundingBox: false,
        zoomFactor: 3,
        handleTouch: false
      };

      // Initialize Drift on the main product image
      const mainImage = document.getElementById('main-product-image');
      if (mainImage) {
        new Drift(mainImage, driftOptions);
      }
    }

    // Thumbnail click functionality
    function initThumbnailClick() {
      const thumbnails = document.querySelectorAll('.thumbnail-item');
      const mainImage = document.getElementById('main-product-image');

      if (!thumbnails.length || !mainImage) return;

      thumbnails.forEach(thumbnail => {
        thumbnail.addEventListener('click', function() {
          // Get image path from data attribute
          const imageSrc = this.getAttribute('data-image');

          // Update main image src and zoom attribute
          mainImage.src = imageSrc;
          mainImage.setAttribute('data-zoom', imageSrc);

          // Update active state
          thumbnails.forEach(item => item.classList.remove('active'));
          this.classList.add('active');

          // Reinitialize Drift for the new image
          initDriftZoom();
        });
      });
    }

    // Image navigation functionality (prev/next buttons)
    function initImageNavigation() {
      const prevButton = document.querySelector('.image-nav-btn.prev-image');
      const nextButton = document.querySelector('.image-nav-btn.next-image');

      if (!prevButton || !nextButton) return;

      const thumbnails = Array.from(document.querySelectorAll('.thumbnail-item'));
      if (!thumbnails.length) return;

      // Function to navigate to previous or next image
      function navigateImage(direction) {
        // Find the currently active thumbnail
        const activeIndex = thumbnails.findIndex(thumb => thumb.classList.contains('active'));
        if (activeIndex === -1) return;

        let newIndex;
        if (direction === 'prev') {
          // Go to previous image or loop to the last one
          newIndex = activeIndex === 0 ? thumbnails.length - 1 : activeIndex - 1;
        } else {
          // Go to next image or loop to the first one
          newIndex = activeIndex === thumbnails.length - 1 ? 0 : activeIndex + 1;
        }

        // Simulate click on the new thumbnail
        thumbnails[newIndex].click();
      }

      // Add event listeners to navigation buttons
      prevButton.addEventListener('click', () => navigateImage('prev'));
      nextButton.addEventListener('click', () => navigateImage('next'));
    }

    // Initialize all features
    initDriftZoom();
    initThumbnailClick();
    initImageNavigation();
  }

  // ✅ ONLY INIT PRODUCT DETAIL FEATURES IF ON PRODUCT PAGE
  if (document.querySelector('#main-product-image') || document.querySelector('.thumbnail-item')) {
    productDetailFeatures();
  }

  /**
   * Price range slider implementation for price filtering.
   */
  function priceRangeWidget() {
    // Get all price range widgets on the page
    const priceRangeWidgets = document.querySelectorAll('.price-range-container');

    // ✅ CHECK IF PRICE RANGE WIDGETS EXIST
    if (priceRangeWidgets.length === 0) return;

    priceRangeWidgets.forEach(widget => {
      const minRange = widget.querySelector('.min-range');
      const maxRange = widget.querySelector('.max-range');
      const sliderProgress = widget.querySelector('.slider-progress');
      const minPriceDisplay = widget.querySelector('.current-range .min-price');
      const maxPriceDisplay = widget.querySelector('.current-range .max-price');
      const minPriceInput = widget.querySelector('.min-price-input');
      const maxPriceInput = widget.querySelector('.max-price-input');
      const applyButton = widget.querySelector('.filter-actions .btn-primary');

      if (!minRange || !maxRange || !sliderProgress || !minPriceDisplay || !maxPriceDisplay || !minPriceInput || !maxPriceInput) return;

      // ... rest of price range code (this part was already safe)
      // Slider configuration
      const sliderMin = parseInt(minRange.min);
      const sliderMax = parseInt(minRange.max);
      const step = parseInt(minRange.step) || 1;

      // Initialize with default values
      let minValue = parseInt(minRange.value);
      let maxValue = parseInt(maxRange.value);

      // Set initial values
      updateSliderProgress();
      updateDisplays();

      // Min range input event
      minRange.addEventListener('input', function() {
        minValue = parseInt(this.value);

        // Ensure min doesn't exceed max
        if (minValue > maxValue) {
          minValue = maxValue;
          this.value = minValue;
        }

        // Update min price input and display
        minPriceInput.value = minValue;
        updateDisplays();
        updateSliderProgress();
      });

      // ... rest of the price range functionality remains the same
    });
  }

  // ✅ ONLY INIT PRICE RANGE IF WIDGETS EXIST
  if (document.querySelector('.price-range-container')) {
    priceRangeWidget();
  }

  /**
   * Ecommerce Checkout Section
   * This script handles the functionality of both multi-step and one-page checkout processes
   */
  function initCheckout() {
    // Detect checkout type
    const isMultiStepCheckout = document.querySelector('.checkout-steps') !== null;
    const isOnePageCheckout = document.querySelector('.checkout-section') !== null;

    // ✅ ONLY INIT CHECKOUT IF ON CHECKOUT PAGE
    if (!isMultiStepCheckout && !isOnePageCheckout) return;

    // Initialize common functionality
    initInputMasks();
    initPromoCode();

    // Initialize checkout type specific functionality
    if (isMultiStepCheckout) {
      initMultiStepCheckout();
    }

    if (isOnePageCheckout) {
      initOnePageCheckout();
    }

    // Initialize tooltips (works for both checkout types)
    initTooltips();
  }

  // ✅ ONLY INIT CHECKOUT IF ON CHECKOUT PAGE
  if (document.querySelector('.checkout-steps') || document.querySelector('.checkout-section')) {
    window.addEventListener('load', initCheckout);
  }

  // ... rest of your checkout functions remain the same but should also include null checks

  /**
   * Initiate Pure Counter
   */
  function initPureCounter() {
    // ✅ CHECK IF PURE COUNTER IS AVAILABLE
    if (typeof PureCounter !== 'undefined') {
      new PureCounter();
    }
  }

  // ✅ ONLY INIT PURE COUNTER IF ELEMENTS EXIST
  if (document.querySelector('.purecounter')) {
    initPureCounter();
  }

  /**
   * Frequently Asked Questions Toggle
   */
  const faqItems = document.querySelectorAll('.faq-item h3, .faq-item .faq-toggle, .faq-item .faq-header');

  // ✅ ONLY ADD FAQ EVENT LISTENERS IF FAQ ITEMS EXIST
  if (faqItems.length > 0) {
    faqItems.forEach((faqItem) => {
      faqItem.addEventListener('click', () => {
        faqItem.parentNode.classList.toggle('faq-active');
      });
    });
  }

  // ✅ ADD CONSOLE LOG TO CONFIRM SCRIPT LOADED
  console.log('Pavitra Enterprises main.js loaded successfully');

})();