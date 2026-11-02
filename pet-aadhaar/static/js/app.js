document.addEventListener("DOMContentLoaded", () => {
  const alerts = document.querySelectorAll(".alert-success");
  alerts.forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
    }, 4000);
  });
});
