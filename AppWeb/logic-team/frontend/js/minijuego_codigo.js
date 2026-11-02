// CU04 - Resolver minijuego de código. Se abre desde el menú de modos (CU05).
// Mesa de trabajo: el jugador arma el algoritmo con bloques (arrastrar y soltar, o clic para
// agregar), lo compila y lo ejecuta. El servidor valida, simula y califica todo
// (services/minijuego_codigo.py); aquí solo se arma el tablero y se anima la traza.
// Usa taller.css (.tl-*), minijuego_codigo.css (.c4-*, .b) y los botones .book-btn de libro.css.
// El tablero viaja con el formato del SDS 3.3.2: {id, tipo: "INBOX", destino} ...
(function () {
  "use strict";

  const mesa = document.getElementById("mj-mesa");
  const inicial = JSON.parse(document.getElementById("mj-estado").textContent);
  const nivel = inicial.nivel;
  const rutas = mesa.dataset;

  const nodos = {
    salir: document.getElementById("mj-salir"),
    ayuda: document.getElementById("mj-ayuda"),
    pasos: document.querySelectorAll("#mj-pasos li"),
    chip: document.getElementById("mj-chip"),
    contador: document.getElementById("mj-contador"),
    objetivo: document.getElementById("mj-objetivo"),
    inbox: document.getElementById("mj-inbox"),
    outbox: document.getElementById("mj-outbox"),
    tablero: document.getElementById("mj-tablero"),
    vars: document.getElementById("mj-vars"),
    pila: document.getElementById("mj-pila"),
    aviso: document.getElementById("mj-aviso"),
    paleta: document.getElementById("mj-paleta"),
    acciones: document.getElementById("mj-acciones"),
    velo: document.getElementById("mj-velo"),
  };

  // Los bloques del nivel vienen del catálogo instrucciones_codigo.json (etiqueta, tipo, descripción)
  const ESTILO = {
    entrada: { icono: "📥", clase: "es" },
    salida: { icono: "📤", clase: "es" },
    memoria: { icono: "📋", clase: "mem" },
    condicion: { icono: "⚖", clase: "cond" },
  };
  const BLOQUES = Object.fromEntries(nivel.bloques.map((b) => [
    b.id, { nombre: b.etiqueta, tipo: b.tipo, ayuda: b.descripcion, ...ESTILO[b.tipo] },
  ]));
  // entrada | salida | memoria | condicion
  const tipoDe = (b) => BLOQUES[b.tipo].tipo;
  const CLAVE_AYUDA = "logicteam.minijuego.ayudaVista";
  const SIMBOLOS = Object.fromEntries(nivel.operadores.map((o) => [o.id, o.simbolo]));

  // fase: armar | cambios | errores | compilado | ejecutando | fallo | exito
  const s = {
    programa: [],
    sueltos: [],
    fase: "armar",
    compilado: false, // ya se compiló alguna vez (para avisar de cambios, FA2)
    errores: {}, // id de bloque -> nota en rojo
    nErrores: 0,
    aviso: null,
    destino: null, // dónde se agrega un bloque con clic: {lista, indice}
    arrastre: null,
    activo: null,
    vars: {},
    varsNuevas: [],
    cinta: null,
    caso: null, // caso de prueba que se anima (el primero que falla o el ejemplo)
    correcta: false,
    resultado: inicial.resultado,
    intentos: inicial.intentos_fallidos,
    penalizacion: inicial.penalizacion,
    animacion: null,
  };
  let siguienteId = 0;

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

  function sinMovimiento() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      document.documentElement.dataset.movimiento === "reducido";
  }

  // ------------------------------------------------------------ modelo del tablero
  function nuevoBloque(tipo) {
    const v = nivel.variables;
    const bloque = { id: `b${++siguienteId}`, tipo };
    const clase = BLOQUES[tipo].tipo;
    if (clase === "entrada") {
      // Propone la primera variable que todavía no se lee de la INBOX
      const leidas = new Set(todos().filter((b) => tipoDe(b) === "entrada").map((b) => b.destino));
      bloque.destino = v.find((x) => !leidas.has(x)) || v[0];
    } else if (clase === "salida") {
      bloque.valor = v[0];
    } else if (clase === "memoria") {
      bloque.origen = v[0];
      bloque.destino = v[1] || "";
    } else {
      Object.assign(bloque, { condicion: { izq: "", op: "", der: "" }, si: [], no: [] });
    }
    return bloque;
  }

  const esSi = (b) => tipoDe(b) === "condicion";

  function aplanar(lista) {
    return lista.flatMap((b) => [b, ...(esSi(b) ? [...aplanar(b.si), ...aplanar(b.no)] : [])]);
  }

  function todos() { return [...aplanar(s.programa), ...aplanar(s.sueltos)]; }

  function buscar(id, listas = [s.programa, s.sueltos]) {
    for (const lista of listas) {
      for (let i = 0; i < lista.length; i++) {
        const b = lista[i];
        if (b.id === id) return { lista, indice: i, bloque: b };
        if (esSi(b)) {
          const dentro = buscar(id, [b.si, b.no]);
          if (dentro) return dentro;
        }
      }
    }
    return null;
  }

  // ¿La lista está dentro del bloque? (un SI no se puede soltar dentro de sí mismo)
  function contiene(bloque, lista) {
    if (!esSi(bloque)) return false;
    return [bloque.si, bloque.no].some((rama) => rama === lista || rama.some((b) => contiene(b, lista)));
  }

  function editable() { return ["armar", "cambios", "errores", "compilado"].includes(s.fase); }

  function avisoLimite() {
    s.aviso = { tipo: "info", ico: "🧱", titulo: "Llegaste al límite", texto: `Este nivel permite hasta ${nivel.max_bloques} bloques.` };
    pintarAviso();
  }

  function colocar(lista, indice, bloque) {
    lista.splice(indice, 0, bloque);
    s.destino = null;
    cambio();
  }

  function agregar(tipo) {
    if (!editable()) return;
    if (todos().length >= nivel.max_bloques) { avisoLimite(); return; }
    const d = s.destino || { lista: s.programa, indice: s.programa.length };
    colocar(d.lista, d.indice, nuevoBloque(tipo));
  }

  function quitar(id) {
    const encontrado = buscar(id);
    if (!encontrado || !editable()) return;
    encontrado.lista.splice(encontrado.indice, 1);
    s.destino = null;
    cambio();
  }

  // Suelta lo que se está arrastrando en una lista (null = suelto en el tablero, sin conectar)
  function soltar(lista, indice) {
    const a = s.arrastre;
    if (!a || !editable()) return;
    if (lista === null) { lista = s.sueltos; indice = s.sueltos.length; }
    let bloque;
    if (a.nuevo) {
      if (todos().length >= nivel.max_bloques) { avisoLimite(); return; }
      bloque = nuevoBloque(a.nuevo);
    } else {
      const origen = buscar(a.id);
      if (!origen || contiene(origen.bloque, lista)) return;
      if (origen.lista === lista && origen.indice < indice) indice--;
      origen.lista.splice(origen.indice, 1);
      bloque = origen.bloque;
    }
    colocar(lista, indice, bloque);
  }

  // FA1 / FA2: cualquier cambio quita los errores; si ya se había compilado, hay que volver a compilar
  function cambio() {
    s.errores = {};
    s.fase = s.compilado ? "cambios" : "armar";
    s.aviso = s.compilado
      ? { tipo: "info", ico: "↻", titulo: "Modificaste el tablero", texto: "Vuelve a compilar para poder ejecutar." }
      : null;
    reiniciarCinta();
    pintar();
  }

  function tablero() { return { tablero: s.programa, sueltos: s.sueltos }; }

  // ------------------------------------------------------------ arrastrar y soltar
  function arrastrable(nodo, datos) {
    nodo.draggable = true;
    nodo.addEventListener("dragstart", (ev) => {
      if (!editable()) { ev.preventDefault(); return; }
      s.arrastre = datos;
      ev.dataTransfer.effectAllowed = "move";
      ev.dataTransfer.setData("text/plain", datos.nuevo || datos.id);
      ev.stopPropagation();
      requestAnimationFrame(() => {
        if (s.arrastre !== datos) return; // el arrastre ya terminó
        mesa.classList.add("arrastrando");
        if (datos.id) nodo.classList.add("arrastrado");
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

  // Soltar en el tablero fuera de una ranura deja el bloque sin conectar (lo detecta FE1)
  receptor(nodos.tablero, () => soltar(null));
  // Soltar en la paleta un bloque del tablero lo quita (FA1)
  receptor(nodos.paleta, () => { if (s.arrastre && s.arrastre.id) quitar(s.arrastre.id); });

  // ------------------------------------------------------------ dibujo del tablero
  function desplegable(clave, valor, opciones, etiqueta, alCambiar) {
    const sel = el("select", "c4-sel");
    sel.dataset.clave = clave;
    sel.setAttribute("aria-label", etiqueta);
    sel.disabled = !editable();
    if (!opciones.some((o) => o.valor === valor)) opciones = [{ valor: "", texto: "?" }, ...opciones];
    opciones.forEach((o) => {
      const opcion = el("option", null, o.texto);
      opcion.value = o.valor;
      sel.appendChild(opcion);
    });
    sel.value = valor;
    sel.addEventListener("change", () => alCambiar(sel.value));
    sel.addEventListener("mousedown", (ev) => ev.stopPropagation());
    sel.draggable = false;
    return sel;
  }

  function parametros(b) {
    const vars = nivel.variables.map((v) => ({ valor: v, texto: v }));
    const ops = nivel.operadores.map((o) => ({ valor: o.id, texto: o.simbolo }));
    // Al cambiar se vuelve a dibujar el tablero: el foco regresa a la misma lista.
    // Los parámetros del SI viven dentro de b.condicion; los demás, en el bloque.
    const campo = (nombre, opciones, etiqueta, objeto = b) => {
      const clave = `${b.id}-${nombre}`;
      return desplegable(clave, objeto[nombre], opciones, etiqueta, (valor) => {
        objeto[nombre] = valor;
        cambio();
        const mismo = nodos.pila.querySelector(`[data-clave="${clave}"]`);
        if (mismo) mismo.focus({ preventScroll: true });
      });
    };
    const t = el("span", "t");
    const clase = tipoDe(b);
    if (clase === "entrada") con(t, "→", campo("destino", vars, "Variable donde se guarda"));
    else if (clase === "salida") con(t, campo("valor", vars, "Variable que se entrega"));
    else if (clase === "memoria") con(t, campo("origen", vars, "Copiar de"), "→", campo("destino", vars, "Copiar a"));
    else {
      con(
        t,
        campo("izq", vars, "Primera variable", b.condicion),
        campo("op", ops, "Comparación", b.condicion),
        campo("der", vars, "Segunda variable", b.condicion)
      );
    }
    return t;
  }

  function descripcion(b) {
    const nombre = BLOQUES[b.tipo].nombre;
    const clase = tipoDe(b);
    if (clase === "entrada") return `${nombre} a ${b.destino || "?"}`;
    if (clase === "salida") return `${nombre} ${b.valor || "?"}`;
    if (clase === "memoria") return `${nombre} de ${b.origen || "?"} a ${b.destino || "?"}`;
    const c = b.condicion;
    return `${nombre} ${c.izq || "?"} ${SIMBOLOS[c.op] || "?"} ${c.der || "?"}`;
  }

  function pieza(b, chico) {
    const info = BLOQUES[b.tipo];
    const clases = ["b", info.clase];
    if (chico) clases.push("chico");
    if (s.errores[b.id]) clases.push("error");
    if (s.activo === b.id) clases.push("activo");
    const p = con(el("span", clases.join(" ")), el("span", "i", info.icono), info.nombre, parametros(b));
    p.dataset.id = b.id;
    if (editable()) {
      arrastrable(p, { id: b.id });
      const x = boton("c4-quitar", "✕", () => quitar(b.id));
      x.setAttribute("aria-label", `Quitar ${descripcion(b)}`);
      con(p, x);
    }
    const fila = con(el("div", "c4-fila"), p);
    if (s.errores[b.id]) con(fila, el("span", "c4-nota-error", s.errores[b.id]));
    return fila;
  }

  function ranura(lista, indice) {
    const r = el("div", "c4-ranura");
    receptor(r, () => soltar(lista, indice));
    return r;
  }

  function hueco(lista) {
    const elegido = s.destino && s.destino.lista === lista;
    const h = boton(`c4-hueco${elegido ? " elegido" : ""}`, elegido ? "Aquí se agregará el siguiente bloque" : "Suelta aquí el bloque", () => {
      s.destino = { lista, indice: 0 };
      pintarTablero();
    });
    h.disabled = !editable();
    receptor(h, () => soltar(lista, 0));
    return h;
  }

  function pintarLista(contenedor, bloques, chico) {
    bloques.forEach((b, i) => {
      if (editable()) con(contenedor, ranura(bloques, i));
      con(contenedor, nodoBloque(b, chico));
    });
    if (editable()) con(contenedor, ranura(bloques, bloques.length));
  }

  function rama(etiqueta, bloques) {
    const r = con(el("div", "rama"), el("span", "etq", etiqueta));
    if (bloques.length) pintarLista(r, bloques, true);
    else if (editable()) con(r, hueco(bloques));
    else con(r, el("span", "c4-rama-vacia", "(vacío)"));
    return r;
  }

  // SI ... SI NO: bloque en forma de C con sus dos ramas
  function nodoBloque(b, chico) {
    if (!esSi(b)) return pieza(b, chico);
    return con(
      el("div", "b-si"),
      pieza(b, false),
      rama("se cumple:", b.si),
      el("div", "medio", "SI NO"),
      rama("no se cumple:", b.no),
      el("div", "fin")
    );
  }

  function pintarTablero() {
    vaciar(nodos.pila);
    nodos.tablero.classList.toggle("bloqueado", !editable());
    if (!s.programa.length && !s.sueltos.length) {
      // FE3: tablero vacío
      const vacio = boton(`c4-vacio${s.destino ? " elegido" : ""}`, null, () => nodos.paleta.querySelector("button")?.focus());
      con(vacio, con(el("div"), el("span", null, "🧱"), "Arrastra aquí los bloques de abajo"));
      vacio.disabled = !editable();
      receptor(vacio, () => soltar(s.programa, 0));
      con(nodos.pila, vacio);
      return;
    }
    const pila = con(el("div", "c4-pila"), el("span", "b inicio", "▶ INICIO"));
    pintarLista(pila, s.programa, false);
    con(nodos.pila, pila);
    if (s.sueltos.length) {
      const sueltos = el("div", "c4-suelto");
      s.sueltos.forEach((b) => con(sueltos, nodoBloque(b, false)));
      con(nodos.pila, sueltos);
    }
  }

  // ------------------------------------------------------------ cintas y variables
  function reiniciarCinta(caso = nivel.ejemplo) {
    s.cinta = { entrada: caso.entradas, esperada: caso.salida, leidos: 0, salida: [], viaja: false, estado: null };
    s.vars = Object.fromEntries(nivel.variables.map((v) => [v, null]));
    s.varsNuevas = [];
    s.activo = null;
  }

  function caja(texto, clase, etiqueta) {
    const c = el("span", `c4-caja${clase ? " " + clase : ""}`, texto);
    if (etiqueta) con(c, el("small", null, etiqueta));
    return c;
  }

  function pintarCintas() {
    const c = s.cinta;
    vaciar(nodos.inbox);
    con(nodos.inbox, el("span", "c4-cinta-nombre", "INBOX"));
    c.entrada.forEach((valor, i) => {
      const leido = i < c.leidos;
      con(nodos.inbox, caja(String(valor), leido ? "usada" : "", leido || s.fase === "exito" ? null : nivel.variables[i]));
    });
    con(nodos.inbox, el("span", "c4-cinta-ayuda", c.leidos ? "Ya se leyeron" : "Los datos entran por aquí"));

    vaciar(nodos.outbox);
    con(nodos.outbox, el("span", "c4-cinta-nombre", "OUTBOX"));
    const esperada = c.esperada.join(", ");
    let ayuda = `Se espera: ${esperada}`;
    if (!c.salida.length && !c.estado) {
      c.esperada.forEach((v) => con(nodos.outbox, caja(`${v}?`, "fantasma")));
    } else {
      c.salida.forEach((valor, i) => {
        const ultima = i === c.salida.length - 1;
        let clase = "";
        if (c.estado === "ok") clase = "ok";
        else if (c.estado === "mal" && ultima) clase = "mal";
        else if (c.viaja && ultima) clase = "viaja";
        con(nodos.outbox, caja(String(valor), clase));
      });
      if (c.estado === "ok") ayuda = "¡Correcto!";
      else if (c.estado === "mal") ayuda = `Se esperaba ${esperada}`;
      else if (c.viaja) ayuda = "Llegando...";
    }
    con(nodos.outbox, el("span", "c4-cinta-ayuda", ayuda));
  }

  function pintarVars() {
    vaciar(nodos.vars);
    nivel.variables.forEach((v) => {
      const valor = s.vars[v];
      con(nodos.vars, el("span", `c4-var${s.varsNuevas.includes(v) ? " nuevo" : ""}`, `${v} = ${valor === null || valor === undefined ? "?" : valor}`));
    });
  }

  // ------------------------------------------------------------ barra, aviso y acciones
  function pintarBarra() {
    const n = todos().length;
    nodos.contador.textContent = `🧱 ${n} / ${nivel.optimo}`;
    nodos.contador.setAttribute("aria-label", `Bloques usados: ${n} de ${nivel.optimo} (óptimo). Límite: ${nivel.max_bloques}`);

    const paso = { armar: 0, cambios: 1, errores: 1 }[s.fase] ?? 2;
    nodos.pasos.forEach((li, i) => {
      li.className = i < paso ? "hecho" : i === paso ? "actual" : "";
      if (i === paso) li.setAttribute("aria-current", "step");
      else li.removeAttribute("aria-current");
    });

    let chip = null;
    if (s.fase === "cambios") chip = ["", "↻ Cambios sin compilar"];
    else if (s.fase === "errores") chip = ["alerta", `✘ ${s.nErrores} ${s.nErrores === 1 ? "error" : "errores"}`];
    else if (s.fase === "compilado") chip = ["oro", "✔ Compilado"];
    else if (s.fase === "fallo") chip = ["alerta", `Intento fallido ${s.intentos} · −${s.penalizacion}%`];
    nodos.chip.hidden = !chip;
    if (chip) {
      nodos.chip.className = `tl-chip${chip[0] ? " " + chip[0] : ""}`;
      nodos.chip.textContent = chip[1];
    }
    nodos.salir.disabled = s.fase === "exito";
  }

  function pintarAviso() {
    const a = s.aviso;
    nodos.aviso.hidden = !a;
    if (!a) return;
    nodos.aviso.className = `tl-aviso ${a.tipo}`;
    vaciar(nodos.aviso);
    const texto = el("div");
    con(texto, el("b", null, a.titulo));
    con(texto, a.texto);
    con(nodos.aviso, el("span", "ico", a.ico), texto);
  }

  function pintarPaleta() {
    vaciar(nodos.paleta);
    nivel.bloques.forEach(({ id: tipo }) => {
      const info = BLOQUES[tipo];
      const b = boton(`b ${info.clase} chico`, null, () => agregar(tipo));
      con(b, el("span", "i", info.icono), info.nombre);
      b.title = `${info.ayuda}\nArrástralo al tablero o haz clic para agregarlo.`;
      b.setAttribute("aria-label", `Agregar bloque ${info.nombre}: ${info.ayuda}`);
      b.disabled = !editable();
      arrastrable(b, { nuevo: tipo });
      con(nodos.paleta, b);
    });
  }

  function pintarAcciones() {
    vaciar(nodos.acciones);
    if (s.fase === "ejecutando") {
      const a = s.animacion;
      con(
        nodos.acciones,
        boton("book-btn", a.pausa ? "▶ Seguir" : "❚❚ Pausa", pausar),
        boton("book-btn", a.rapido ? "▶ x1" : "▶▶ x2", acelerar)
      );
      return;
    }
    if (s.fase === "fallo") {
      con(
        nodos.acciones,
        boton("book-btn", "↺ Reiniciar", reiniciar),
        boton("book-btn go siguiente", "✎ Editar tablero", editar)
      );
      return;
    }
    const compilar = boton(`book-btn${s.fase === "cambios" ? " go siguiente" : ""}`, "⚙ COMPILAR", compilarTablero);
    const ejecutar = boton(s.fase === "compilado" ? "book-btn go siguiente verde" : "book-btn off", "▶ EJECUTAR", ejecutarTablero);
    compilar.disabled = !editable();
    ejecutar.disabled = s.fase !== "compilado";
    con(nodos.acciones, compilar, ejecutar);
  }

  function pintar() {
    pintarBarra();
    pintarTablero();
    pintarCintas();
    pintarVars();
    pintarAviso();
    pintarPaleta();
    pintarAcciones();
  }

  // ------------------------------------------------------------ compilar (pasos 4 y 5, FE1, FE3)
  async function compilarTablero() {
    if (!editable()) return;
    nodos.acciones.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    try {
      const r = await llamar(rutas.compilar, tablero());
      s.errores = Object.fromEntries(r.errores.map((e) => [e.bloque_id, e.mensaje]));
      if (r.vacio) {
        s.fase = "armar";
        s.aviso = { tipo: "mal", ico: "!", titulo: r.titulo, texto: r.mensaje };
      } else {
        s.compilado = true;
        s.fase = r.compilado ? "compilado" : "errores";
        s.nErrores = Math.max(1, r.errores.length);
        s.aviso = r.compilado
          ? { tipo: "ok", ico: "✔", titulo: r.titulo, texto: r.mensaje }
          : { tipo: "mal", ico: "!", titulo: r.titulo, texto: r.mensaje };
      }
    } catch (err) {
      s.aviso = { tipo: "mal", ico: "!", titulo: "No se pudo compilar", texto: err.message };
    }
    pintar();
    const siguiente = nodos.acciones.querySelector(".siguiente");
    if (siguiente) siguiente.focus({ preventScroll: true });
  }

  // ------------------------------------------------------------ ejecutar (pasos 6 a 9, FE2)
  async function ejecutarTablero() {
    if (s.fase !== "compilado") return;
    nodos.acciones.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    let r;
    try {
      r = await llamar(rutas.ejecutar, tablero());
    } catch (err) {
      // RN02: si el servidor no reconoce el tablero compilado, hay que volver a compilar
      s.fase = "cambios";
      s.aviso = { tipo: "mal", ico: "!", titulo: "No se pudo ejecutar", texto: err.message };
      pintar();
      return;
    }
    s.intentos = r.intentos_fallidos;
    s.penalizacion = r.penalizacion;
    s.caso = r.caso;
    s.correcta = r.correcta;
    s.resultado = r.resultado;
    s.errores = {};
    reiniciarCinta({ entradas: r.caso.entradas, salida: r.caso.salida_esperada });
    s.fase = "ejecutando";
    s.animacion = { i: 0, pausa: false, rapido: false, t: null };
    const c = r.caso;
    s.aviso = {
      tipo: "info",
      ico: "▶",
      titulo: "Ejecutando",
      texto: c.numero > 1
        ? `Prueba ${c.numero} de ${r.casos.length}: entran ${c.entradas.join(", ")}.`
        : `Entran ${c.entradas.join(", ")}.`,
    };
    pintar();
    s.animacion.t = setTimeout(avanzar, duracion());
  }

  function duracion() {
    if (sinMovimiento()) return 300;
    return s.animacion && s.animacion.rapido ? 450 : 950;
  }

  // Cada bloque se ilumina al ejecutarse y las cajas viajan entre las cintas
  function avanzar() {
    const a = s.animacion;
    if (!a || a.pausa || s.fase !== "ejecutando") return;
    const traza = s.caso.traza;
    if (a.i >= traza.length) { terminarEjecucion(); return; }
    // Cada paso trae lo que queda en la INBOX, lo que hay en la OUTBOX y el valor de las variables
    const paso = traza[a.i++];
    s.varsNuevas = nivel.variables.filter((v) => paso.variables[v] !== s.vars[v]);
    s.vars = paso.variables;
    s.activo = paso.bloque_id;
    s.cinta.viaja = paso.outbox.length > s.cinta.salida.length;
    s.cinta.leidos = s.cinta.entrada.length - paso.inbox.length;
    s.cinta.salida = paso.outbox;
    s.aviso = { tipo: "info", ico: "▶", titulo: "Ejecutando", texto: paso.nota };
    pintarTablero();
    pintarCintas();
    pintarVars();
    pintarAviso();
    a.t = setTimeout(avanzar, duracion());
  }

  function pausar() {
    const a = s.animacion;
    a.pausa = !a.pausa;
    clearTimeout(a.t);
    if (!a.pausa) a.t = setTimeout(avanzar, 150);
    pintarAcciones();
    nodos.acciones.querySelector("button").focus({ preventScroll: true });
  }

  function acelerar() {
    s.animacion.rapido = !s.animacion.rapido;
    pintarAcciones();
    nodos.acciones.querySelectorAll("button")[1].focus({ preventScroll: true });
  }

  function terminarEjecucion() {
    clearTimeout(s.animacion && s.animacion.t);
    s.animacion = null;
    s.activo = null;
    s.varsNuevas = [];
    s.cinta.viaja = false;
    const c = s.caso;
    if (s.correcta) {
      s.cinta.estado = "ok";
      s.fase = "exito";
      s.aviso = null;
      pintar();
      mostrarResultado(s.resultado);
      return;
    }
    // FE2: se detiene, la caja se marca en rojo y se señala el bloque a revisar
    s.fase = "fallo";
    s.cinta.estado = c.fallo.caja_mal ? "mal" : null;
    if (c.fallo.bloque_id) s.errores = { [c.fallo.bloque_id]: c.fallo.nota };
    const conCual = c.numero > 1 ? `Con ${c.entradas.join(" y ")}: ` : "";
    s.aviso = { tipo: "mal", ico: "✘", titulo: "La prueba falló", texto: conCual + c.fallo.mensaje };
    pintar();
    nodos.acciones.querySelector(".siguiente").focus({ preventScroll: true });
  }

  // Después de fallar: "Reiniciar" vacía el tablero; "Editar tablero" conserva los bloques
  function reiniciar() {
    s.programa = [];
    s.sueltos = [];
    s.errores = {};
    s.compilado = false;
    s.fase = "armar";
    s.aviso = null;
    reiniciarCinta();
    pintar();
  }

  function editar() {
    s.fase = "armar";
    s.aviso = { tipo: "info", ico: "✎", titulo: "Corrige tu algoritmo", texto: "Cambia los bloques y vuelve a compilar." };
    reiniciarCinta();
    pintar();
  }

  // ------------------------------------------------------------ ventanas (resultado y salir)
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

  // Pasos 8 y 9: estrellas (RN01, RN03) y resumen corto de la XP (RN04, RN05)
  function mostrarResultado(r) {
    const estrellas = el("div", "c4-estrellas");
    estrellas.setAttribute("aria-label", `${r.estrellas} de ${r.estrellas_max} estrellas`);
    for (let i = 0; i < r.estrellas_max; i++) con(estrellas, el("span", i < r.estrellas ? "on" : "off", "★"));

    const n = r.bloques_usados;
    const usados = el("p");
    if (n === r.optimo) con(usados, "Usaste ", el("b", null, `${n} bloques`), ", justo el óptimo.");
    else if (n < r.optimo) con(usados, "Usaste ", el("b", null, `${n} bloques`), ": ¡menos que el óptimo!");
    else con(usados, "Usaste ", el("b", null, `${n} bloques`), `; el óptimo es ${r.optimo}.`);

    const fallos = r.intentos_fallidos;
    const resumen = con(
      el("div", "c4-resumen"),
      filaResumen(`${r.estrellas} ${r.estrellas === 1 ? "estrella" : "estrellas"}`, `${r.xp_base} XP (${r.porcentaje_xp}%)`),
      fallos ? filaResumen(`${fallos} ${fallos === 1 ? "prueba fallida" : "pruebas fallidas"}`, `−${r.penalizacion}%`) : null,
      filaResumen("Ganas", `⭐ +${r.xp} XP`, "total")
    );

    // Paso 10: el minijuego se abrió desde el menú de modos, así que se regresa ahí
    const menu = el("a", "book-btn go", "Volver al menú ➔");
    menu.href = rutas.menu;
    const otraVez = el("a", "book-btn", "↺ Jugar otra vez");
    otraVez.href = rutas.otraVez;

    abrirVentana([el("h2", null, "¡Algoritmo correcto!"), estrellas, usados, resumen, con(el("div", "btn-row"), otraVez, menu)]);
  }

  // Mientras hay una ventana abierta la animación se detiene; al cerrarla sigue donde iba
  function detenerMientras(foco) {
    const a = s.animacion;
    const seguia = a && !a.pausa;
    if (seguia) { a.pausa = true; clearTimeout(a.t); }
    return () => {
      if (seguia && s.animacion) { s.animacion.pausa = false; s.animacion.t = setTimeout(avanzar, 150); }
      foco.focus({ preventScroll: true });
    };
  }

  // "¿Cómo se juega?": qué hace cada bloque del nivel y los tres pasos
  function mostrarAyuda() {
    if (!nodos.velo.hidden) return;
    try { localStorage.setItem(CLAVE_AYUDA, "1"); } catch (err) { /* sin almacenamiento */ }

    const intro = con(
      el("p"),
      "Arma un pequeño programa con bloques. Al ejecutarlo, los bloques corren ",
      el("b", null, "de arriba hacia abajo"),
      `: leen números de la INBOX, los guardan en variables (${nivel.variables.join(", ")}) y entregan el resultado en la OUTBOX.`
    );
    const bloques = el("ul", "c4-ayuda-bloques");
    nivel.bloques.forEach(({ id: tipo }) => {
      const info = BLOQUES[tipo];
      con(bloques, con(el("li"), con(el("span", `b ${info.clase} chico`), el("span", "i", info.icono), info.nombre), el("span", null, info.ayuda)));
    });
    const pasos = con(
      el("ol", "c4-ayuda-pasos"),
      con(el("li"), el("b", null, "Armar: "), "haz clic en un bloque de abajo para agregarlo al final, o arrástralo al tablero. Para meter un bloque dentro de un SI, haz clic en su hueco «Suelta aquí el bloque» y luego en el bloque. Con ✕ lo quitas."),
      con(el("li"), el("b", null, "Compilar: "), "revisa que todo esté completo y conectado. Si algo falta, se marca en rojo."),
      con(el("li"), el("b", null, "Ejecutar: "), `prueba tu programa con varios pares de números. Cada prueba fallida resta ${inicial.penalizacion_por_fallo}% de la XP (máximo ${inicial.penalizacion_maxima}%).`)
    );
    const consejo = con(el("p", "c4-ayuda-consejo"), "🧱 Usa pocos bloques: con ", el("b", null, `${nivel.optimo} (el óptimo)`), " ganas 3 estrellas.");
    const listo = boton("book-btn go", "¡Entendido!", cerrarVentana);
    abrirVentana([el("h2", "tl-pregunta", "¿Cómo se juega?"), intro, bloques, pasos, consejo, con(el("div", "btn-row"), listo)], detenerMientras(nodos.ayuda));
    nodos.velo.firstChild.classList.add("ancha");
  }

  nodos.ayuda.addEventListener("click", mostrarAyuda);

  // FA3: abandonar en cualquier momento antes de terminar
  function confirmarSalida() {
    if (s.fase === "exito" || !nodos.velo.hidden) return;
    const reanudar = detenerMientras(nodos.salir);

    const texto = con(el("p"), "Perderás tu solución y ", el("b", null, "no ganarás XP"), ". Volverás al menú de modos de juego.");
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
    abrirVentana([el("h2", "tl-pregunta", "¿Abandonar el minijuego?"), texto, con(el("div", "btn-row"), quedarse, abandonar)], reanudar);
    quedarse.focus();
  }

  nodos.salir.addEventListener("click", confirmarSalida);

  // ------------------------------------------------------------ inicio (paso 1)
  conNegritas(nodos.objetivo, nivel.objetivo);
  reiniciarCinta();
  // Al recargar, el servidor devuelve el último tablero compilado del intento
  s.programa = inicial.tablero || [];
  siguienteId = Math.max(0, ...todos().map((b) => parseInt(b.id.replace(/\D/g, ""), 10) || 0));
  if (inicial.estado === "resuelto" && inicial.resultado) {
    // Ya lo resolvió: se muestra su solución y el resultado
    s.fase = "exito";
    s.cinta.leidos = s.cinta.entrada.length;
    s.cinta.salida = s.cinta.esperada;
    s.cinta.estado = "ok";
    pintar();
    mostrarResultado(inicial.resultado);
  } else {
    if (inicial.compilado && s.programa.length) {
      s.compilado = true;
      s.fase = "compilado";
      s.aviso = { tipo: "ok", ico: "✔", titulo: "Retomaste tu tablero", texto: "Ya estaba compilado: puedes ejecutarlo o seguir editándolo." };
    }
    pintar();
    // La primera vez que se entra a un minijuego, la ayuda se abre sola
    let vista = false;
    try { vista = localStorage.getItem(CLAVE_AYUDA) === "1"; } catch (err) { /* sin almacenamiento */ }
    if (!vista) mostrarAyuda();
  }
})();
