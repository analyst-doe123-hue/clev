// Example: Floating button scroll to top
document.addEventListener("DOMContentLoaded", function() {
    const topBtn = document.getElementById("scrollTopBtn");
    if (topBtn) {
        window.onscroll = function () {
            topBtn.style.display = window.scrollY > 300 ? "block" : "none";
        };
        topBtn.onclick = () => window.scrollTo({top: 0, behavior: 'smooth'});
    }
});
// =============================
// Image Slider / Carousel Logic
// =============================
document.addEventListener("DOMContentLoaded", function () {
    const slides = document.querySelector(".slides");
    const slideElements = document.querySelectorAll(".slide");
    const indicatorsContainer = document.getElementById("indicators");

    if (!slides || slideElements.length === 0) return;

    let currentIndex = 0;
    const totalSlides = slideElements.length;

    // Create indicators dynamically
    slideElements.forEach((_, index) => {
        const indicator = document.createElement("div");
        indicator.classList.add("indicator");
        if (index === 0) indicator.classList.add("active");
        indicator.addEventListener("click", () => goToSlide(index));
        indicatorsContainer.appendChild(indicator);
    });
    const indicators = document.querySelectorAll(".indicator");

    function goToSlide(index) {
        currentIndex = index;
        slides.style.transform = `translateX(-${index * 100}%)`;
        updateIndicators();
    }

    function updateIndicators() {
        indicators.forEach((dot, idx) => {
            dot.classList.toggle("active", idx === currentIndex);
        });
    }

    // Auto-slide every 5 seconds
    setInterval(() => {
        currentIndex = (currentIndex + 1) % totalSlides;
        goToSlide(currentIndex);
    }, 5000);
});
