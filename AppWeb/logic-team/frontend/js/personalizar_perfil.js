// Pantalla 1 de Personalizar Partida (CU02): elegir perfil / antecedente.
//  - Paso 3 y FA1: al elegir (o cambiar) una tarjeta se actualiza la selección y la vista previa.
//  - Special Requirement: la vista previa de atributos iniciales cambia en tiempo real.
//  - FE1 / RN03: no se puede continuar sin perfil; se muestra un mensaje y se vuelve al paso 3.
(function () {
  const form = document.getElementById("form-perfil");
  if (!form) return;

  const grupo = document.getElementById("perfiles");
  const radios = Array.from(form.querySelectorAll('input[name="perfil"]'));
  const error = document.getElementById("error-perfil");
  const vacio = document.getElementById("preview-vacio");
  const datos = document.getElementById("preview-datos");

  const NIVELES = { baja: 1, media: 2, alta: 3 };

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

  function pintarNivel(clave, nivel) {
    document.getElementById("prev-" + clave).textContent = nivel;
    document.getElementById("meter-" + clave).dataset.n = NIVELES[nivel] || 0;
  }

  function actualizar() {
    // (La tarjeta elegida se marca con CSS: input:checked + .perfil-card)
    // Vista previa
    const elegido = radios.find((r) => r.checked);
    if (!elegido) {
      vacio.hidden = false;
      datos.hidden = true;
      return;
    }
    const d = elegido.dataset;
    document.getElementById("prev-vidas").textContent = "❤️ " + d.vidas;
    document.getElementById("prev-xp").textContent = "⭐ " + d.xp + " XP";
    pintarNivel("teoria", d.teoria);
    pintarNivel("equipo", d.equipo);
    pintarNivel("inteligencia", d.inteligencia);
    vacio.hidden = true;
    datos.hidden = false;
  }

  radios.forEach((r) =>
    r.addEventListener("change", () => {
      ocultarError();
      actualizar();
    })
  );

  // Botón "i": muestra vida y XP iniciales dentro de la tarjeta
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
    }
  });

  actualizar(); // por si el servidor devolvió un perfil ya elegido
})();
