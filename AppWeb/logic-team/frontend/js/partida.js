// CU01 - Realizar partida. Dibuja el libro con el estado que manda el servidor.
// El servidor decide todo (resultado, vidas, probabilidades); aquí solo se pinta y se envía la
// opción elegida. Usa las clases de libro.css (.page, .choice, .medallion, .stamp, .book-btn).
(function () {
  "use strict";

  const spread = document.getElementById("pt-spread");
  const izq = document.getElementById("pt-izq");
  const der = document.getElementById("pt-der");
  const aviso = document.getElementById("pt-aviso");
  const listonCap = document.getElementById("ribbon-cap");
  const base = `/partida/${spread.dataset.partida}/`;
  const claveRespaldo = `logicteam.partida.${spread.dataset.partida}`;
  const LETRAS = "ABCD";

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

  function vaciar(nodo) { while (nodo.firstChild) nodo.removeChild(nodo.firstChild); }

  function cookie(nombre) {
    const m = document.cookie.match(new RegExp(`(?:^|; )${nombre}=([^;]*)`));
    return m ? decodeURIComponent(m[1]) : "";
  }

  function mostrarAviso(mensaje) {
    aviso.textContent = mensaje;
    aviso.hidden = false;
    clearTimeout(mostrarAviso.t);
    mostrarAviso.t = setTimeout(() => { aviso.hidden = true; }, 7000);
  }

  async function llamar(ruta, cuerpo) {
    const opciones = { headers: { Accept: "application/json" }, credentials: "same-origin" };
    if (cuerpo !== undefined) {
      opciones.method = "POST";
      opciones.headers["Content-Type"] = "application/json";
      opciones.headers["X-CSRFToken"] = cookie("csrftoken");
      opciones.body = JSON.stringify(cuerpo);
    }
    let respuesta;
    try {
      respuesta = await fetch(base + ruta, opciones);
    } catch (e) {
      throw new Error("No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.");
    }
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) throw new Error(datos.error || "No se pudo completar la acción.");
    return datos;
  }

  // Autoguardado local del avance (RNF-CON-06); el progreso real vive en el servidor.
  function respaldar(e) {
    try {
      localStorage.setItem(claveRespaldo, JSON.stringify({
        guardado: new Date().toISOString(), hp: e.hp, hp_max: e.hp_max,
        xp: e.xp, progreso: e.progreso, puntuacion: e.puntuacion,
      }));
    } catch (err) { /* el navegador puede bloquear el almacenamiento */ }
  }

  function leerRespaldo() {
    try { return JSON.parse(localStorage.getItem(claveRespaldo)); } catch (err) { return null; }
  }

  // ------------------------------------------------------------ piezas del libro
  const ornamento = () => { const o = el("div", "ornament"); o.setAttribute("aria-hidden", "true"); return o; };
  const numeroPagina = (n) => el("div", "page-num", `– ${n} –`);
  const sello = (texto, extra) => el("span", `stamp${extra ? " " + extra : ""}`, texto);

  function barra(etiqueta, valor, maximo, clase, texto) {
    const relleno = el("div", `pt-relleno ${clase}`);
    relleno.style.width = `${maximo ? Math.min(100, (valor / maximo) * 100) : 0}%`;
    return con(
      el("div"),
      con(el("div", "pt-barra-cab"), el("span", "k", etiqueta), el("span", "v", texto)),
      con(el("div", "pt-pista"), relleno)
    );
  }

  // Hoja de personaje: vidas, XP, avance y atributos (RF-05). Ocupa el lugar del emblema.
  function ficha(e) {
    const atributos = el("div", "pt-atributos");
    e.atributos.forEach((a) => con(atributos, sello(`${a.icono} ${a.nombre} ${a.valor}/${a.maximo}`)));
    if (e.puntos_atributo > 0) con(atributos, sello(`✨ ${e.puntos_atributo} por asignar`, "pt-stamp-oro"));
    return con(
      el("div", "pt-ficha"),
      barra("❤️ Vidas", e.hp, e.hp_max, "hp", `${e.hp}/${e.hp_max}`),
      barra(`⭐ Nivel ${e.nivel}`, e.xp_en_nivel, e.xp_por_nivel, "xp",
        e.nivel >= e.nivel_maximo ? "nivel máximo" : `${e.xp_en_nivel}/${e.xp_por_nivel} XP para el nivel ${e.nivel + 1}`),
      barra("📖 Historia", e.progreso, 100, "progreso", `${e.progreso}% · evento ${e.evento_numero} de ${e.evento_total}`),
      atributos
    );
  }

  function tarjeta(medallon, texto, sellos) {
    const boton = el("button", "choice");
    boton.type = "button";
    const cuerpo = con(el("div"), el("p", "pt-opcion", texto));
    if (sellos && sellos.length) {
      const fila = el("div");
      sellos.forEach((s) => con(fila, s));
      con(cuerpo, fila);
    }
    return con(boton, el("div", "medallion" + (medallon.length > 1 ? " pt-icono" : ""), medallon), cuerpo);
  }

  // Al reactivar, las tarjetas de atributos que ya están al máximo siguen bloqueadas
  function desactivar(botones, si) { botones.forEach((b) => { b.disabled = si || b.dataset.lleno === "1"; }); }

  // Sello de goma entintado (como los de oficina): doble anillo, texto en curva y una
  // palomita o tache al centro. La textura de tinta sale de un filtro SVG.
  function selloDeTinta(ok) {
    const caja = document.createElement("div");
    caja.className = "pt-sello " + (ok ? "ok" : "mal");
    caja.setAttribute("aria-hidden", "true");
    const centro = ok
      ? '<path d="M38 61 L53 76 L83 44" fill="none" stroke="currentColor" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>'
      : '<path d="M43 43 L77 77 M77 43 L43 77" fill="none" stroke="currentColor" stroke-width="10" stroke-linecap="round"/>';
    caja.innerHTML = `
      <svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id="pt-tinta" x="-10%" y="-10%" width="120%" height="120%">
            <feTurbulence type="fractalNoise" baseFrequency="0.32" numOctaves="3" seed="${ok ? 3 : 8}" result="ruido"/>
            <feColorMatrix in="ruido" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.7 1.62" result="motas"/>
            <feComposite in="SourceGraphic" in2="motas" operator="in" result="entintado"/>
            <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="1" seed="2" result="onda"/>
            <feDisplacementMap in="entintado" in2="onda" scale="1.6"/>
          </filter>
          <path id="pt-arco-sup" d="M 20 60 A 40 40 0 0 1 100 60"/>
          <path id="pt-arco-inf" d="M 11 60 A 49 49 0 0 0 109 60"/>
        </defs>
        <g filter="url(#pt-tinta)" fill="currentColor">
          <circle cx="60" cy="60" r="56" fill="none" stroke="currentColor" stroke-width="4.5"/>
          <circle cx="60" cy="60" r="50.5" fill="none" stroke="currentColor" stroke-width="1.8"/>
          <circle cx="60" cy="60" r="35" fill="none" stroke="currentColor" stroke-width="3"/>
          <text font-family="Cinzel, Georgia, serif" font-weight="900" font-size="12.5" letter-spacing="2" text-anchor="middle" stroke="currentColor" stroke-width="0.5">
            <textPath href="#pt-arco-sup" startOffset="50%">DECISIÓN</textPath>
          </text>
          <text font-family="Cinzel, Georgia, serif" font-weight="900" font-size="12.5" letter-spacing="2" text-anchor="middle" stroke="currentColor" stroke-width="0.5">
            <textPath href="#pt-arco-inf" startOffset="50%">${ok ? "CORRECTA" : "ERRÓNEA"}</textPath>
          </text>
          <text x="14.5" y="64.5" font-size="11" text-anchor="middle">★</text>
          <text x="105.5" y="64.5" font-size="11" text-anchor="middle">★</text>
          ${centro}
        </g>
      </svg>`;
    return caja;
  }

  // El libro se cierra (FE1): la página izquierda gira sobre el lomo y queda la portada.
  const PORTADA = `
    <svg viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <g fill="none" stroke="#e8b94f" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="34,14 8,40 34,66"/><line x1="72" y1="6" x2="48" y2="74"/><polyline points="86,14 112,40 86,66"/>
      </g>
    </svg>`;

  function copiaDePagina(pagina) {
    const copia = pagina.cloneNode(true);
    copia.removeAttribute("id");
    copia.querySelectorAll("[id]").forEach((n) => n.removeAttribute("id"));
    const hoja = el("div", "pt-cl-hoja");
    hoja.appendChild(copia);
    return hoja;
  }

  async function cerrarLibro() {
    const libroReal = document.getElementById("main-book");
    if (!libroReal || sinMovimiento() || !libroReal.animate) return;
    const r = libroReal.getBoundingClientRect();
    const capa = el("div", "pt-cierre");
    const velo = el("div", "pt-cierre-velo");

    if (window.innerWidth <= 820) {
      // En celular las páginas van una sobre otra: el libro solo se apaga
      con(document.body, con(capa, velo));
      libroReal.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "scale(.92)" }],
        { duration: 700, easing: "ease-in", fill: "forwards" });
      await velo.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 800, fill: "forwards" }).finished;
      return;
    }

    const libro = el("div", "pt-cl-libro");
    Object.assign(libro.style, { left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" });
    const derecha = con(el("div", "pt-cl-mitad"), copiaDePagina(der));
    const sombra = el("div", "pt-cl-sombra");
    con(derecha, sombra);
    const frente = con(el("div", "pt-cl-cara frente"), copiaDePagina(izq));
    const dorso = el("div", "pt-cl-cara dorso");
    dorso.innerHTML = PORTADA;
    const tapa = con(el("div", "pt-cl-tapa"), frente, dorso);
    con(document.body, con(capa, velo, con(libro, derecha, tapa)));
    libroReal.style.visibility = "hidden";

    // 1) La mitad izquierda gira sobre el lomo y cae encima de la derecha
    const giro = { duration: 1300, easing: "cubic-bezier(.55,.05,.3,1)", fill: "forwards" };
    tapa.animate([{ transform: "rotateY(0deg)" }, { transform: "rotateY(180deg)" }], giro);
    await sombra.animate([{ opacity: 0 }, { opacity: 1, offset: 0.85 }, { opacity: 0.2 }], giro).finished;
    // 2) El libro cerrado se centra, se encoge un poco y la escena se apaga
    libro.animate([{ transform: "none" }, { transform: `translateX(${-r.width / 4}px) scale(.9)` }],
      { duration: 800, easing: "ease-in-out", fill: "forwards" });
    await new Promise((res) => setTimeout(res, 650));
    await velo.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 650, easing: "ease-in", fill: "forwards" }).finished;
  }

  function sinMovimiento() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.dataset.movimiento === "reducido";
  }

  // ------------------------------------------------------------ fases
  // Flujo normal paso 1 (y FA2.1): situación, estado del jugador y opciones.
  function pintarEvento(e) {
    const ev = e.evento;
    const probabilidad = ev.tipo === "probabilidad";
    con(
      izq,
      el("div", "chapter-label", `CAPÍTULO ${e.bloque.capitulo} · ${e.bloque.nombre.toUpperCase()}`),
      el("h1", "chapter-title", ev.titulo),
      ornamento(),
      el("p", "pt-tema", `${ev.tema} · ${ev.subtema}`),
      el("p", "story", ev.contexto),
      ficha(e),
      numeroPagina(e.evento_numero * 2 - 1)
    );

    const lista = el("div", "choices");
    const botones = [];
    ev.opciones.forEach((op, i) => {
      const sellos = probabilidad
        ? [sello(`🎲 ${op.probabilidad}%`), sello(`${op.atributo_icono} ${op.atributo_nombre} ${op.valor_atributo}`, "pt-stamp-oro")]
        : [];
      const boton = tarjeta(LETRAS[i], op.texto, sellos);
      boton.setAttribute("aria-label", `Opción ${LETRAS[i]}: ${op.texto}` + (probabilidad ? `, probabilidad ${op.probabilidad}%` : ""));
      boton.addEventListener("click", () => elegir(op.id, boton, botones));
      botones.push(boton);
      con(lista, boton);
    });

    con(
      der,
      el("h2", "choose-title", "¿Qué decides?"),
      el("p", "choose-sub", probabilidad ? "Tu probabilidad depende de tus atributos" : "Analiza la situación y elige con criterio"),
      con(el("div", "pt-tipo"), sello(probabilidad ? "🎲 Prueba de atributos" : "🔎 Decisión de análisis")),
      lista,
      numeroPagina(e.evento_numero * 2)
    );
  }

  // Flujo normal paso 2: el usuario elige; el servidor resuelve y se estampa el sello
  // verde (correcta) o rojo (errónea) sobre la opción antes de pasar la página.
  async function elegir(opcionId, boton, botones) {
    desactivar(botones, true);
    boton.classList.add("selected");
    try {
      const estado = await llamar("decision/", { opcion_id: opcionId });
      const acierto = estado.resultado && estado.resultado.acierto;
      boton.classList.add(acierto ? "sello-ok" : "sello-mal", "golpe");
      boton.appendChild(selloDeTinta(acierto));
      boton.setAttribute("aria-label", (acierto ? "Correcta: " : "Errónea: ") + boton.getAttribute("aria-label"));
      await new Promise((res) => setTimeout(res, sinMovimiento() ? 400 : 1300));
      pintar(estado);
    } catch (err) {
      mostrarAviso(err.message);
      boton.classList.remove("selected");
      desactivar(botones, false);
    }
  }

  // Flujo normal pasos 3-6 (y FA2.2-2.3): retroalimentación, indicadores, desenlace y botón.
  function pintarResultado(e) {
    const r = e.resultado;
    con(
      izq,
      el("div", "chapter-label", "RETROALIMENTACIÓN TÉCNICA"),
      el("h1", "chapter-title", r.evento_titulo),
      ornamento(),
      el("p", `pt-veredicto ${r.acierto ? "ok" : "mal"}`, r.acierto ? "✔ Decisión acertada" : "✘ Decisión errónea"),
      el("p", "pt-eleccion", `Elegiste: «${r.opcion.texto}»`),
      el("p", "pt-retro", r.retroalimentacion)
    );
    if (r.riesgo) {
      con(
        izq,
        con(
          el("div", "pt-riesgo"),
          el("b", null, `🎲 ${r.riesgo.atributo} · probabilidad ${r.riesgo.probabilidad}% · riesgo ${r.riesgo.nivel}`),
          el("span", null, `Salió ${r.riesgo.tirada} de 100: ${r.acierto ? "éxito" : "fallo"}. ${r.riesgo.mensaje}`)
        )
      );
    }
    con(izq, ficha(e), numeroPagina(e.evento_numero * 2 - 1));

    const cambios = el("div", "pt-cambios");
    if (r.cambios.hp) con(cambios, sello(`❤️ ${r.cambios.hp} vida`, "pt-stamp-mal"));
    if (r.cambios.xp) con(cambios, sello(`⭐ +${r.cambios.xp} XP`, "pt-stamp-oro"));
    if (r.cambios.puntos) con(cambios, sello(`🏆 +${r.cambios.puntos}`, "pt-stamp-oro"));
    if (r.cambios.puntos_atributo) con(cambios, sello(`✨ +${r.cambios.puntos_atributo} punto de atributo`, "pt-stamp-oro"));

    const termino = r.estado_final !== "en_curso";
    const boton = el("button", "book-btn go", termino ? "Ver el final ➔" : "Pasar la página ➔");
    boton.type = "button";
    boton.addEventListener("click", async () => {
      boton.disabled = true;
      try {
        pintar(await llamar("continuar/", {}));
      } catch (err) {
        mostrarAviso(err.message);
        boton.disabled = false;
      }
    });

    con(
      der,
      el("h2", "choose-title", "Desenlace"),
      el("p", "choose-sub", `${r.tema} · ${r.subtema}`),
      el("p", "story", r.desenlace),
      cambios,
      con(el("div", "btn-row"), el("span"), boton),
      numeroPagina(e.evento_numero * 2)
    );
    boton.focus({ preventScroll: true });
  }

  // Mejora de atributos: la XP acumulada se convierte en puntos (estilo Life in Adventure).
  function pintarMejora(e) {
    con(
      izq,
      el("div", "chapter-label", `CAPÍTULO ${e.bloque.capitulo} · ${e.bloque.nombre.toUpperCase()}`),
      el("h1", "chapter-title", `¡Subes al nivel ${e.nivel}!`),
      ornamento(),
      el("p", "story", "Cada acierto te dio experiencia, y la experiencia se convierte en talento. Antes de seguir, elige qué atributo quieres fortalecer (máximo 10): las pruebas de probabilidad que vienen dependen de él."),
      ficha(e),
      numeroPagina(e.evento_numero * 2 - 1)
    );
    const lista = el("div", "choices");
    const botones = [];
    e.atributos.forEach((a) => {
      const lleno = a.valor >= a.maximo;
      const boton = tarjeta(a.icono, a.nombre, [
        sello(lleno ? `${a.valor}/${a.maximo} · al máximo` : `${a.valor} ➔ ${a.valor + 1}`, "pt-stamp-oro"),
      ]);
      boton.dataset.lleno = lleno ? "1" : "";
      boton.addEventListener("click", async () => {
        desactivar(botones, true);
        boton.classList.add("selected");
        try {
          pintar(await llamar("mejorar/", { atributo: a.id }));
        } catch (err) {
          mostrarAviso(err.message);
          boton.classList.remove("selected");
          desactivar(botones, false);
        }
      });
      botones.push(boton);
      con(lista, boton);
    });
    desactivar(botones, false);
    con(
      der,
      el("h2", "choose-title", "Elige tu atributo"),
      el("p", "choose-sub", `Puntos disponibles: ${e.puntos_atributo}`),
      lista,
      numeroPagina(e.evento_numero * 2)
    );
  }

  // ------------------------------------------------------------ dibujo general
  function pasarPagina() {
    spread.classList.remove("active");
    void spread.offsetWidth; // reinicia la animación turnPage de libro.css
    spread.classList.add("active");
  }

  function pintar(e, animar = true) {
    respaldar(e);
    if (e.fase === "fin") {
      terminar(e); // FA1 / FE1: pantalla Post Game
      return;
    }
    vaciar(izq);
    vaciar(der);
    listonCap.textContent = e.bloque.capitulo;
    if (e.fase === "resultado") pintarResultado(e);
    else if (e.fase === "mejora") pintarMejora(e);
    else pintarEvento(e);
    if (animar) {
      pasarPagina();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  // Al terminar: si perdió, el libro se cierra; en ambos casos el Post Game abre sin
  // pantalla de carga (ver post_game.html).
  async function terminar(e) {
    try { sessionStorage.setItem("trCierre", "1"); } catch (err) { /* sin almacenamiento */ }
    if (e.estado === "derrota") await cerrarLibro();
    window.location.href = e.url_fin;
  }

  function pintarSinConexion(mensaje) {
    vaciar(izq);
    vaciar(der);
    const respaldo = leerRespaldo();
    con(izq, el("div", "chapter-label", "SIN CONEXIÓN"), el("h1", "chapter-title", "El libro no abre"), ornamento(), el("p", "story", mensaje));
    if (respaldo) {
      con(izq, el("p", "final-note", `Último avance guardado en este dispositivo: ❤️ ${respaldo.hp}/${respaldo.hp_max} · ⭐ ${respaldo.xp} XP · 📖 ${respaldo.progreso}% · 🏆 ${respaldo.puntuacion}`));
    }
    const boton = el("button", "book-btn go", "Reintentar ➔");
    boton.type = "button";
    boton.addEventListener("click", () => llamar("estado/").then((e) => pintar(e)).catch((err) => mostrarAviso(err.message)));
    con(der, con(el("div", "btn-row"), el("span"), boton));
  }

  // Estado inicial: viene incrustado en la página; si falta, se pide al servidor.
  const inicial = document.getElementById("pt-estado");
  try {
    pintar(JSON.parse(inicial.textContent), false);
  } catch (err) {
    llamar("estado/").then((e) => pintar(e, false)).catch((e) => pintarSinConexion(e.message));
  }
})();
