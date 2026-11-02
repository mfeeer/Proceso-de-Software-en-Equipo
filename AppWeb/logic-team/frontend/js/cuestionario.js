// CU05 - Completar cuestionario de tecnicismos (modo «Cuestionario súbito»).
// El servidor arma y firma el cuestionario (pasos 4 a 6); aquí se dibuja la mesa de trabajo,
// una pregunta a la vez, y se guardan las respuestas en el dispositivo (pasos 7 a 9). Al terminar
// se muestra el resumen (paso 10) y se envía el resultado al historial (paso 11), que el servidor
// vuelve a calificar con el token firmado.
//   RN07  durante el cuestionario no se dice si la respuesta fue correcta: la elegida se marca
//         en dorado y se pasa a la siguiente
//   FA1   409 al generar -> aviso con el avance y botón «Ir a Historia narrativa»
//   FA3   «Salir» pide confirmación y descarta las respuestas
//   FA4   «Jugar otra vez» pide un cuestionario nuevo
//   FE1   sin conexión se puede terminar; el resultado queda pendiente (js/cuestionario_sync.js)
(function () {
  "use strict";

  const mesa = document.getElementById("c5-mesa");
  if (!mesa) return;
  const URL = {
    generar: mesa.dataset.generar,
    menu: mesa.dataset.menu,
    historia: mesa.dataset.historia,
  };
  const CLAVE_ACTUAL = "logicteam.cuestionario.actual";
  const LETRAS = "ABCD";
  const SELLO_TIPO = { A: "📖 Tipo A · Definición", B: "🧭 Tipo B · Aplicación", C: "✍ Tipo C · Completar" };
  const sync = window.CU05Sync;

  let actual = null; // { datos: respuesta de /generar/, respuestas: [índices] }
  let bloqueado = false; // evita doble clic mientras se pasa a la siguiente pregunta
  let dialogo = null;

  // ------------------------------------------------------------ utilidades
  function el(etiqueta, clase, texto) {
    const nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto !== undefined && texto !== null) nodo.textContent = texto;
    return nodo;
  }

  function con(padre, ...hijos) {
    hijos.forEach((h) => { if (h) padre.appendChild(h); });
    return padre;
  }

  function vaciar() { while (mesa.firstChild) mesa.removeChild(mesa.firstChild); dialogo = null; }

  function boton(texto, clase, alPulsar) {
    const b = el("button", clase, texto);
    b.type = "button";
    b.addEventListener("click", alPulsar);
    return b;
  }

  function enlace(texto, clase, href) {
    const a = el("a", clase, texto);
    a.href = href;
    return a;
  }

  function cookie(nombre) {
    const m = document.cookie.match(new RegExp(`(?:^|; )${nombre}=([^;]*)`));
    return m ? decodeURIComponent(m[1]) : "";
  }

  function sinMovimiento() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.dataset.movimiento === "reducido";
  }

  const pausa = (ms) => new Promise((r) => setTimeout(r, sinMovimiento() ? 0 : ms));

  function guardarActual() {
    try { localStorage.setItem(CLAVE_ACTUAL, JSON.stringify(actual)); } catch (e) { /* bloqueado */ }
  }

  function leerActual() {
    try {
      const a = JSON.parse(localStorage.getItem(CLAVE_ACTUAL));
      const ok = a && a.datos && a.datos.token && Array.isArray(a.datos.preguntas) &&
        Array.isArray(a.respuestas) && a.respuestas.length < a.datos.preguntas.length;
      return ok ? a : null;
    } catch (e) {
      return null;
    }
  }

  function borrarActual() {
    try { localStorage.removeItem(CLAVE_ACTUAL); } catch (e) { /* bloqueado */ }
  }

  function aviso(tipo, icono, titulo, texto) {
    const caja = el("div", `tl-aviso ${tipo} c5-aviso`);
    caja.setAttribute("role", tipo === "mal" ? "alert" : "status");
    const cuerpo = con(el("div"), el("b", null, titulo));
    cuerpo.appendChild(document.createTextNode(texto));
    return con(caja, el("span", "ico", icono), cuerpo);
  }

  function barra(conSalir, derecha) {
    return con(
      el("div", "tl-barra"),
      conSalir ? boton("✕ Salir", "tl-salir", pedirSalida) : null,
      con(el("div", "tl-titulo"), el("small", null, "MODO DE JUEGO"), el("b", null, "Cuestionario súbito")),
      con(el("div", "tl-derecha"), derecha)
    );
  }

  // ------------------------------------------------------------ pasos 4 a 6 y FA1
  async function generar() {
    vaciar();
    con(mesa, barra(false, null), el("p", "c5-cargando", "Preparando tu cuestionario…"));
    let respuesta;
    try {
      respuesta = await fetch(URL.generar, {
        method: "POST",
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-CSRFToken": cookie("csrftoken") },
      });
    } catch (e) {
      pintarError("No se pudo conectar con el servidor para preparar el cuestionario. Revisa tu conexión e inténtalo de nuevo.");
      return;
    }
    const datos = await respuesta.json().catch(() => ({}));
    if (respuesta.status === 409 && datos.error === "insuficientes") {
      pintarBloqueado(datos);
      return;
    }
    if (!respuesta.ok || !Array.isArray(datos.preguntas)) {
      pintarError(datos.error || "No se pudo preparar el cuestionario.");
      return;
    }
    actual = { datos, respuestas: [] };
    guardarActual();
    pintarPregunta();
  }

  function pintarError(mensaje) {
    vaciar();
    con(
      mesa,
      barra(false, null),
      aviso("mal", "!", "No se pudo continuar", mensaje),
      con(el("div", "c5-acciones"), enlace("⬅ Volver al menú", "book-btn", URL.menu), boton("↻ Reintentar", "book-btn go", generar))
    );
  }

  function pintarBloqueado(datos) {
    vaciar();
    const medidor = el("div", "c5-meter");
    medidor.setAttribute("aria-hidden", "true");
    for (let i = 0; i < datos.necesarios; i += 1) con(medidor, el("span", i < datos.registrados ? "on" : ""));
    const ventana = con(
      el("div", "tl-pergamino tl-ventana"),
      el("h2", null, "Cuestionario bloqueado"),
      el("p", null, datos.mensaje),
      medidor,
      el("p", "c5-ayuda", "Los tecnicismos aparecen resaltados en los eventos de la historia."),
      con(el("div", "btn-row"), enlace("Volver al menú", "book-btn", URL.menu), enlace("Ir a Historia narrativa ➔", "book-btn go", URL.historia))
    );
    ventana.setAttribute("role", "alertdialog");
    ventana.setAttribute("aria-label", "Cuestionario bloqueado");
    con(mesa, barra(false, null), con(el("div", "tl-velo"), ventana));
    ventana.querySelector("a.go").focus();
  }

  // ------------------------------------------------------------ pasos 7 a 9
  function avance(numero, total) {
    const puntos = el("ol", "c5-puntos");
    puntos.setAttribute("aria-hidden", "true");
    for (let i = 1; i <= total; i += 1) con(puntos, el("li", i < numero ? "hecha" : i === numero ? "actual" : ""));
    const chip = el("span", "tl-chip", `${numero} / ${total}`);
    chip.setAttribute("aria-label", `Pregunta ${numero} de ${total}`);
    return con(el("div", "c5-avance"), puntos, chip);
  }

  // Tipo C: la palabra faltante se dibuja como un hueco
  function textoConHueco(texto) {
    const p = el("p", "texto");
    const partes = texto.split("_____");
    partes.forEach((parte, i) => {
      p.appendChild(document.createTextNode(parte));
      if (i < partes.length - 1) {
        const hueco = el("span", "c5-hueco", "?");
        hueco.setAttribute("aria-label", "palabra faltante");
        p.appendChild(hueco);
      }
    });
    return p;
  }

  function pintarPregunta() {
    vaciar();
    bloqueado = false;
    const { preguntas } = actual.datos;
    const indice = actual.respuestas.length;
    const p = preguntas[indice];
    const total = preguntas.length;

    const tarjeta = el("div", "tl-pergamino c5-pregunta");
    tarjeta.tabIndex = -1;
    tarjeta.setAttribute("aria-live", "polite");
    con(
      tarjeta,
      el("span", "stamp pt-stamp-oro", SELLO_TIPO[p.tipo] || p.tipo_nombre),
      p.nombre ? el("span", "nombre", p.nombre) : null,
      p.tipo === "C" ? textoConHueco(p.texto) : el("p", "texto", p.texto),
      el("p", "pide", p.pide)
    );

    const opciones = el("div", `c5-opciones${p.tipo === "B" ? " renglones" : ""}`);
    const botones = p.opciones.map((texto, i) => {
      const b = boton("", "c5-op", () => responder(i, b, botones));
      con(b, el("span", "letra", LETRAS[i]), document.createTextNode(texto));
      b.setAttribute("aria-label", `Opción ${LETRAS[i]}: ${texto}`);
      return b;
    });
    botones.forEach((b) => con(opciones, b));

    con(
      mesa,
      barra(true, avance(indice + 1, total)),
      tarjeta,
      opciones,
      el("p", "c5-pista", "Toca una opción para responder · no verás si acertaste hasta el final")
    );
    tarjeta.focus({ preventScroll: true });
  }

  async function responder(indice, b, botones) {
    if (bloqueado || dialogo) return;
    bloqueado = true;
    botones.forEach((x) => { x.disabled = true; });
    b.classList.add("elegida"); // RN07: dorado, sin decir si es correcta
    b.setAttribute("aria-pressed", "true");
    actual.respuestas.push(indice);
    guardarActual(); // las respuestas se guardan localmente (FE1)
    await pausa(450);
    if (actual.respuestas.length < actual.datos.preguntas.length) pintarPregunta();
    else terminar();
  }

  // Atajo de teclado: 1-4 o A-D eligen una opción
  document.addEventListener("keydown", (ev) => {
    if (dialogo || bloqueado || ev.altKey || ev.ctrlKey || ev.metaKey) return;
    const tecla = ev.key.toUpperCase();
    const i = "1234".includes(tecla) ? Number(tecla) - 1 : LETRAS.indexOf(tecla);
    if (i < 0 || tecla.length !== 1) return;
    const b = mesa.querySelectorAll(".c5-op")[i];
    if (b && !b.disabled) b.click();
  });

  // ------------------------------------------------------------ FA3
  function pedirSalida() {
    if (dialogo) return;
    const seguir = boton("Seguir respondiendo", "book-btn", cerrarDialogo);
    const salir = boton("Sí, salir", "book-btn go", () => {
      borrarActual(); // no se guarda ningún resultado
      window.location.href = URL.menu;
    });
    const ventana = con(
      el("div", "tl-pergamino tl-ventana"),
      el("h2", null, "¿Salir del cuestionario?"),
      el("p", null, "Se perderá tu progreso: tus respuestas no se guardarán y volverás al menú de modos."),
      con(el("div", "btn-row"), seguir, salir)
    );
    ventana.setAttribute("role", "alertdialog");
    ventana.setAttribute("aria-modal", "true");
    ventana.setAttribute("aria-label", "¿Salir del cuestionario?");
    dialogo = con(el("div", "tl-velo"), ventana);
    dialogo.addEventListener("click", (ev) => { if (ev.target === dialogo) cerrarDialogo(); });
    mesa.appendChild(dialogo);
    seguir.focus();
  }

  function cerrarDialogo() {
    if (!dialogo) return;
    dialogo.remove();
    dialogo = null;
    const tarjeta = mesa.querySelector(".c5-pregunta");
    if (tarjeta) tarjeta.focus({ preventScroll: true });
  }

  document.addEventListener("keydown", (ev) => {
    if (!dialogo) return;
    if (ev.key === "Escape") cerrarDialogo();
    if (ev.key === "Tab") {
      const enfocables = [...dialogo.querySelectorAll("button")];
      const primero = enfocables[0];
      const ultimo = enfocables[enfocables.length - 1];
      if (ev.shiftKey && document.activeElement === primero) { ev.preventDefault(); ultimo.focus(); }
      else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primero.focus(); }
    }
  });

  // ------------------------------------------------------------ pasos 10 a 13
  function calificar(datos, respuestas) {
    const errores = [];
    let aciertos = 0;
    datos.preguntas.forEach((p, i) => {
      if (respuestas[i] === p.correcta) aciertos += 1;
      else errores.push({ p, elegida: p.opciones[respuestas[i]], correcta: p.opciones[p.correcta] });
    });
    const total = datos.preguntas.length;
    // RN06: aciertos / total × 100 (el servidor lo vuelve a calcular al guardar)
    const puntaje = total ? Math.floor((aciertos * 200 + total) / (2 * total)) : 0;
    return { aciertos, total, puntaje, errores };
  }

  async function terminar() {
    const datos = actual.datos;
    const respuestas = actual.respuestas.slice();
    const fecha = new Date();
    const resultado = calificar(datos, respuestas);
    borrarActual();
    const item = { cuestionario_id: datos.cuestionario_id, token: datos.token, respuestas, fecha: fecha.toISOString() };

    let estado = "guardado";
    let mensaje = "";
    const r = sync ? await sync.enviar(item, false) : { ok: false, red: true };
    if (r.ok) {
      if (r.datos && typeof r.datos.puntaje === "number") resultado.puntaje = r.datos.puntaje;
    } else if (r.red || (r.estado && r.estado >= 500)) {
      estado = sync && sync.agregar(item) ? "pendiente" : "perdido"; // FE1
    } else {
      estado = "rechazado";
      mensaje = (r.datos && r.datos.error) || "El servidor no aceptó el resultado.";
    }
    pintarResumen(resultado, fecha, estado, mensaje, datos.cuestionario_id);
  }

  function anillo(puntaje) {
    const caja = el("div", "c5-anillo");
    caja.style.background = `conic-gradient(#3f6b2a 0 ${puntaje}%, rgba(142, 42, 42, 0.75) ${puntaje}% 100%)`;
    caja.setAttribute("role", "img");
    caja.setAttribute("aria-label", `Puntaje ${puntaje} de 100`);
    return con(caja, con(el("div"), el("b", null, String(puntaje)), el("span", null, "puntaje")));
  }

  function sello(estado) {
    if (estado === "guardado") return el("span", "stamp pt-stamp-oro c5-sello", "✔ Guardado en tu historial");
    if (estado === "pendiente") return el("span", "stamp pt-stamp-mal c5-sello", "⏳ Pendiente de sincronizar");
    return el("span", "stamp pt-stamp-mal c5-sello", "✘ No se guardó");
  }

  function pintarResumen(r, fecha, estado, mensaje, cuestionarioId) {
    vaciar();
    const formato = new Intl.DateTimeFormat("es-MX", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    const marcaSello = sello(estado);
    const marcador = con(
      el("div", "tl-pergamino c5-marcador"),
      el("h2", null, "¡Terminaste!"),
      anillo(r.puntaje),
      con(
        el("div", "c5-cuenta"),
        con(el("div", "ok"), el("b", null, String(r.aciertos)), el("span", null, r.aciertos === 1 ? "acierto" : "aciertos")),
        con(el("div", "mal"), el("b", null, String(r.errores.length)), el("span", null, r.errores.length === 1 ? "error" : "errores"))
      ),
      el("p", "c5-fecha", formato.format(fecha)),
      marcaSello
    );

    const repaso = el("div", "tl-pergamino c5-repaso");
    if (r.errores.length) {
      con(repaso, el("h3", null, r.errores.length === 1 ? "Repasa tu error" : `Repasa tus ${r.errores.length} errores`));
      const lista = el("ol", "c5-errores");
      r.errores.forEach(({ p, elegida, correcta }) => {
        const tuya = el("span", "tuya", "✘ ");
        con(tuya, el("s", null, elegida));
        con(
          lista,
          con(
            el("li", "c5-error"),
            el("strong", null, p.tecnicismo),
            el("span", "tipo", p.tipo_nombre),
            con(el("div", "fila"), tuya, el("span", "buena", `✔ ${correcta}`)),
            el("span", "exp", p.explicacion)
          )
        );
      });
      con(repaso, lista);
    } else {
      con(repaso, el("h3", null, "¡Sin errores!"), el("p", "c5-sin-errores", "Respondiste bien todas las preguntas. Dominas los tecnicismos que has descubierto."));
    }

    let avisoRed = null;
    if (estado === "pendiente") {
      avisoRed = aviso("info c5-sin-red", "📶", "Sin conexión · pendiente de sincronizar", "Tu resultado quedó guardado en este dispositivo y se enviará a tu historial cuando vuelva la conexión.");
    } else if (estado === "perdido") {
      avisoRed = aviso("mal", "!", "No se pudo guardar el resultado", "No hay conexión y este navegador no permite guardar datos en el dispositivo.");
    } else if (estado === "rechazado") {
      avisoRed = aviso("mal", "!", "No se pudo guardar el resultado", mensaje);
    }

    const total = actual.datos.preguntas.length;
    const chip = el("span", "tl-chip oro", `${total} / ${total}`);
    const volver = enlace("⬅ Volver al menú", "book-btn", URL.menu);
    con(
      mesa,
      barra(false, chip),
      avisoRed,
      con(el("div", "c5-resumen"), marcador, repaso),
      con(el("div", "c5-acciones"), volver, boton("↻ Jugar otra vez", "book-btn go", generar)) // FA4
    );
    volver.focus({ preventScroll: true });

    // FE1: si el resultado pendiente se sincroniza con la pantalla abierta, se actualiza el sello
    if (estado === "pendiente") {
      const alSincronizar = (ev) => {
        if (!ev.detail.enviados.some((x) => x.cuestionario_id === cuestionarioId)) return;
        marcaSello.replaceWith(sello("guardado"));
        if (avisoRed) avisoRed.replaceWith(aviso("ok", "✔", "Resultado sincronizado", "Volvió la conexión y tu resultado ya está en tu historial."));
        document.removeEventListener("cu05:sincronizado", alSincronizar);
      };
      document.addEventListener("cu05:sincronizado", alSincronizar);
    }
  }

  // ------------------------------------------------------------ inicio
  // Si se recargó la página a mitad del cuestionario, se retoma en la misma pregunta.
  actual = leerActual();
  if (actual) pintarPregunta();
  else generar();
})();
