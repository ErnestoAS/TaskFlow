// Portada: resalta las instrucciones del dispositivo de quien visita y, en iPhone, cambia el
// botón principal por los pasos de Safari (iOS no permite instalar con un botón, §5).
(function () {
  const ua = navigator.userAgent;
  const esIOS = /iPhone|iPad|iPod/i.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const plataforma = esIOS ? "ios" : /Android/i.test(ua) ? "android" : "compu";
  document.querySelectorAll("[data-tarjeta-plat]").forEach(function (t) {
    t.classList.toggle("actual", t.dataset.tarjetaPlat === plataforma);
  });
  document.querySelectorAll("[data-solo]").forEach(function (el) {
    const solo = el.dataset.solo;
    el.hidden = esIOS ? solo !== "ios" : solo === "ios";
  });
  if (esIOS) {
    const detalle = document.getElementById("detalle-portada");
    if (detalle) detalle.textContent = "En iPhone se instala desde Safari con «Compartir → Agregar a pantalla de inicio».";
  }
})();
