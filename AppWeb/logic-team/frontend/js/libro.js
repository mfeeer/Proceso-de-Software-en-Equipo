// Comportamiento compartido del libro: luciérnagas flotando y entrada del libro.
// Lo carga base.html, así que cualquier página que extienda la base lo tiene.
(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- Luciérnagas / polvo dorado ---
  const canvas = document.getElementById("motes");
  if (canvas && !reduceMotion) {
    const ctx = canvas.getContext("2d");
    let W, H, motes = [];

    function initMotes() {
      W = canvas.width = window.innerWidth;
      H = canvas.height = window.innerHeight;
      motes = Array.from({ length: 70 }, () => ({
        x: Math.random() * W,
        y: Math.random() * H,
        r: Math.random() * 2 + 0.6,
        vy: -(Math.random() * 0.25 + 0.05),
        vx: (Math.random() - 0.5) * 0.2,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.02 + 0.008,
      }));
    }

    function drawMotes() {
      ctx.clearRect(0, 0, W, H);
      motes.forEach((m) => {
        m.x += m.vx + Math.sin(m.phase) * 0.15;
        m.y += m.vy;
        m.phase += m.speed;
        if (m.y < -10) { m.y = H + 10; m.x = Math.random() * W; }
        const a = 0.25 + 0.45 * (0.5 + 0.5 * Math.sin(m.phase * 3));
        ctx.beginPath();
        ctx.arc(m.x, m.y, m.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 213, 120, ${a})`;
        ctx.shadowBlur = 10;
        ctx.shadowColor = "rgba(255, 190, 80, 0.9)";
        ctx.fill();
      });
      ctx.shadowBlur = 0;
      requestAnimationFrame(drawMotes);
    }

    window.addEventListener("resize", initMotes);
    initMotes();
    drawMotes();
  }

  // --- Entrada: se quita la pantalla de carga y se abre el libro ---
  window.addEventListener("load", () => {
    setTimeout(() => {
      const loader = document.getElementById("loader-overlay");
      const book = document.getElementById("main-book");
      if (loader) loader.classList.add("hidden");
      if (book) book.classList.add("visible");
    }, reduceMotion ? 0 : 2200);
  });

  // --- Llegada desde la transición "el libro se abre" (ver js/transicion.js) ---
  try {
    if (sessionStorage.getItem("trLlegada")) {
      sessionStorage.removeItem("trLlegada");
      const luz = document.createElement("div");
      luz.className = "tr-llegada";
      document.body.appendChild(luz);
      requestAnimationFrame(() => requestAnimationFrame(() => luz.classList.add("fuera")));
      setTimeout(() => luz.remove(), 1300);
    }
  } catch (e) { /* sin almacenamiento: no pasa nada */ }
})();
