// Pantalla 2 de Personalizar Partida (CU02): elegir los temas y comenzar la aventura.
//  - Paso 4: se marcan los temas que se quieran, de cualquier materia (mínimo 1).
//  - Special Requirement: la hoja de personaje se actualiza en tiempo real.
//  - RN02: no se puede comenzar sin al menos un tema; se muestra un mensaje.
(function () {
  const form = document.getElementById("form-modulo");
  if (!form) return;

  const grupo = document.getElementById("modulos");
  const temas = Array.from(form.querySelectorAll('input[name="tema"]'));
  const error = document.getElementById("error-modulo");
  const resumen = document.getElementById("prev-modulo");
  const cuenta = document.getElementById("prev-cuenta");
  const MENSAJE_MIN = "Debes seleccionar al menos un tema para continuar.";
  const todos = document.getElementById("todos-temas");

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
    resumen.textContent = sel.length
      ? sel.map((t) => t.dataset.titulo).join(" · ")
      : "Aún no has elegido ninguno";
    cuenta.textContent = String(sel.length);
    // Botón "Seleccionar todos": si ya están todos marcados, sirve para quitarlos
    if (todos) {
      const completos = sel.length === temas.length;
      todos.textContent = completos ? "☐ Quitar todos" : "☑ Seleccionar todos";
      todos.setAttribute("aria-pressed", String(completos));
    }
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

  if (todos) {
    todos.addEventListener("click", () => {
      const marcar = marcados().length !== temas.length;
      temas.forEach((t) => { t.checked = marcar; });
      ocultarError();
      actualizar();
    });
  }

  form.addEventListener("submit", (e) => {
    if (marcados().length < 1) {
      e.preventDefault();
      mostrarError(MENSAJE_MIN);
      return;
    }
    // Con temas elegidos: el libro se acerca, se abre y su luz da paso a la partida (CU01)
    if (window.TransicionLibro) {
      e.preventDefault();
      window.TransicionLibro.abrir(() => form.submit());
    }
  });

  actualizar(); // por si el servidor devolvió temas ya elegidos
})();
