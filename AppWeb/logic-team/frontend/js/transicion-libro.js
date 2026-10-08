// Transición reutilizable: "el libro se acerca, se abre brillando y la luz inunda la pantalla".
// Es independiente de cualquier página: crea sus propias capas y estilos al usarse.
//
// Uso en cualquier página (después de cargar este archivo con {% static 'js/transicion-libro.js' %}):
//
//   TransicionLibro.abrir({
//     origen:  document.getElementById("mi-libro"), // opcional: elemento desde el que "vuela" el libro
//                                                   //   (si se omite, nace en el centro de la pantalla)
//     destino: "/siguiente-pagina/",                // opcional: URL a la que navegar al terminar
//     atenuar: document.getElementById("escena"),   // opcional: elemento que se oscurece durante el vuelo
//     ocultar: document.getElementById("mi-libro"), // opcional: elemento a esconder mientras vuela el libro
//     alTerminar: () => {},                         // opcional: se ejecuta en vez de navegar si no hay destino
//   });
//
// Devuelve una promesa que se resuelve al terminar. Respeta el ajuste "reducir animaciones" (CU03):
// en ese caso no anima y navega (o ejecuta alTerminar) de inmediato.
(function () {
  const CSS = `
  .tl-vuelo { position: fixed; inset: 0; z-index: 9999; pointer-events: none; }
  .tl-libro { position: absolute; perspective: 520px; will-change: transform; }
  .tl-luz { position: absolute; inset: -60%; border-radius: 50%; opacity: 0; transform: scale(.4);
    background: radial-gradient(circle, rgba(255,244,190,.98) 0%, rgba(255,205,100,.4) 38%, rgba(255,190,80,0) 68%); }
  .tl-paginas { position: absolute; inset: 0; border-radius: 2px 4px 4px 2px;
    background:
      repeating-linear-gradient(180deg, transparent 0 9%, rgba(120,80,30,.18) 9% 10%) 14% 18% / 72% 66% no-repeat,
      linear-gradient(100deg, #e2cd98 0%, #f6ebd0 14%, #f1e2b8 100%);
    box-shadow: inset 0 0 18px rgba(170,110,30,.45), 0 0 0 rgba(255,215,120,0); }
  .tl-tapa { position: absolute; inset: 0; transform-origin: left center; transform-style: preserve-3d; }
  .tl-cara { position: absolute; inset: 0; backface-visibility: hidden; -webkit-backface-visibility: hidden; }
  .tl-cara svg { width: 100%; height: 100%; display: block; overflow: visible; }
  .tl-dorso { transform: rotateY(180deg); border-radius: 4px; border: 2px solid #d4a94a;
    background: linear-gradient(120deg, #3a0c0e, #5a1618); }
  .tl-destello { position: absolute; inset: 0; opacity: 0; background: #fff1c2; }`;

  const HTML = `
  <div class="tl-libro">
    <div class="tl-luz"></div>
    <div class="tl-paginas"></div>
    <div class="tl-tapa">
      <div class="tl-cara">
        <svg viewBox="-52 -92 104 140" preserveAspectRatio="none" focusable="false">
          <rect x="-52" y="-92" width="104" height="132" rx="4" fill="#4a1012" stroke="#d4a94a" stroke-width="3"/>
          <rect x="-42" y="-82" width="84" height="112" fill="none" stroke="#d4a94a" stroke-width="1.5" opacity=".8"/>
          <path d="M-18 -44 L-34 -28 L-18 -12 M18 -44 L34 -28 L18 -12 M8 -50 L-8 -6" fill="none" stroke="#e8c46a" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
          <rect x="-52" y="40" width="104" height="8" fill="#f3e6c4"/>
        </svg>
      </div>
      <div class="tl-cara tl-dorso"></div>
    </div>
  </div>
  <div class="tl-destello"></div>`;

  let enCurso = false;

  function sinMovimiento() {
    return document.documentElement.dataset.movimiento === "reducido";
  }

  function ir(opts) {
    if (opts.destino) window.location.href = opts.destino;
    else if (typeof opts.alTerminar === "function") opts.alTerminar();
  }

  async function abrir(opts) {
    opts = opts || {};
    if (enCurso) return;
    if (sinMovimiento()) { ir(opts); return; }
    enCurso = true;

    if (!document.getElementById("tl-estilos")) {
      const st = document.createElement("style");
      st.id = "tl-estilos";
      st.textContent = CSS;
      document.head.appendChild(st);
    }

    const vw = window.innerWidth, vh = window.innerHeight;
    // Rectángulo de partida: el del elemento de origen o un libro pequeño al centro
    let r;
    if (opts.origen) {
      r = opts.origen.getBoundingClientRect();
    } else {
      const h = vh * 0.2;
      r = { left: vw / 2 - (h * 104) / 280, top: vh / 2 - h / 2, width: (h * 104) / 140, height: h };
    }

    const vuelo = document.createElement("div");
    vuelo.className = "tl-vuelo";
    vuelo.setAttribute("aria-hidden", "true");
    vuelo.innerHTML = HTML;
    document.body.appendChild(vuelo);

    const libro = vuelo.querySelector(".tl-libro");
    const luz = vuelo.querySelector(".tl-luz");
    const paginas = vuelo.querySelector(".tl-paginas");
    const tapa = vuelo.querySelector(".tl-tapa");
    const destello = vuelo.querySelector(".tl-destello");
    Object.assign(libro.style, { left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" });

    const ocultar = opts.ocultar || null;
    const atenuar = opts.atenuar || null;
    if (ocultar) ocultar.style.visibility = "hidden";
    if (atenuar) {
      atenuar.style.transition = "filter 1.1s ease";
      atenuar.style.filter = "brightness(.5) saturate(.9)";
    }

    const k = Math.min((vh * 0.62) / r.height, (vw * 0.46) / r.width);
    const dx = vw / 2 - (r.left + r.width / 2);
    const dy = vh / 2 - (r.top + r.height / 2);
    const dxAbierto = dx + (r.width * k) / 2;
    const T = (x, y, s) => `translate(${x}px, ${y}px) scale(${s})`;
    const SOMBRA0 = "inset 0 0 18px rgba(170,110,30,.45), 0 0 0 rgba(255,215,120,0)";
    const SOMBRA1 = "inset 0 0 18px rgba(170,110,30,.45), 0 0 24px 6px rgba(255,215,120,.55)";
    const SOMBRA2 = "inset 0 0 40px rgba(255,235,170,.9), 0 0 80px 30px rgba(255,225,140,.9)";

    // 1) Se acerca
    const a1 = libro.animate([{ transform: T(0, 0, 1) }, { transform: T(dx, dy, k) }],
      { duration: 1300, easing: "cubic-bezier(.45,.05,.2,1)", fill: "forwards" });
    paginas.animate([{ boxShadow: SOMBRA0 }, { boxShadow: SOMBRA1 }], { duration: 1300, easing: "ease-in", fill: "forwards" });
    await a1.finished.catch(() => {});

    // 2) Se abre brillando
    const dur = 1700, ease = "cubic-bezier(.5,0,.25,1)";
    libro.animate([{ transform: T(dx, dy, k) }, { transform: T(dxAbierto, dy, k) }], { duration: dur, easing: ease, fill: "forwards" });
    tapa.animate([{ transform: "rotateY(0deg)" }, { transform: "rotateY(-168deg)" }], { duration: dur, easing: ease, fill: "forwards" });
    luz.animate([{ opacity: 0, transform: "scale(.4)" }, { opacity: .9, transform: "scale(1.4)", offset: .55 }, { opacity: 1, transform: "scale(3)" }],
      { duration: dur, easing: "ease-in", fill: "forwards" });
    paginas.animate([{ boxShadow: SOMBRA1, filter: "brightness(1)" }, { boxShadow: SOMBRA2, filter: "brightness(1.25)" }],
      { duration: dur, easing: "ease-in", fill: "forwards" });
    await new Promise((res) => setTimeout(res, dur - 250));

    // 3) La luz inunda la pantalla y se apaga hacia el tono oscuro de la pantalla de carga
    const fin = destello.animate([
      { opacity: 0, backgroundColor: "#fff1c2" },
      { opacity: 1, backgroundColor: "#fff1c2", offset: .5 },
      { opacity: 1, backgroundColor: "#0d0705" }],
      { duration: 1100, easing: "ease-in-out", fill: "forwards" });
    await fin.finished.catch(() => {});

    if (opts.destino) {
      ir(opts);
    } else {
      // Sin navegación: se limpia todo y se avisa
      vuelo.remove();
      if (ocultar) ocultar.style.visibility = "";
      if (atenuar) atenuar.style.filter = "";
      enCurso = false;
      ir(opts);
    }
  }

  // Si el usuario vuelve con "atrás" (bfcache), se deshace cualquier rastro de la transición
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    enCurso = false;
    document.querySelectorAll(".tl-vuelo").forEach((n) => n.remove());
  });

  window.TransicionLibro = { abrir };
})();
