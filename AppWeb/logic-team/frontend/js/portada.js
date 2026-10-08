// Portada: encuadre del paisaje. El botón "Iniciar partida" es un enlace normal.
// (La animación del libro que se abre quedó guardada en js/transicion-libro.js para usarla en otras páginas.)
(function () {
  const fondo = document.getElementById("fondo-svg");
  if (!fondo) return;

  // En pantallas verticales se centra el paisaje en el libro
  const LIBRO_X = 480;
  function encuadrar() {
    const aspecto = window.innerWidth / window.innerHeight;
    if (aspecto < 1.2) {
      const ancho = Math.min(1280, 800 * aspecto);
      const x = Math.max(0, Math.min(1280 - ancho, LIBRO_X - ancho / 2));
      fondo.setAttribute("viewBox", `${x.toFixed(1)} 0 ${ancho.toFixed(1)} 800`);
    } else {
      fondo.setAttribute("viewBox", "0 0 1280 800");
    }
  }
  window.addEventListener("resize", encuadrar);
  encuadrar();
})();
