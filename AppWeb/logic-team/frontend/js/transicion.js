// Transición "el libro se abre" (ver css/transicion.css).
//
// Uso:  TransicionLibro.abrir(() => form.submit());
//
// El libro nace exactamente donde está el libro de la imagen de fondo (img/fondo-camino.jpg),
// se acerca hasta llenar la pantalla, se abre en una luz dorada y, al terminar, llama al
// callback (normalmente para enviar el formulario o cambiar de página).
(function () {
  // Posición del libro dentro de la imagen de fondo (fracciones de su ancho y alto).
  // La imagen mide 2000x1250 y el libro (con sus hojas) ocupa x 667-833, y 310-531.
  const LIBRO = { x: 667 / 2000, y: 310 / 1250, w: 166 / 2000, h: 222 / 1250 };
  const FONDO_RATIO = 2000 / 1250;

  const SVG = `
    <svg viewBox="0 0 166 222" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="2" y="209" width="162" height="12" rx="1" fill="#f3e4bf"/>
      <rect x="1.5" y="1.5" width="163" height="208" rx="8" fill="#4a0f0f" stroke="#d9a93f" stroke-width="3"/>
      <rect x="17" y="17" width="132" height="176" fill="none" stroke="#b88a35" stroke-width="1.5"/>
      <g fill="none" stroke="#e8b94f" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="55,75 28,100 55,127"/>
        <line x1="95" y1="67" x2="71" y2="137"/>
        <polyline points="110,75 137,100 110,127"/>
      </g>
    </svg>`;

  // Rectángulo (en px de la ventana) donde el CSS dibuja la imagen de fondo.
  function cajaDelFondo() {
    const vw = window.innerWidth, vh = window.innerHeight;
    // En pantallas chicas el fondo se desplaza con la página; en las demás está fijo.
    const fijo = vw > 720;
    const caja = fijo
      ? { left: 0, top: 0, width: vw, height: vh }
      : document.documentElement.getBoundingClientRect();
    const escala = Math.max(caja.width / 2000, caja.height / 1250); // background-size: cover
    const ancho = 2000 * escala, alto = 1250 * escala;
    return {
      left: caja.left + (caja.width - ancho) / 2,
      top: caja.top + (caja.height - alto) / 2,
      width: ancho,
      height: alto,
    };
  }

  let enCurso = false;

  function abrir(alTerminar) {
    if (enCurso) return;
    enCurso = true;

    const reducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    try { sessionStorage.setItem("trLlegada", "1"); } catch (e) { /* sin almacenamiento: no pasa nada */ }
    if (reducido) { alTerminar(); return; }

    const vw = window.innerWidth, vh = window.innerHeight;
    const f = cajaDelFondo();
    const L = f.left + LIBRO.x * f.width, T = f.top + LIBRO.y * f.height;
    const W = LIBRO.w * f.width, H = LIBRO.h * f.height;

    // Destino: el libro centrado, ocupando ~72% del alto de la ventana
    const escala = (vh * 0.72) / H;
    const dx = vw / 2 - (L + W / 2), dy = vh * 0.5 - (T + H / 2);

    const capa = document.createElement("div");
    capa.className = "tr-capa";
    capa.innerHTML =
      '<div class="tr-velo"></div>' +
      '<div class="tr-luz"></div>' +
      '<div class="tr-libro">' + SVG + "</div>" +
      '<div class="tr-destello"></div>';
    document.body.appendChild(capa);

    const libro = capa.querySelector(".tr-libro");
    const luz = capa.querySelector(".tr-luz");
    Object.assign(libro.style, { left: L + "px", top: T + "px", width: W + "px", height: H + "px" });
    // La luz ocupa el lugar de la tapa ya agrandada (sin las hojas de abajo)
    const hLuz = (H * 209) / 222 * escala, wLuz = W * escala;
    Object.assign(luz.style, {
      width: wLuz + "px", height: hLuz + "px",
      left: vw / 2 - wLuz / 2 + "px", top: vh * 0.5 - hLuz / 2 - (H * 6 * escala) / 222 + "px",
    });

    const paso = (ms, fn) => setTimeout(fn, ms);
    document.body.classList.add("tr-saliendo");                       // el contenido se desvanece
    requestAnimationFrame(() => requestAnimationFrame(() => capa.classList.add("f1")));  // aparece el libro
    paso(380, () => {                                                  // el libro se acerca
      capa.classList.add("f2");
      libro.style.transform = "translate(" + dx + "px," + dy + "px) scale(" + escala + ")";
    });
    paso(1750, () => capa.classList.add("f3"));                        // se abre en luz
    paso(2850, () => capa.classList.add("f4"));                        // la luz inunda la pantalla
    paso(3550, () => alTerminar());                                    // cambia de página
  }

  window.TransicionLibro = { abrir };
})();
