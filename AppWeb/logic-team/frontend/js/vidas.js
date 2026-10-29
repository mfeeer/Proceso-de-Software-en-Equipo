// CU06 - Conseguir vidas. Minijuego de verdadero o falso con tarjetas deslizables.
// Diseño: SDS (WP.12) 1.3.6 y 3.3.1, Figura 9. Vive encima del libro de la partida (CU01):
//   partida.js  -> CU06Vidas.conectar({ llamar, alActualizar }) -> { boton, sincronizar, abrir }
//   boton(estado)        botón permanente de la hoja de personaje (RN-02, FA3, FE4)
//   sincronizar(estado)  después de pintar el libro: retoma la ronda o muestra la sugerencia (FA1)
//   abrir(estado, modo)  "instrucciones" | "ronda" | "resultado" | "sugerencia"
//   alActualizar(estado) el libro se repinta al volver a la historia
// El servidor elige las afirmaciones y evalúa cada respuesta; todas las rutas responden con el
// estado de la partida y aquí se dibuja estado.vidas.ronda. Estilos en css/vidas.css (cv-*).
(function () {
  "use strict";

  const VACIO = "♡";
  const LLENO = "❤";

  // ------------------------------------------------------------ utilidades
  function el(etiqueta, clase, texto) {
    const nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto !== undefined && texto !== null) nodo.textContent = texto;
    return nodo;
  }

  function con(padre, ...hijos) {
    hijos.forEach((hijo) => { if (hijo) padre.appendChild(hijo); });
    return padre;
  }

  function boton(clase, texto, alHacerClic) {
    const b = el("button", clase, texto);
    b.type = "button";
    if (alHacerClic) b.addEventListener("click", alHacerClic);
    return b;
  }

  function sinMovimiento() {
    return (typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches) ||
      document.documentElement.dataset.movimiento === "reducido";
  }

  const esperar = (ms) => new Promise((res) => setTimeout(res, sinMovimiento() ? 0 : ms));

  // ------------------------------------------------------------ estado del módulo
  let llamar = null;        // de partida.js: llamar(ruta, cuerpo) -> Promise<estado>
  let alActualizar = null;  // de partida.js: vuelve a dibujar el libro con un estado
  let estado = null;        // último estado de la partida (incluye estado.vidas)

  let capa = null;          // .cv-capa abierta (null = minijuego cerrado)
  let hoja = null;          // .cv-hoja dentro de la capa
  let cuerpo = null;        // .cv-cuerpo: lo que cambia entre pantallas
  let corazones = null;     // contador de vidas de la cabecera
  let pantalla = "";        // instrucciones | tarjeta | retro | resultado | sugerencia
  let ocupado = false;      // hay una petición en curso
  let confirmar = null;     // diálogo de FE2 abierto
  let enfoqueAntes = null;
  let carta = null;
  let botonesRespuesta = [];

  const ronda = () => (estado && estado.vidas ? estado.vidas.ronda : null);

  // ------------------------------------------------------------ botón permanente
  // Pasos 1-2 (RN-02), FA3 y FE4: siempre visible en la hoja de personaje.
  function botonPermanente(e) {
    estado = e;
    const disponible = Boolean(e.vidas && e.vidas.disponible);
    let texto = "❤️ Conseguir vidas";
    let ayuda = "Recupera una vida respondiendo afirmaciones de verdadero o falso.";
    let clase = "cv-boton";
    if (!disponible && e.hp >= e.hp_max) {
      texto = "❤️ Vidas completas";
      ayuda = "Disponible cuando te falte una vida.";
    } else if (!disponible) {
      texto = "❤️ Sin vidas";
      ayuda = "Con 0 vidas el minijuego ya no está disponible.";
      clase += " sin-vidas";
    }
    const b = boton(clase, texto, () => abrir(estado, "instrucciones"));
    b.id = "cv-boton";
    b.disabled = !disponible;
    b.title = ayuda;
    return b;
  }

  // Después de pintar el libro: retoma una ronda (recarga de página) o muestra la sugerencia
  // cuando el servidor la marcó y el libro está en un evento (FA1).
  function sincronizar(e) {
    estado = e;
    if (capa || !e.vidas || e.fase === "fin") return;
    const r = e.vidas.ronda;
    if (r) abrir(e, r.terminada ? "resultado" : "ronda");
    else if (e.vidas.sugerir && e.fase === "evento") abrir(e, "sugerencia");
  }

  // ------------------------------------------------------------ capa y cabecera
  function pintarCorazones(nuevo) {
    if (!corazones) return;
    while (corazones.firstChild) corazones.removeChild(corazones.firstChild);
    for (let i = 0; i < estado.hp_max; i++) {
      const lleno = i < estado.hp;
      const clase = "cv-corazon" + (lleno ? " lleno" : "") + (nuevo && i === estado.hp - 1 ? " nuevo" : "");
      corazones.appendChild(el("span", clase, lleno ? LLENO : VACIO));
    }
    corazones.setAttribute("aria-label", `Vidas: ${estado.hp} de ${estado.hp_max}`);
  }

  function crearCapa(sugerencia) {
    capa = el("div", "cv-capa" + (sugerencia ? " cv-capa-sugerencia" : ""));
    hoja = el("section", "cv-hoja");
    hoja.setAttribute("role", "dialog");
    hoja.setAttribute("aria-modal", "true");
    hoja.setAttribute("aria-labelledby", "cv-titulo");
    if (!sugerencia) {
      corazones = el("div", "cv-corazones");
      corazones.setAttribute("role", "img");
      con(
        hoja,
        con(
          el("header", "cv-cabecera"),
          con(el("div", "cv-marca"), el("span", "cv-marca-k", "MINIJUEGO"), el("span", "cv-marca-v", "Conseguir vidas")),
          con(el("div", "cv-cab-centro"), corazones),
          boton("cv-salir", "Salir ✕", salir)
        )
      );
      pintarCorazones(false);
    }
    cuerpo = el("div", "cv-cuerpo");
    con(document.body, con(capa, con(hoja, cuerpo)));
    document.body.classList.add("cv-abierto");
    document.addEventListener("keydown", teclado, true);
    requestAnimationFrame(() => capa && capa.classList.add("visible"));
  }

  function quitarCapa() {
    if (!capa) return null;
    const vieja = capa;
    document.removeEventListener("keydown", teclado, true);
    document.body.classList.remove("cv-abierto");
    capa = hoja = cuerpo = corazones = confirmar = carta = null;
    pantalla = "";
    ocupado = false;
    return vieja;
  }

  function abrir(e, modo) {
    if (e) estado = e;
    if (!llamar || !estado) return;
    if (capa) {
      // De la sugerencia a las instrucciones: cambia a la ventana con cabecera
      const vieja = quitarCapa();
      vieja.remove();
    } else {
      enfoqueAntes = document.activeElement;
    }
    crearCapa(modo === "sugerencia");
    if (modo === "sugerencia") pintarSugerencia();
    else if (modo === "ronda") pintarTarjeta();
    else if (modo === "resultado") pintarResultado(false);
    else pintarInstrucciones();
  }

  // Cierra la ventana; con un estado nuevo, el libro se repinta (alActualizar).
  async function cerrar(nuevoEstado) {
    const vieja = quitarCapa();
    if (!vieja) return;
    vieja.classList.remove("visible");
    await esperar(250);
    vieja.remove();
    if (nuevoEstado && alActualizar) alActualizar(nuevoEstado);
    const destino = document.getElementById("cv-boton");
    const foco = destino && !destino.disabled ? destino : enfoqueAntes;
    if (foco && document.contains(foco)) foco.focus({ preventScroll: true });
  }

  function nuevaPantalla(nombre) {
    pantalla = nombre;
    while (cuerpo.firstChild) cuerpo.removeChild(cuerpo.firstChild);
  }

  function enfocar(nodo) {
    if (nodo) requestAnimationFrame(() => nodo.focus({ preventScroll: true }));
  }

  function avisar(mensaje) {
    if (!cuerpo) return;
    let aviso = cuerpo.querySelector(".cv-aviso");
    if (!aviso) {
      aviso = el("p", "cv-aviso");
      aviso.setAttribute("role", "alert");
      cuerpo.insertBefore(aviso, cuerpo.firstChild);
    }
    aviso.textContent = mensaje;
  }

  // Llama a la API y guarda el estado; si falla, avisa dentro de la ventana y devuelve null.
  async function pedir(ruta, cuerpoJson) {
    if (ocupado) return null;
    ocupado = true;
    try {
      estado = await llamar(ruta, cuerpoJson || {});
      return estado;
    } catch (err) {
      avisar(err.message);
      return null;
    } finally {
      ocupado = false;
    }
  }

  // ------------------------------------------------------------ FA1: sugerencia
  function pintarSugerencia() {
    nuevaPantalla("sugerencia");
    const titulo = el("h2", "cv-titulo", "¡Puedes recuperar una vida!");
    titulo.id = "cv-titulo";
    const ir = boton("book-btn go", "Conseguir vida", () => descartarSugerencia(true));
    con(
      cuerpo,
      el("div", "cv-medalla ok", LLENO),
      titulo,
      el("p", "cv-texto", "Responde preguntas de verdadero o falso para conseguirla."),
      con(el("div", "btn-row cv-botones"), boton("book-btn", "Ahora no", () => descartarSugerencia(false)), ir)
    );
    enfocar(ir);
  }

  // En ambos casos el conteo de eventos reinicia; "Conseguir vida" sigue en el paso 4.
  async function descartarSugerencia(conseguir) {
    const nuevo = await pedir("vidas/sugerencia/");
    if (!nuevo) return;
    if (conseguir) abrir(nuevo, "instrucciones");
    else cerrar(nuevo);
  }

  // ------------------------------------------------------------ paso 4: instrucciones
  function pintarInstrucciones() {
    nuevaPantalla("instrucciones");
    const v = estado.vidas;
    const titulo = el("h2", "cv-titulo", "Recupera una vida");
    titulo.id = "cv-titulo";
    const guia = con(
      el("div", "cv-guia"),
      con(el("div", "cv-guia-lado falso"), el("span", "cv-flecha", "←"), el("b", null, "FALSO")),
      con(el("div", "cv-guia-carta"), el("span", null, "¿?")),
      con(el("div", "cv-guia-lado verdadero"), el("b", null, "VERDADERO"), el("span", "cv-flecha", "→"))
    );
    guia.setAttribute("aria-hidden", "true");
    const comenzarBtn = boton("book-btn go", "Comenzar ➔", comenzar);
    con(
      cuerpo,
      titulo,
      el("p", "cv-texto", "Desliza a la izquierda si la afirmación es FALSA y a la derecha si es VERDADERA."),
      guia,
      el("p", "cv-regla", `Son ${v.preguntas_por_ronda} afirmaciones. Acierta al menos ${v.aciertos_minimos} para ganar 1 vida. También puedes usar los botones o las flechas ← → del teclado.`),
      con(el("div", "btn-row cv-botones"), boton("book-btn", "Volver a la historia", () => cerrar()), comenzarBtn)
    );
    enfocar(comenzarBtn);
  }

  // Paso 5: el servidor crea la ronda (o devuelve la que estaba en juego).
  async function comenzar() {
    if (await pedir("vidas/iniciar/")) pintarTarjeta();
  }

  // ------------------------------------------------------------ progreso
  function progreso(numero) {
    const r = ronda();
    const puntos = el("ol", "cv-puntos");
    puntos.setAttribute("aria-hidden", "true");
    for (let i = 0; i < r.total; i++) {
      let clase = "cv-punto";
      if (i < r.resultados.length) clase += r.resultados[i] ? " bien" : " mal";
      else if (i === r.resultados.length && pantalla === "tarjeta") clase += " actual";
      puntos.appendChild(el("li", clase));
    }
    return con(
      el("div", "cv-progreso"),
      el("span", "cv-progreso-k", `Afirmación ${numero} de ${r.total}`),
      puntos,
      el("span", "cv-progreso-v", `✔ ${r.aciertos}`)
    );
  }

  // ------------------------------------------------------------ pasos 6-7: tarjeta
  function pintarTarjeta() {
    const r = ronda();
    if (!r || !r.pregunta) return;
    nuevaPantalla("tarjeta");
    const p = r.pregunta;
    carta = el("div", "cv-carta");
    carta.tabIndex = 0;
    carta.setAttribute("role", "group");
    carta.setAttribute("aria-roledescription", "tarjeta");
    carta.setAttribute("aria-label", `Afirmación: ${p.afirmacion}. Desliza o usa las flechas: izquierda falso, derecha verdadero.`);
    const texto = el("p", "cv-carta-texto", p.afirmacion);
    texto.id = "cv-titulo";
    const etiquetas = [el("span", "cv-etiqueta falso", "FALSO"), el("span", "cv-etiqueta verdadero", "VERDADERO")];
    etiquetas.forEach((n) => n.setAttribute("aria-hidden", "true"));
    con(carta, ...etiquetas, el("p", "cv-carta-tema", p.tema), texto, el("p", "cv-carta-pista", "← desliza →"));
    const mazo = con(el("div", "cv-mazo"), el("div", "cv-fondo dos"), el("div", "cv-fondo uno"), carta);

    const falso = boton("book-btn cv-falso", "← Falso", () => responder(false));
    const verdadero = boton("book-btn cv-verdadero", "Verdadero →", () => responder(true));
    botonesRespuesta = [falso, verdadero];

    con(cuerpo, progreso(r.numero), mazo, con(el("div", "cv-respuestas"), falso, verdadero));
    arrastre(carta);
    enfocar(carta);
  }

  // Deslizar con mouse, dedo o lápiz (Pointer Events). Umbral: 30% del ancho de la tarjeta,
  // máximo 120 px. Si el gesto no llega, la tarjeta regresa sin llamar al servidor (FE3).
  function arrastre(nodo) {
    let inicio = null;
    let dx = 0;
    const umbral = () => Math.min(120, nodo.offsetWidth * 0.3);

    function inclinar(x) {
      const u = umbral();
      nodo.style.transform = `translateX(${x}px) rotate(${x / 18}deg)`;
      nodo.style.setProperty("--cv-verdadero", Math.max(0, Math.min(1, x / u)));
      nodo.style.setProperty("--cv-falso", Math.max(0, Math.min(1, -x / u)));
      nodo.classList.toggle("lista-verdadero", x >= u);
      nodo.classList.toggle("lista-falso", x <= -u);
    }

    function soltar(cancelado) {
      if (inicio === null) return;
      inicio = null;
      nodo.classList.remove("arrastrando");
      if (!cancelado && Math.abs(dx) >= umbral()) {
        responder(dx > 0);
        return;
      }
      regresar(nodo, !cancelado && Math.abs(dx) > 6);
    }

    nodo.addEventListener("pointerdown", (ev) => {
      if (ocupado || pantalla !== "tarjeta" || (ev.pointerType === "mouse" && ev.button !== 0)) return;
      inicio = ev.clientX;
      dx = 0;
      const pista = nodo.parentNode && nodo.parentNode.querySelector(".cv-regresa");
      if (pista) pista.remove();
      nodo.classList.remove("regresa");
      nodo.classList.add("arrastrando");
      try { nodo.setPointerCapture(ev.pointerId); } catch (err) { /* sin captura: se sigue igual */ }
    });
    nodo.addEventListener("pointermove", (ev) => {
      if (inicio === null) return;
      dx = ev.clientX - inicio;
      inclinar(dx);
    });
    nodo.addEventListener("pointerup", () => soltar(false));
    nodo.addEventListener("pointercancel", () => soltar(true));
    nodo.addEventListener("lostpointercapture", () => soltar(true));
  }

  function regresar(nodo, avisarGesto) {
    nodo.classList.add("regresa");
    nodo.classList.remove("lista-verdadero", "lista-falso");
    nodo.style.transform = "";
    nodo.style.setProperty("--cv-verdadero", 0);
    nodo.style.setProperty("--cv-falso", 0);
    if (!avisarGesto) return;
    const mazo = nodo.parentNode;
    if (!mazo || mazo.querySelector(".cv-regresa")) return;
    const pista = el("span", "cv-regresa", "↩ Desliza más para responder");
    pista.setAttribute("role", "status");
    mazo.appendChild(pista);
    setTimeout(() => pista.remove(), 1800);
  }

  // ------------------------------------------------------------ paso 8: respuesta
  async function responder(respuesta) {
    if (ocupado || pantalla !== "tarjeta" || !carta) return;
    botonesRespuesta.forEach((b) => { b.disabled = true; });
    const nodo = carta;
    // La tarjeta sale volando hacia el lado elegido mientras el servidor evalúa
    nodo.classList.remove("arrastrando", "regresa");
    nodo.classList.add("vuela", respuesta ? "lista-verdadero" : "lista-falso");
    nodo.style.setProperty(respuesta ? "--cv-verdadero" : "--cv-falso", 1);
    nodo.style.transform = `translateX(${respuesta ? 140 : -140}%) rotate(${respuesta ? 18 : -18}deg)`;
    nodo.style.opacity = "0";
    const [nuevo] = await Promise.all([pedir("vidas/responder/", { respuesta }), esperar(280)]);
    if (nuevo) {
      pintarRetro();
      return;
    }
    nodo.classList.remove("vuela");
    nodo.style.opacity = "";
    regresar(nodo, false);
    botonesRespuesta.forEach((b) => { b.disabled = false; });
  }

  function pintarRetro() {
    const r = ronda();
    const u = r.ultima;
    nuevaPantalla("retro");
    const tarjeta = el("div", `cv-carta cv-retro ${u.correcta ? "ok" : "mal"}`);
    tarjeta.setAttribute("role", "status");
    const veredicto = el("p", "cv-retro-veredicto", u.correcta ? "✔ ¡Correcto!" : "✘ Incorrecto");
    veredicto.id = "cv-titulo";
    con(
      tarjeta,
      veredicto,
      el("p", "cv-carta-texto chico", `«${u.afirmacion}»`),
      el("p", "cv-retro-correcta", `La afirmación es ${u.respuesta ? "VERDADERA" : "FALSA"}.`),
      el("p", "cv-retro-explicacion", u.explicacion)
    );
    const siguiente = r.terminada
      ? boton("book-btn go", "Ver resultado ➔", () => pintarResultado(true))
      : boton("book-btn go", "Siguiente ➔", pintarTarjeta);
    con(cuerpo, progreso(u.numero), con(el("div", "cv-mazo"), tarjeta), con(el("div", "btn-row cv-botones"), el("span"), siguiente));
    enfocar(siguiente);
  }

  // ------------------------------------------------------------ pasos 10-11, FE1 y FA3
  function pintarResultado(animar) {
    const r = ronda();
    nuevaPantalla("resultado");
    pintarCorazones(animar && r.vidas_ganadas > 0);
    const titulo = el("h2", "cv-titulo", r.exito ? "¡Recuperaste una vida!" : "No lograste recuperar la vida. ¡Inténtalo más adelante!");
    titulo.id = "cv-titulo";
    let texto;
    if (r.exito && estado.hp >= estado.hp_max) texto = "¡Tienes todas tus vidas! Sigue con tu historia.";
    else if (r.exito) texto = "Si vuelves a perder vidas, puedes intentarlo de nuevo cuando quieras.";
    else texto = `Necesitabas ${estado.vidas.aciertos_minimos} aciertos. El botón «Conseguir vidas» sigue disponible.`;
    const volver = boton("book-btn go", "Volver a la historia ➔", volverALaHistoria);
    con(
      cuerpo,
      el("div", `cv-medalla ${r.exito ? "ok" : "mal"}`, r.exito ? LLENO : "✘"),
      titulo,
      el("p", "cv-marcador", `${r.aciertos} de ${r.total} aciertos`),
      el("p", "cv-texto", texto),
      con(el("div", "btn-row cv-botones"), el("span"), volver)
    );
    enfocar(volver);
  }

  // Paso 11 y FE2: el servidor borra la ronda y el libro se repinta con las vidas al día.
  async function volverALaHistoria() {
    const nuevo = await pedir("vidas/salir/");
    if (nuevo) cerrar(nuevo);
    else if (confirmar) cerrarConfirmacion();
  }

  // ------------------------------------------------------------ FE2: salir
  function salir() {
    if (ocupado) return;
    const r = ronda();
    if (pantalla === "instrucciones") cerrar();
    else if (r && !r.terminada) pedirConfirmacion();
    else volverALaHistoria(); // resultado (o retro de la última afirmación)
  }

  function pedirConfirmacion() {
    if (confirmar) return;
    const seguir = boton("book-btn", "Seguir jugando", cerrarConfirmacion);
    const titulo = el("p", "cv-confirmar-titulo", "¿Salir del minijuego?");
    titulo.id = "cv-confirmar-titulo";
    confirmar = con(
      el("div", "cv-confirmar"),
      con(
        el("div", "cv-confirmar-caja"),
        titulo,
        el("p", "cv-texto", "Si sales, perderás el progreso de esta ronda."),
        con(el("div", "btn-row cv-botones"), seguir, boton("book-btn go", "Salir", volverALaHistoria))
      )
    );
    confirmar.setAttribute("role", "alertdialog");
    confirmar.setAttribute("aria-modal", "true");
    confirmar.setAttribute("aria-labelledby", "cv-confirmar-titulo");
    hoja.appendChild(confirmar);
    enfocar(seguir);
  }

  function cerrarConfirmacion() {
    if (!confirmar) return;
    confirmar.remove();
    confirmar = null;
    enfocar(pantalla === "tarjeta" ? carta : cuerpo.querySelector(".book-btn.go"));
  }

  // ------------------------------------------------------------ teclado
  // FA2: flechas ← → para responder. Escape pide confirmación para salir (FE2). Tab no sale
  // de la ventana. El panel de ajustes de CU03 sigue funcionando encima.
  function teclado(ev) {
    if (!capa) return;
    const panelAjustes = document.getElementById("ajustes-panel");
    if (panelAjustes && panelAjustes.contains(ev.target)) return;
    if (ev.key === "Escape") {
      ev.preventDefault();
      if (confirmar) cerrarConfirmacion();
      else if (pantalla !== "sugerencia") salir();
    } else if ((ev.key === "ArrowLeft" || ev.key === "ArrowRight") && pantalla === "tarjeta" && !confirmar && !ocupado) {
      ev.preventDefault();
      const verdadero = ev.key === "ArrowRight";
      const b = botonesRespuesta[verdadero ? 1 : 0];
      if (b) {
        b.classList.add("presionado");
        setTimeout(() => b.classList.remove("presionado"), 180);
      }
      responder(verdadero);
    } else if (ev.key === "Tab") {
      atraparFoco(ev);
    }
  }

  function atraparFoco(ev) {
    const zona = confirmar || hoja;
    const enfocables = [...zona.querySelectorAll("button:not([disabled]), [tabindex='0']")];
    if (!enfocables.length) return;
    const primero = enfocables[0];
    const ultimo = enfocables[enfocables.length - 1];
    if (!zona.contains(document.activeElement)) {
      ev.preventDefault();
      primero.focus();
    } else if (ev.shiftKey && document.activeElement === primero) {
      ev.preventDefault();
      ultimo.focus();
    } else if (!ev.shiftKey && document.activeElement === ultimo) {
      ev.preventDefault();
      primero.focus();
    }
  }

  // ------------------------------------------------------------ API para partida.js
  window.CU06Vidas = {
    conectar(opciones) {
      llamar = opciones.llamar;
      alActualizar = opciones.alActualizar;
      return { boton: botonPermanente, sincronizar, abrir };
    },
  };
})();
