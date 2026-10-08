// Transición "el libro se abre" (ver css/transicion.css).
//
// Uso:  TransicionLibro.abrir(() => form.submit());
//
// 1) El libro nace exactamente donde está el libro de la imagen de fondo (img/fondo-camino.jpg)
//    y se acerca al centro de la pantalla.
// 2) La tapa se va abriendo y, conforme se abre, sale luz desde dentro del libro.
// 3) La luz ilumina toda la pantalla un momento y entonces se llama al callback (normalmente
//    para enviar el formulario). La página siguiente (el libro abierto del CU01) aparece desde
//    esa misma luz: ver ".tr-llegada" en js/libro.js.
// Respeta "reducir animaciones" (sistema operativo o ajuste de CU03): en ese caso no anima.
(function () {
  // Copia del fondo sin el libro: se pone debajo del libro que vuela para que no se vea el
  // libro original "quedarse atrás". Se precarga para que esté lista al empezar.
  const SIN_LIBRO = (document.currentScript ? document.currentScript.src : "/static/js/transicion.js")
    .replace(/js\/transicion\.js.*$/, "img/fondo-camino-sin-libro.jpg");
  new Image().src = SIN_LIBRO;

  // Posición del libro dentro de la imagen de fondo (fracciones de su ancho y alto).
  // La imagen mide 2000x1250 y el libro (con sus hojas) ocupa x 667-833, y 310-531.
  const LIBRO = { x: 667 / 2000, y: 310 / 1250, w: 166 / 2000, h: 222 / 1250 };

  // Tapa del libro (réplica del de la imagen de fondo)
  const TAPA = `
    <svg viewBox="0 0 166 222" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="1.5" y="1.5" width="163" height="219" rx="8" fill="#4a0f0f" stroke="#d9a93f" stroke-width="3"/>
      <rect x="17" y="17" width="132" height="188" fill="none" stroke="#b88a35" stroke-width="1.5"/>
      <g fill="none" stroke="#e8b94f" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="55,80 28,105 55,132"/>
        <line x1="95" y1="72" x2="71" y2="142"/>
        <polyline points="110,80 137,105 110,132"/>
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

  function sinMovimiento() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.dataset.movimiento === "reducido";
  }

  const esperar = (ms) => new Promise((res) => setTimeout(res, ms));
  let enCurso = false;

  async function abrir(alTerminar) {
    if (enCurso) return;
    enCurso = true;

    // La página siguiente nace de la luz (js/libro.js) y se salta la pantalla de carga.
    try { sessionStorage.setItem("trLlegada", "1"); } catch (e) { /* sin almacenamiento: no pasa nada */ }
    if (sinMovimiento() || !document.body.animate) { alTerminar(); return; }

    const vw = window.innerWidth, vh = window.innerHeight;
    const f = cajaDelFondo();
    const L = f.left + LIBRO.x * f.width, T = f.top + LIBRO.y * f.height;
    const W = LIBRO.w * f.width, H = LIBRO.h * f.height;

    // Destino: libro cerrado al centro; abierto mide el doble de ancho, así que se limita a ~84%.
    const k = Math.min((vh * 0.62) / H, (vw * 0.42) / W);
    const dx = vw / 2 - (L + W / 2), dy = vh / 2 - (T + H / 2);
    const mover = (x, s) => `translate(${x}px, ${dy}px) scale(${s})`;

    // Primero se desvanece el contenido de la página para dejar libre el libro del fondo
    document.body.classList.add("tr-saliendo");
    await esperar(500);

    const capa = document.createElement("div");
    capa.className = "tr-capa";
    capa.setAttribute("aria-hidden", "true");
    capa.innerHTML =
      '<div class="tr-sin-libro"></div>' +
      '<div class="tr-velo"></div>' +
      '<div class="tr-libro">' +
      '  <div class="tr-paginas"><div class="tr-brillo"></div></div>' +
      '  <div class="tr-tapa"><div class="tr-cara">' + TAPA + '</div><div class="tr-cara tr-dorso"></div></div>' +
      '</div>' +
      '<div class="tr-luz"></div>' +
      '<div class="tr-destello"></div>';
    document.body.appendChild(capa);

    const libro = capa.querySelector(".tr-libro");
    const tapa = capa.querySelector(".tr-tapa");
    const brillo = capa.querySelector(".tr-brillo");
    const luz = capa.querySelector(".tr-luz");
    const destello = capa.querySelector(".tr-destello");
    Object.assign(libro.style, { left: L + "px", top: T + "px", width: W + "px", height: H + "px" });

    // Parche del fondo sin libro, justo donde está el libro original (con un margen).
    // Lleva el mismo velo oscuro que personalizar.css pone sobre la imagen de fondo.
    const m = Math.max(W, H) * 0.25;
    const px = L - m, py = T - m, pw = W + 2 * m, ph = H + 2 * m;
    const velo = (y) => (0.5 + 0.14 * Math.min(1, Math.max(0, y / vh))).toFixed(3);
    Object.assign(capa.querySelector(".tr-sin-libro").style, {
      left: px + "px", top: py + "px", width: pw + "px", height: ph + "px",
      backgroundImage:
        `linear-gradient(rgba(14,6,6,${velo(py)}), rgba(14,6,6,${velo(py + ph)})), url("${SIN_LIBRO}")`,
      backgroundSize: `100% 100%, ${f.width}px ${f.height}px`,
      backgroundPosition: `0 0, ${f.left - px}px ${f.top - py}px`,
    });

    requestAnimationFrame(() => capa.classList.add("f1")); // se oscurece el paisaje

    // 1) El libro se acerca
    const acercar = libro.animate([{ transform: mover(0, 1) }, { transform: mover(dx, k) }],
      { duration: 1300, easing: "cubic-bezier(.45,.05,.2,1)", fill: "forwards" });
    await acercar.finished.catch(() => {});

    // 2) La tapa se abre y la luz sale desde dentro
    const dur = 1800, suave = "cubic-bezier(.55,0,.25,1)";
    libro.animate([{ transform: mover(dx, k) }, { transform: mover(dx + (W * k) / 2, k) }],
      { duration: dur, easing: suave, fill: "forwards" });
    tapa.animate([{ transform: "rotateY(0deg)" }, { transform: "rotateY(-172deg)" }],
      { duration: dur, easing: suave, fill: "forwards" });
    brillo.animate([{ opacity: 0 }, { opacity: 0.6, offset: 0.35 }, { opacity: 1 }],
      { duration: dur, easing: "ease-in", fill: "forwards" });
    Object.assign(luz.style, { width: W * k * 2 + "px", height: H * k + "px" });
    luz.animate([
      { opacity: 0, transform: "translate(-50%, -50%) scale(.25)" },
      { opacity: 0.85, transform: "translate(-50%, -50%) scale(1.1)", offset: 0.6 },
      { opacity: 1, transform: "translate(-50%, -50%) scale(2.6)" }],
      { duration: dur, easing: "ease-in", fill: "forwards" });
    await esperar(dur - 350);

    // 3) La luz ilumina toda la pantalla y da paso a la siguiente página
    const inundar = destello.animate([{ opacity: 0 }, { opacity: 1 }],
      { duration: 650, easing: "ease-in", fill: "forwards" });
    await inundar.finished.catch(() => {});
    await esperar(180);
    alTerminar();
  }

  // Si el usuario vuelve con "atrás" (bfcache), se deshace cualquier rastro de la transición
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    enCurso = false;
    document.body.classList.remove("tr-saliendo");
    document.querySelectorAll(".tr-capa").forEach((n) => n.remove());
  });

  window.TransicionLibro = { abrir };
})();
