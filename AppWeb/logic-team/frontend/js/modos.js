// CU05 pasos 1 a 3 - Menú de modos de juego.
// FA1: si el cuestionario está bloqueado, al elegirlo se abre el aviso con el avance (RN03).
// FE1: muestra cuántos resultados siguen pendientes de sincronizar.
(function () {
  "use strict";

  // ------------------------------------------------------------ FA1
  const velo = document.getElementById("c5-bloqueado");
  const boton = document.getElementById("btn-cuestionario");
  if (velo && boton && boton.tagName === "BUTTON") {
    const cerrarBtn = document.getElementById("c5-cerrar");
    const abrir = () => {
      velo.hidden = false;
      cerrarBtn.focus();
    };
    const cerrar = () => {
      velo.hidden = true;
      boton.focus();
    };
    boton.addEventListener("click", abrir);
    cerrarBtn.addEventListener("click", cerrar);
    velo.addEventListener("click", (ev) => { if (ev.target === velo) cerrar(); });
    document.addEventListener("keydown", (ev) => {
      if (velo.hidden) return;
      if (ev.key === "Escape") cerrar();
      if (ev.key === "Tab") {
        // El foco se queda dentro del aviso mientras está abierto
        const enfocables = [...velo.querySelectorAll("button, a[href]")];
        const primero = enfocables[0];
        const ultimo = enfocables[enfocables.length - 1];
        if (ev.shiftKey && document.activeElement === primero) { ev.preventDefault(); ultimo.focus(); }
        else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primero.focus(); }
      }
    });
  }

  // ------------------------------------------------------------ FE1
  const aviso = document.getElementById("c5-pendientes");
  function pintarPendientes() {
    if (!aviso || !window.CU05Sync) return;
    const n = window.CU05Sync.pendientes().length;
    aviso.hidden = n === 0;
    if (!n) return;
    aviso.textContent = "";
    const ico = document.createElement("span");
    ico.className = "ico";
    ico.textContent = "📶";
    const cuerpo = document.createElement("div");
    const titulo = document.createElement("b");
    titulo.textContent = "Pendiente de sincronizar";
    cuerpo.append(
      titulo,
      n === 1
        ? "Tienes 1 resultado del cuestionario guardado en este dispositivo. Se enviará a tu historial cuando vuelva la conexión."
        : `Tienes ${n} resultados del cuestionario guardados en este dispositivo. Se enviarán a tu historial cuando vuelva la conexión.`
    );
    aviso.append(ico, cuerpo);
  }
  document.addEventListener("cu05:sincronizado", pintarPendientes);
  pintarPendientes();
})();
