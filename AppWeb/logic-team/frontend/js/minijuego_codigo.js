// CU04 - Resolver minijuego de código. Se abre desde el menú de modos (CU05).
// Mesa de trabajo: un programa completo (Python o pseudocódigo) con sus líneas revueltas. El
// jugador las pasa del banco a su programa, las ordena y les pone sangría (clic, arrastrar y
// soltar o teclado) y pide comprobar. El servidor revisa el acomodo y califica
// (services/minijuego_codigo.py); aquí solo se arma el programa y se muestra el resultado.
// Usa taller.css (.tl-*), minijuego_codigo.css (.c4-*) y los botones .book-btn de libro.css.
// El programa viaja como en el SDS 3.3.2: {programa: [{id: "l1", sangria: 0}, ...]}.
(function () {
  "use strict";

  const mesa = document.getElementById("mj-mesa");
  const inicial = JSON.parse(document.getElementById("mj-estado").textContent);
  const nivel = inicial.nivel;
  const rutas = mesa.dataset;

  const nodos = {
    salir: document.getElementById("mj-salir"),
    ayuda: document.getElementById("mj-ayuda"),
    lenguajes: document.getElementById("mj-lenguajes"),
    chip: document.getElementById("mj-chip"),
    niveles: document.getElementById("mj-niveles"),
    objetivo: document.getElementById("mj-objetivo"),
    ejemplo: document.getElementById("mj-ejemplo"),
    banco: document.getElementById("mj-banco"),
    listaBanco: document.getElementById("mj-lista-banco"),
    programa: document.getElementById("mj-programa"),
    aviso: document.getElementById("mj-aviso"),
    acciones: document.getElementById("mj-acciones"),
    velo: document.getElementById("mj-velo"),
  };

  const CLAVE_AYUDA = "logicteam.minijuego.ayudaVista";
  const MAX_SANGRIA = 6;
  const CODIGO = Object.fromEntries(nivel.lineas.map((l) => [l.id, l.codigo]));
  const ORDEN_BANCO = nivel.lineas.map((l) => l.id); // el orden revuelto que mandó el servidor

  // Para colorear el código y sugerir la sangría al pasar una línea
  const PALABRAS = {
    python: {
      clave: ["if", "else", "elif", "for", "in", "while", "def", "return", "and", "or", "not", "True", "False", "None"],
      funcion: ["print", "input", "int", "float", "range", "len", "str"],
      abre: (c) => /:\s*$/.test(c),
      cierra: (c) => /^(else|elif)\b/.test(c),
    },
    pseudocodigo: {
      clave: ["Algoritmo", "FinAlgoritmo", "Si", "Entonces", "SiNo", "FinSi", "Para", "Hasta", "Hacer", "FinPara",
        "Mientras", "FinMientras", "Repetir", "Definir", "Como", "Entero", "Real", "MOD", "Y", "O", "NO"],
      funcion: ["Leer", "Escribir"],
      abre: (c) => /^(Algoritmo|SiNo)\b|\b(Entonces|Hacer)\s*$/.test(c),
      cierra: (c) => /^(Fin\w*|SiNo)\b/.test(c),
    },
  };
  const LENGUAJE = PALABRAS[nivel.lenguaje] || PALABRAS.python;

  // fase: armar | comprobando | exito
  const s = {
    programa: [], // [{id, sangria}]
    banco: [], // ids
    seleccion: null, // índice de la línea elegida en el programa
    errores: {}, // id de línea -> nota en rojo
    aviso: null,
    fase: "armar",
    arrastre: null, // {id, desde: "banco" | "programa"}
    intentos: inicial.intentos_fallidos,
    penalizacion: inicial.penalizacion,
    resultado: inicial.resultado,
  };

  // ------------------------------------------------------------ utilidades
  function el(etiqueta, clase, texto) {
    const nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto !== undefined && texto !== null) nodo.textContent = texto;
    return nodo;
  }

  function con(padre, ...hijos) {
    hijos.forEach((hijo) => {
      if (hijo === null || hijo === undefined || hijo === false) return;
      padre.appendChild(typeof hijo === "string" ? document.createTextNode(hijo) : hijo);
    });
    return padre;
  }

  function vaciar(nodo) { while (nodo.firstChild) nodo.removeChild(nodo.firstChild); }

  function boton(clase, texto, alHacerClic) {
    const b = el("button", clase, texto);
    b.type = "button";
    if (alHacerClic) b.addEventListener("click", alHacerClic);
    return b;
  }

  // Texto con **negritas** (el objetivo viene así de niveles_codigo/*.json)
  function conNegritas(nodo, texto) {
    vaciar(nodo);
    texto.split("**").forEach((parte, i) => con(nodo, i % 2 ? el("b", null, parte) : parte));
  }

  function cookie(nombre) {
    const m = document.cookie.match(new RegExp(`(?:^|; )${nombre}=([^;]*)`));
    return m ? decodeURIComponent(m[1]) : "";
  }

  async function llamar(url, cuerpo) {
    let respuesta;
    try {
      respuesta = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": cookie("csrftoken"),
        },
        body: JSON.stringify(cuerpo || {}),
      });
    } catch (e) {
      throw new Error("No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.");
    }
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) throw new Error(datos.error || "No se pudo completar la acción.");
    return datos.codigo;
  }

  // Colorea palabras clave, funciones, textos y números (todo con textContent)
  function resaltar(codigo) {
    const frag = document.createDocumentFragment();
    const re = /("[^"]*")|(\b\d+(?:\.\d+)?\b)|([A-Za-zÁÉÍÓÚáéíóúÑñ_][\wÁÉÍÓÚáéíóúÑñ]*)|(<-)|(\s+|.)/g;
    let m;
    while ((m = re.exec(codigo))) {
      if (m[1]) con(frag, el("span", "tk-txt", m[1]));
      else if (m[2]) con(frag, el("span", "tk-num", m[2]));
      else if (m[3] && LENGUAJE.clave.includes(m[3])) con(frag, el("span", "tk-kw", m[3]));
      else if (m[3] && LENGUAJE.funcion.includes(m[3])) con(frag, el("span", "tk-fn", m[3]));
      else if (m[4]) con(frag, el("span", "tk-kw", "←"));
      else con(frag, m[0]);
    }
    return frag;
  }

  function editable() { return s.fase === "armar"; }

  // ------------------------------------------------------------ modelo del programa
  // Al pasar una línea se sugiere la sangría: un nivel más si la de arriba abre un bloque y
  // uno menos si la línea cierra uno (else, SiNo, FinSi...). El jugador la puede cambiar.
  function sangriaSugerida(id, indice) {
    const arriba = s.programa[indice - 1];
    if (!arriba) return 0;
    let sangria = arriba.sangria + (LENGUAJE.abre(CODIGO[arriba.id]) ? 1 : 0);
    if (LENGUAJE.cierra(CODIGO[id])) sangria -= 1;
    return Math.max(0, Math.min(MAX_SANGRIA, sangria));
  }

  function insertar(id, indice) {
    s.banco = s.banco.filter((x) => x !== id);
    const sangria = sangriaSugerida(id, indice);
    s.programa.splice(indice, 0, { id, sangria });
    s.seleccion = indice;
    cambio(indice);
  }

  function aPrograma(id) {
    if (!editable()) return;
    const indice = s.seleccion === null ? s.programa.length : s.seleccion + 1;
    insertar(id, indice);
  }

  function aBanco(indice) {
    if (!editable()) return;
    const [linea] = s.programa.splice(indice, 1);
    s.banco = ORDEN_BANCO.filter((id) => id === linea.id || s.banco.includes(id));
    s.seleccion = s.programa.length ? Math.min(indice, s.programa.length - 1) : null;
    cambio(s.seleccion);
  }

  function mover(indice, paso) {
    const destino = indice + paso;
    if (!editable() || destino < 0 || destino >= s.programa.length) return;
    const [linea] = s.programa.splice(indice, 1);
    s.programa.splice(destino, 0, linea);
    s.seleccion = destino;
    cambio(destino);
  }

  function sangrar(indice, paso) {
    const linea = s.programa[indice];
    if (!editable() || !linea) return;
    const nueva = Math.max(0, Math.min(MAX_SANGRIA, linea.sangria + paso));
    if (nueva === linea.sangria) return;
    linea.sangria = nueva;
    s.seleccion = indice;
    cambio(indice);
  }

  function reiniciar() {
    if (!editable()) return;
    s.programa = [];
    s.banco = [...ORDEN_BANCO];
    s.seleccion = null;
    cambio(null);
  }

  // Cualquier cambio quita las marcas del último intento
  function cambio(foco) {
    s.errores = {};
    s.aviso = null;
    pintar();
    enfocar(foco);
  }

  function enfocar(indice) {
    if (indice === null || indice === undefined) return;
    const fila = nodos.programa.querySelector(`[data-indice="${indice}"]`);
    if (fila) fila.focus({ preventScroll: false });
  }

  // ------------------------------------------------------------ arrastrar y soltar
  function arrastrable(nodo, datos) {
    nodo.draggable = true;
    nodo.addEventListener("dragstart", (ev) => {
      if (!editable()) { ev.preventDefault(); return; }
      s.arrastre = datos;
      ev.dataTransfer.effectAllowed = "move";
      ev.dataTransfer.setData("text/plain", datos.id);
      requestAnimationFrame(() => {
        if (s.arrastre !== datos) return;
        mesa.classList.add("arrastrando");
        nodo.classList.add("arrastrado");
      });
    });
    nodo.addEventListener("dragend", () => {
      s.arrastre = null;
      mesa.classList.remove("arrastrando");
      nodo.classList.remove("arrastrado");
      mesa.querySelectorAll(".encima").forEach((n) => n.classList.remove("encima"));
    });
  }

  function receptor(nodo, alSoltar) {
    nodo.addEventListener("dragover", (ev) => {
      if (!s.arrastre) return;
      ev.preventDefault();
      ev.stopPropagation();
      ev.dataTransfer.dropEffect = "move";
      nodo.classList.add("encima");
    });
    nodo.addEventListener("dragleave", () => nodo.classList.remove("encima"));
    nodo.addEventListener("drop", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      nodo.classList.remove("encima");
      alSoltar();
    });
  }

  // Soltar en una ranura del programa: entra ahí (del banco) o se mueve ahí (del programa)
  function soltarEn(indice) {
    const a = s.arrastre;
    if (!a || !editable()) return;
    if (a.desde === "banco") { insertar(a.id, indice); return; }
    const origen = s.programa.findIndex((l) => l.id === a.id);
    if (origen < 0) return;
    const [linea] = s.programa.splice(origen, 1);
    const destino = origen < indice ? indice - 1 : indice;
    s.programa.splice(destino, 0, linea);
    s.seleccion = destino;
    cambio(destino);
  }

  receptor(nodos.banco, () => {
    const a = s.arrastre;
    if (a && a.desde === "programa") aBanco(s.programa.findIndex((l) => l.id === a.id));
  });
  receptor(nodos.programa, () => soltarEn(s.programa.length));

  // ------------------------------------------------------------ dibujo
  function pintarBanco() {
    vaciar(nodos.listaBanco);
    if (!s.banco.length) {
      con(nodos.listaBanco, el("li", "c4-banco-vacio", "Ya pasaste todas las líneas."));
      return;
    }
    s.banco.forEach((id) => {
      const b = boton("c4-linea", null, () => aPrograma(id));
      const codigo = el("code");
      codigo.appendChild(resaltar(CODIGO[id]));
      con(b, codigo);
      b.setAttribute("aria-label", `Pasar a tu programa: ${CODIGO[id]}`);
      b.disabled = !editable();
      arrastrable(b, { id, desde: "banco" });
      con(nodos.listaBanco, con(el("li"), b));
    });
  }

  function ranura(indice) {
    const r = el("li", "c4-ranura");
    r.setAttribute("aria-hidden", "true");
    receptor(r, () => soltarEn(indice));
    return r;
  }

  function control(texto, etiqueta, accion, deshabilitado) {
    const b = boton("c4-ctl", texto, (ev) => { ev.stopPropagation(); accion(); });
    b.setAttribute("aria-label", etiqueta);
    b.title = etiqueta;
    b.tabIndex = -1; // con teclado se usan los atajos de la fila
    b.disabled = deshabilitado;
    return b;
  }

  function filaPrograma(linea, i) {
    const fila = el("li", "c4-fila");
    fila.dataset.indice = i;
    fila.tabIndex = 0;
    fila.style.setProperty("--s", linea.sangria);
    if (s.seleccion === i) fila.classList.add("elegida");
    if (s.errores[linea.id]) fila.classList.add("error");
    fila.setAttribute(
      "aria-label",
      `Línea ${i + 1}, sangría ${linea.sangria}: ${CODIGO[linea.id]}${s.errores[linea.id] ? `. Error: ${s.errores[linea.id]}` : ""}`
    );

    const codigo = el("code", "c4-texto");
    codigo.appendChild(resaltar(CODIGO[linea.id]));
    con(fila, el("span", "c4-num", String(i + 1)), con(el("span", "c4-sangria"), codigo));

    if (editable()) {
      con(
        fila,
        con(
          el("span", "c4-ctls"),
          control("⇤", "Quitar sangría", () => sangrar(i, -1), linea.sangria === 0),
          control("⇥", "Dar sangría", () => sangrar(i, 1), linea.sangria >= MAX_SANGRIA),
          control("↑", "Subir", () => mover(i, -1), i === 0),
          control("↓", "Bajar", () => mover(i, 1), i === s.programa.length - 1),
          control("✕", "Regresar al banco", () => aBanco(i), false)
        )
      );
      arrastrable(fila, { id: linea.id, desde: "programa" });
      fila.addEventListener("click", () => {
        s.seleccion = i;
        nodos.programa.querySelectorAll(".elegida").forEach((n) => n.classList.remove("elegida"));
        fila.classList.add("elegida");
      });
      fila.addEventListener("keydown", (ev) => teclado(ev, i));
    }
    // La nota va al final: ocupa su propio renglón debajo de la línea
    if (s.errores[linea.id]) con(fila, el("span", "c4-nota-error", s.errores[linea.id]));
    return fila;
  }

  function teclado(ev, i) {
    let hecho = true;
    if (ev.key === "Tab") {
      // Si ya no se puede cambiar la sangría, Tab sigue al siguiente control como siempre
      const sangria = s.programa[i].sangria;
      if (ev.shiftKey ? sangria === 0 : sangria >= MAX_SANGRIA) return;
      sangrar(i, ev.shiftKey ? -1 : 1);
    } else if (ev.altKey && ev.key === "ArrowUp") mover(i, -1);
    else if (ev.altKey && ev.key === "ArrowDown") mover(i, 1);
    else if (ev.key === "ArrowUp") { s.seleccion = Math.max(0, i - 1); enfocar(s.seleccion); }
    else if (ev.key === "ArrowDown") { s.seleccion = Math.min(s.programa.length - 1, i + 1); enfocar(s.seleccion); }
    else if (ev.key === "Delete" || ev.key === "Backspace") aBanco(i);
    else hecho = false;
    if (hecho) ev.preventDefault();
  }

  function pintarPrograma() {
    vaciar(nodos.programa);
    nodos.programa.classList.toggle("bloqueado", !editable());
    if (!s.programa.length) {
      const vacio = el("li", "c4-vacio");
      con(vacio, el("span", null, "⌨"), "Pasa aquí las líneas del banco");
      receptor(vacio, () => soltarEn(0));
      con(nodos.programa, vacio);
      return;
    }
    s.programa.forEach((linea, i) => {
      if (editable()) con(nodos.programa, ranura(i));
      con(nodos.programa, filaPrograma(linea, i));
    });
    if (editable()) con(nodos.programa, ranura(s.programa.length));
  }

  function pintarAviso() {
    const a = s.aviso;
    nodos.aviso.hidden = !a;
    if (!a) return;
    nodos.aviso.className = `tl-aviso ${a.tipo}`;
    vaciar(nodos.aviso);
    const texto = el("div");
    con(texto, el("b", null, a.titulo), a.texto);
    con(nodos.aviso, el("span", "ico", a.ico), texto);
  }

  function pintarBarra() {
    const chip = s.intentos && s.fase !== "exito" ? `Intentos fallidos: ${s.intentos} · −${s.penalizacion}%` : null;
    nodos.chip.hidden = !chip;
    if (chip) {
      nodos.chip.className = "tl-chip alerta";
      nodos.chip.textContent = chip;
    }
    nodos.salir.disabled = s.fase === "exito";
  }

  function pintarAcciones() {
    vaciar(nodos.acciones);
    const limpiar = boton("book-btn", "↺ Regresar todo", reiniciar);
    limpiar.disabled = !editable() || !s.programa.length;
    const comprobar = boton(`book-btn go${s.programa.length ? " siguiente" : ""}`, "▶ Comprobar", comprobarPrograma);
    comprobar.disabled = !editable();
    con(nodos.acciones, limpiar, comprobar);
  }

  function pintar() {
    pintarBarra();
    pintarBanco();
    pintarPrograma();
    pintarAviso();
    pintarAcciones();
  }

  // Selector de lenguaje y de niveles (enlaces a la mesa de cada nivel; el servidor da las URL)
  function pintarNavegacion() {
    vaciar(nodos.lenguajes);
    inicial.lenguajes.forEach((l) => {
      const actual = l.id === nivel.lenguaje;
      const a = el(actual ? "span" : "a", `c4-lenguaje${actual ? " actual" : ""}`, l.nombre);
      if (actual) a.setAttribute("aria-current", "true");
      else a.href = l.url;
      con(nodos.lenguajes, a);
    });

    vaciar(nodos.niveles);
    inicial.niveles.forEach((n) => {
      const actual = n.numero === nivel.numero;
      const a = el(actual ? "span" : "a", `c4-nivel${actual ? " actual" : ""}${n.estrellas ? " resuelto" : ""}`);
      if (actual) a.setAttribute("aria-current", "page");
      else a.href = n.url;
      const estrellas = n.estrellas ? "★".repeat(n.estrellas) : "";
      con(a, el("b", null, String(n.numero)), el("span", "c4-nivel-titulo", n.nombre), estrellas ? el("span", "c4-nivel-estrellas", estrellas) : null);
      a.setAttribute("aria-label", `Nivel ${n.numero}: ${n.nombre}${n.estrellas ? `, ${n.estrellas} estrellas` : ""}`);
      con(nodos.niveles, a);
    });
  }

  // Consola de ejemplo: lo que escribe el programa y lo que teclea el usuario
  function consola(lineas, clase) {
    const caja = el("div", `c4-consola${clase ? " " + clase : ""}`);
    lineas.forEach((l, i) => {
      const fila = con(el("div", "c4-consola-linea"), l.texto);
      if (l.entrada) con(fila, el("span", "c4-consola-entrada", l.entrada));
      fila.style.setProperty("--i", i);
      con(caja, fila);
    });
    return caja;
  }

  // ------------------------------------------------------------ comprobar (pasos 4 a 9)
  async function comprobarPrograma() {
    if (!editable()) return;
    s.fase = "comprobando";
    nodos.acciones.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    let r;
    try {
      r = await llamar(rutas.comprobar, { programa: s.programa });
    } catch (err) {
      s.fase = "armar";
      s.aviso = { tipo: "mal", ico: "!", titulo: "No se pudo comprobar", texto: err.message };
      pintar();
      return;
    }
    s.intentos = r.intentos_fallidos;
    s.penalizacion = r.penalizacion;
    if (r.correcta) {
      s.fase = "exito";
      s.resultado = r.resultado;
      s.seleccion = null;
      s.aviso = { tipo: "ok", ico: "✔", titulo: r.titulo, texto: r.mensaje };
      pintar();
      mostrarResultado(r.resultado, r.consola);
      return;
    }
    s.fase = "armar";
    if (!r.completo) {
      // FE1 y FE3: todavía no se califica, no cuenta como intento fallido
      s.aviso = { tipo: "info", ico: "…", titulo: r.titulo, texto: r.mensaje };
    } else {
      // FE2: se marca cada línea con su problema y se explica el primero
      s.errores = Object.fromEntries(r.errores.map((e) => [e.linea_id, e.nota]));
      const extra = r.repetido
        ? " Es el mismo acomodo que ya probaste, así que no cuenta otra vez."
        : ` Intento fallido: −${r.penalizacion}% de la XP.`;
      s.aviso = { tipo: "mal", ico: "✘", titulo: r.titulo, texto: r.mensaje + extra };
    }
    pintar();
    const primera = r.errores && r.errores.length
      ? s.programa.findIndex((l) => l.id === r.errores[0].linea_id)
      : -1;
    if (primera >= 0) enfocar(primera);
  }

  // ------------------------------------------------------------ ventanas (resultado, ayuda y salir)
  let alCerrarVentana = null;

  function abrirVentana(contenido, alCerrar) {
    vaciar(nodos.velo);
    const ventana = con(el("div", "tl-pergamino tl-ventana"), ...contenido);
    ventana.setAttribute("role", "dialog");
    ventana.setAttribute("aria-modal", "true");
    const titulo = ventana.querySelector("h2");
    if (titulo) {
      titulo.id = "mj-ventana-titulo";
      ventana.setAttribute("aria-labelledby", titulo.id);
    }
    con(nodos.velo, ventana);
    nodos.velo.hidden = false;
    alCerrarVentana = alCerrar || null;
    const principal = ventana.querySelector(".book-btn.go") || ventana.querySelector("button");
    if (principal) principal.focus();
    return ventana;
  }

  function cerrarVentana() {
    nodos.velo.hidden = true;
    vaciar(nodos.velo);
    const alCerrar = alCerrarVentana;
    alCerrarVentana = null;
    if (alCerrar) alCerrar();
  }

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !nodos.velo.hidden && alCerrarVentana) cerrarVentana();
  });

  function filaResumen(izquierda, derecha, clase) {
    return con(el("div", clase), el("span", null, izquierda), el("span", null, derecha));
  }

  // Pasos 8 y 9: el programa "corre" en la consola, estrellas (RN01, RN03) y XP (RN04, RN05)
  function mostrarResultado(r, lineasConsola) {
    const estrellas = el("div", "c4-estrellas");
    estrellas.setAttribute("aria-label", `${r.estrellas} de ${r.estrellas_max} estrellas`);
    for (let i = 0; i < r.estrellas_max; i++) con(estrellas, el("span", i < r.estrellas ? "on" : "off", "★"));

    const fallos = r.intentos_fallidos;
    const nota = el("p");
    if (!fallos) con(nota, "¡A la primera! Tu programa quedó listo ", el("b", null, "sin intentos fallidos"), ".");
    else con(nota, "Tu programa quedó listo después de ", el("b", null, `${fallos} ${fallos === 1 ? "intento fallido" : "intentos fallidos"}`), ".");

    const resumen = con(
      el("div", "c4-resumen"),
      filaResumen(`${r.estrellas} ${r.estrellas === 1 ? "estrella" : "estrellas"}`, `${r.xp_base} XP (${r.porcentaje_xp}%)`),
      fallos ? filaResumen(`${fallos} ${fallos === 1 ? "intento fallido" : "intentos fallidos"}`, `−${r.penalizacion}%`) : null,
      filaResumen("Ganas", `⭐ +${r.xp} XP`, "total")
    );

    const botones = el("div", "btn-row");
    // «Otro programa» abre un intento nuevo del mismo nivel con otro programa al azar
    const otraVez = el("a", "book-btn", "🎲 Otro programa");
    otraVez.href = rutas.otraVez;
    con(botones, otraVez);
    const siguiente = inicial.niveles.find((n) => n.numero > nivel.numero);
    const menu = el("a", siguiente ? "book-btn" : "book-btn go", "Volver al menú");
    menu.href = rutas.menu;
    con(botones, menu);
    if (siguiente) {
      const ir = el("a", "book-btn go", "Siguiente nivel ➔");
      ir.href = siguiente.url;
      con(botones, ir);
    }

    const salida = lineasConsola ? [el("p", "c4-consola-titulo", "Así corre tu programa:"), consola(lineasConsola, "corre")] : [];
    const ventana = abrirVentana([el("h2", null, "¡Programa correcto!"), estrellas, ...salida, nota, resumen, botones]);
    ventana.classList.add("ancha");
  }

  // "¿Cómo se juega?"
  function mostrarAyuda() {
    if (!nodos.velo.hidden) return;
    try { localStorage.setItem(CLAVE_AYUDA, "1"); } catch (err) { /* sin almacenamiento */ }

    const intro = con(
      el("p"),
      `Aquí hay un programa completo en ${nivel.lenguaje_nombre}, pero con sus líneas revueltas. `,
      el("b", null, "Acomódalas para que el programa funcione"),
      "."
    );
    const pasos = con(
      el("ol", "c4-ayuda-pasos"),
      con(el("li"), el("b", null, "Pasa las líneas: "), "haz clic en una línea del banco y se agrega debajo de la línea que elegiste en tu programa. También puedes arrastrarla."),
      con(el("li"), el("b", null, "Ordénalas: "), "usa ↑ ↓ o arrástralas. Con ✕ una línea regresa al banco."),
      con(
        el("li"),
        el("b", null, "Dales sangría: "),
        nivel.lenguaje === "python"
          ? "con ⇥ metes una línea dentro del if o del for de arriba; con ⇤ la sacas."
          : "con ⇥ metes una línea dentro del Si, del Para o del Algoritmo de arriba; con ⇤ la sacas."
      ),
      con(el("li"), el("b", null, "Comprueba: "), `si algo está mal se marca en rojo. Cada intento fallido baja tus estrellas y resta ${inicial.penalizacion_por_fallo}% de la XP (máximo ${inicial.penalizacion_maxima}%).`)
    );
    const consejo = con(
      el("p", "c4-ayuda-consejo"),
      "💡 Hay ",
      el("b", null, "varias formas correctas"),
      ": por ejemplo, puedes leer los datos en el orden que quieras. Y cada vez que juegas un nivel te puede tocar ",
      el("b", null, "otro programa"),
      " con otros valores."
    );
    const sobran = nivel.distractores
      ? con(el("p", "c4-ayuda-consejo"), "⚠ Este nivel trae ", el("b", null, `${nivel.distractores} ${nivel.distractores === 1 ? "línea que sobra" : "líneas que sobran"}`), ": déjalas en el banco.")
      : null;
    const atajos = con(el("p", "c4-ayuda-atajos"), "Con teclado: elige una línea de tu programa y usa Tab / Shift+Tab para la sangría, Alt+↑ / Alt+↓ para moverla y Supr para regresarla al banco.");
    const listo = boton("book-btn go", "¡Entendido!", cerrarVentana);
    const ventana = abrirVentana(
      [el("h2", "tl-pregunta", "¿Cómo se juega?"), intro, pasos, consejo, sobran, atajos, con(el("div", "btn-row"), listo)],
      () => nodos.ayuda.focus({ preventScroll: true })
    );
    ventana.classList.add("ancha");
  }

  nodos.ayuda.addEventListener("click", mostrarAyuda);

  // FA3: abandonar en cualquier momento antes de terminar
  function confirmarSalida() {
    if (s.fase === "exito" || !nodos.velo.hidden) return;
    const texto = con(el("p"), "Perderás tu acomodo y ", el("b", null, "no ganarás XP"), ". Volverás al menú de modos de juego.");
    const quedarse = boton("book-btn", "Seguir intentando", cerrarVentana);
    const abandonar = boton("book-btn go", "Sí, abandonar", async () => {
      abandonar.disabled = quedarse.disabled = true;
      try {
        const datos = await llamar(rutas.salir);
        window.location.href = datos.url;
      } catch (err) {
        abandonar.disabled = quedarse.disabled = false;
        s.aviso = { tipo: "mal", ico: "!", titulo: "No se pudo salir", texto: err.message };
        pintarAviso();
      }
    });
    abrirVentana([el("h2", "tl-pregunta", "¿Abandonar el minijuego?"), texto, con(el("div", "btn-row"), quedarse, abandonar)], () => nodos.salir.focus({ preventScroll: true }));
    quedarse.focus();
  }

  nodos.salir.addEventListener("click", confirmarSalida);

  // ------------------------------------------------------------ inicio (paso 1)
  conNegritas(nodos.objetivo, nivel.objetivo);
  con(nodos.ejemplo, el("span", "c4-ejemplo-k", "Ejemplo"), consola(nivel.consola));
  pintarNavegacion();

  // Al recargar, el servidor devuelve el último acomodo comprobado
  const guardado = (inicial.programa || []).filter((l) => CODIGO[l.id] !== undefined);
  s.programa = guardado.map((l) => ({ id: l.id, sangria: l.sangria }));
  s.banco = ORDEN_BANCO.filter((id) => !s.programa.some((l) => l.id === id));

  if (inicial.estado === "resuelto" && inicial.resultado) {
    s.fase = "exito";
    s.aviso = { tipo: "ok", ico: "✔", titulo: "Ya resolviste este nivel", texto: "Este es tu programa. Presiona «Otro programa» para jugar con uno nuevo." };
    pintar();
    mostrarResultado(inicial.resultado, nivel.consola);
  } else {
    pintar();
    let vista = false;
    try { vista = localStorage.getItem(CLAVE_AYUDA) === "1"; } catch (err) { /* sin almacenamiento */ }
    if (!vista) mostrarAyuda();
  }
})();
