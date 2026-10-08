// Pantalla 2 de Personalizar Partida (CU02): elegir los temas y comenzar la aventura.
//  - Paso 4: se marcan de 1 a 3 temas (se pueden cambiar antes de confirmar).
//  - Special Requirement: la hoja de personaje se actualiza en tiempo real.
//  - RN02: no se puede comenzar sin tema (mínimo 1) ni con más de 3; se muestra un mensaje.
(function () {
  const form = document.getElementById("form-modulo");
  if (!form) return;

  const MAX = parseInt(form.dataset.max, 10) || 3;
  const grupo = document.getElementById("modulos");
  const temas = Array.from(form.querySelectorAll('input[name="tema"]'));
  const error = document.getElementById("error-modulo");
  const resumen = document.getElementById("prev-modulo");
  const cuenta = document.getElementById("prev-cuenta");
  const MENSAJE_MIN = "Debes seleccionar al menos un tema para continuar.";

  const marcados = () => temas.filter((t) => t.checked);

  function ocultarError() {
    error.hidden = true;
    grupo.classList.remove("invalid");
  }

  function mostrarError(texto) {
    error.textContent = texto;
    error.hidden = false;
    grupo.classList.remove("invalid");
    void grupo.offsetWidth; // reinicia la animación
    grupo.classList.add("invalid");
    grupo.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function actualizar() {
    const sel = marcados();
    const lleno = sel.length >= MAX;
    // Solo se puede elegir de una materia: al marcar un tema, las otras tarjetas se bloquean.
    // Dentro de la materia elegida, con el máximo alcanzado se bloquean las demás casillas.
    const card = sel.length ? sel[0].closest(".modulo-card") : null;
    temas.forEach((t) => {
      const otraMateria = card && t.closest(".modulo-card") !== card;
      t.disabled = !t.checked && (otraMateria || lleno);
      t.closest(".tema").classList.toggle("bloqueado", t.disabled);
    });
    form.querySelectorAll(".modulo-card").forEach((c) => c.classList.toggle("apagada", !!card && c !== card));
    resumen.textContent = sel.length
      ? sel.map((t) => t.dataset.titulo).join(" · ")
      : "Aún no has elegido ninguno";
    cuenta.textContent = sel.length + "/" + MAX;
    cuenta.classList.toggle("lleno", lleno);
    // contador por módulo y borde de las tarjetas que tienen algo marcado
    form.querySelectorAll(".modulo-card").forEach((card) => {
      const n = card.querySelectorAll('input[name="tema"]:checked').length;
      card.classList.toggle("con-seleccion", n > 0);
      card.querySelector(".contador-modulo").textContent = n ? n + " marcado" + (n > 1 ? "s" : "") : "";
    });
  }

  temas.forEach((t) =>
    t.addEventListener("change", () => {
      ocultarError();
      actualizar();
    })
  );

  form.addEventListener("submit", (e) => {
    const n = marcados().length;
    if (n < 1 || n > MAX) {
      e.preventDefault();
      mostrarError(n < 1 ? MENSAJE_MIN : "Puedes elegir máximo " + MAX + " temas.");
      return;
    }
    // Con temas elegidos: el libro se abre y, al terminar, se envía el formulario
    if (window.TransicionLibro) {
      e.preventDefault();
      window.TransicionLibro.abrir(() => form.submit());
    }
  });

  actualizar(); // por si el servidor devolvió temas ya elegidos
})();
