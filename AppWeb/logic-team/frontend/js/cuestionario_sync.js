// CU05 FE1 - Resultados del cuestionario pendientes de sincronizar (RF-60).
// Si se pierde la conexión, el resultado queda guardado en este dispositivo (localStorage) y se
// envía al historial cuando vuelve la conexión (evento "online") o en la siguiente visita al
// menú o al cuestionario. El servidor no lo guarda dos veces: el id viaja en el token firmado.
(function () {
  "use strict";

  const CLAVE = "logicteam.cuestionario.pendientes";
  const URL_RESULTADO = "/api/cuestionario/resultado/";
  let enCurso = null;

  function cookie(nombre) {
    const m = document.cookie.match(new RegExp(`(?:^|; )${nombre}=([^;]*)`));
    return m ? decodeURIComponent(m[1]) : "";
  }

  function pendientes() {
    try {
      const lista = JSON.parse(localStorage.getItem(CLAVE) || "[]");
      return Array.isArray(lista) ? lista : [];
    } catch (e) {
      return [];
    }
  }

  function guardar(lista) {
    try {
      if (lista.length) localStorage.setItem(CLAVE, JSON.stringify(lista));
      else localStorage.removeItem(CLAVE);
      return true;
    } catch (e) {
      return false; // almacenamiento bloqueado o lleno
    }
  }

  function agregar(item) {
    const lista = pendientes().filter((p) => p.cuestionario_id !== item.cuestionario_id);
    lista.push(item);
    return guardar(lista);
  }

  // Envía un resultado. red=true significa que no se pudo hablar con el servidor.
  async function enviar(item, pendiente) {
    let respuesta;
    try {
      respuesta = await fetch(URL_RESULTADO, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": cookie("csrftoken"),
        },
        body: JSON.stringify({
          token: item.token,
          respuestas: item.respuestas,
          fecha: item.fecha,
          pendiente: Boolean(pendiente),
        }),
      });
    } catch (e) {
      return { ok: false, red: true };
    }
    const datos = await respuesta.json().catch(() => ({}));
    return { ok: respuesta.ok, red: false, estado: respuesta.status, datos };
  }

  function avisar(detalle) {
    document.dispatchEvent(new CustomEvent("cu05:sincronizado", { detail: detalle }));
  }

  async function sincronizar() {
    if (enCurso) return enCurso;
    enCurso = (async () => {
      const enviados = [];
      const descartados = [];
      for (const item of pendientes()) {
        const r = await enviar(item, true);
        if (r.red || (r.estado && r.estado >= 500)) continue; // se reintenta después
        // Guardado (201), ya estaba (200) o rechazado para siempre (400/403): sale de la lista
        guardar(pendientes().filter((p) => p.cuestionario_id !== item.cuestionario_id));
        (r.ok ? enviados : descartados).push({ ...item, respuesta: r.datos });
      }
      const detalle = { enviados, descartados, restantes: pendientes().length };
      avisar(detalle);
      return detalle;
    })();
    try {
      return await enCurso;
    } finally {
      enCurso = null;
    }
  }

  window.CU05Sync = { pendientes, agregar, enviar, sincronizar };

  window.addEventListener("online", () => { sincronizar(); });
  if (pendientes().length) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => sincronizar());
    else sincronizar();
  }
})();
