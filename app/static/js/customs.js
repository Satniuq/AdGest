document.addEventListener('DOMContentLoaded', function() {
  const carouselElement = document.getElementById('billingCarousel');
  if(carouselElement) {
      // Se necessário, inicialize manualmente o carousel ou configure comportamentos adicionais.
      new bootstrap.Carousel(carouselElement, {
          interval: 5000,
          wrap: true
      });
  }
});

  