// Pantalla 2 de Personalizar Partida (CU02): elegir el módulo temático y comenzar la aventura.
//  - Paso 4: se elige un módulo (clic en la tarjeta; se puede cambiar antes de confirmar).
//  - Special Requirement: la hoja de personaje se actualiza en tiempo real.
//  - RN02: no se puede comenzar sin tema; se muestra un mensaje.
(function () {
  const form = document.getElementById("form-modulo");
  if (!form) return;

  const grupo = document.getElementById("modulos");
  const radios = Array.from(form.querySelectorAll('input[name="modulo"]'));
  const error = document.getElementById("error-modulo");
  const resumen = document.getElementById("prev-modulo");

  function ocultarError() {
    error.hidden = true;
    grupo.classList.remove("invalid");
  }

  function mostrarError() {
    error.hidden = false;
    grupo.classList.remove("invalid");
    void grupo.offsetWidth; // reinicia la animación
    grupo.classList.add("invalid");
    if (radios[0]) radios[0].focus({ preventScroll: true });
    grupo.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function actualizar() {
    const elegido = radios.find((r) => r.checked);
    resumen.textContent = elegido ? elegido.dataset.titulo : "Aún no has elegido uno";
  }

  radios.forEach((r) =>
    r.addEventListener("change", () => {
      ocultarError();
      actualizar();
    })
  );

  // Botón "i": cuántos temas incluye el módulo
  form.querySelectorAll(".info-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const extra = document.getElementById(btn.getAttribute("aria-controls"));
      const abierto = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!abierto));
      extra.hidden = abierto;
    });
  });

  form.addEventListener("submit", (e) => {
    if (!radios.some((r) => r.checked)) {
      e.preventDefault();
      mostrarError();
      return;
    }
    // Con módulo elegido: el libro se abre y, al terminar, se envía el formulario
    if (window.TransicionLibro) {
      e.preventDefault();
      window.TransicionLibro.abrir(() => form.submit());
    }
  });

  actualizar(); // por si el servidor devolvió un módulo ya elegido
})();
