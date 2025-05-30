// app/static/js/custom.js

document.addEventListener('DOMContentLoaded', function() {
  // 1) Carousel de Billing, já tinhas isto:
  const carouselElement = document.getElementById('billingCarousel');
  if (carouselElement) {
    new bootstrap.Carousel(carouselElement, {
      interval: 5000,
      wrap: true
    });
  }

});