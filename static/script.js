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
