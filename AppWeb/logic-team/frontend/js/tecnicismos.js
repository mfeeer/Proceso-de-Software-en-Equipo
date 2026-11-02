// Cambios al CU01 que pide el CU05 (SRS RF-39 y RF-40).
//   RF-39  resalta con otro color los tecnicismos que aparecen en el texto del evento
//   RF-40  al presionar un tecnicismo muestra su explicación en un globo de pergamino
// El registro (RF-41) lo hace el servidor al mostrar el evento; aquí solo se avisa cuáles
// son nuevos. El servidor manda en el estado la lista "tecnicismos" del evento con sus
// formas (cómo aparecen escritos), así que aquí no hay contenido fijo.
(function () {
  "use strict";

  let globo = null;
  let origen = null;

  function el(etiqueta, clase, texto) {
    const nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto !== undefined && texto !== null) nodo.textContent = texto;
    return nodo;
  }

  function escapar(texto) {
    return texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  const minusculas = (texto) => texto.toLocaleLowerCase("es");

  // Expresión con todas las formas, de la más larga a la más corta, para que «clase base»
  // gane sobre «clase». Solo palabras completas y sin importar mayúsculas.
  function preparar(tecnicismos) {
    const porForma = new Map();
    tecnicismos.forEach((t) => (t.formas || []).forEach((f) => {
      if (f && !porForma.has(minusculas(f))) porForma.set(minusculas(f), t);
    }));
    if (!porForma.size) return null;
    const formas = [...porForma.keys()].sort((a, b) => b.length - a.length).map(escapar);
    const expresion = new RegExp(`(?<![\\p{L}\\p{N}_])(?:${formas.join("|")})(?![\\p{L}\\p{N}_])`, "giu");
    return { expresion, porForma };
  }

  function marca(texto, tecnicismo, interactivo) {
    if (!interactivo) {
      // Dentro de una opción (que ya es un botón) solo se colorea: la explicación está en la tira
      const span = el("span", "tc-termino tc-pasivo", texto);
      span.title = tecnicismo.nombre;
      return span;
    }
    const boton = el("button", "tc-termino", texto);
    boton.type = "button";
    boton.dataset.tc = tecnicismo.id;
    boton.setAttribute("aria-haspopup", "dialog");
    boton.setAttribute("aria-expanded", "false");
    boton.setAttribute("aria-label", `${texto}: tecnicismo, ver explicación`);
    boton.addEventListener("click", (ev) => { ev.stopPropagation(); alternar(boton, tecnicismo); });
    return boton;
  }

  // RF-39: recorre los textos de los nodos y envuelve cada tecnicismo encontrado.
  function resaltar(nodos, tecnicismos, opciones) {
    const interactivo = !opciones || opciones.interactivo !== false;
    const preparado = preparar(tecnicismos || []);
    if (!preparado) return;
    (Array.isArray(nodos) ? nodos : [nodos]).forEach((nodo) => {
      if (!nodo) return;
      const recorrido = document.createTreeWalker(nodo, NodeFilter.SHOW_TEXT, {
        acceptNode: (t) => (t.parentElement && t.parentElement.closest(".tc-termino")
          ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
      });
      const textos = [];
      while (recorrido.nextNode()) textos.push(recorrido.currentNode);
      textos.forEach((texto) => {
        const valor = texto.nodeValue;
        preparado.expresion.lastIndex = 0;
        let m;
        let ultimo = 0;
        const piezas = [];
        while ((m = preparado.expresion.exec(valor)) !== null) {
          const tecnicismo = preparado.porForma.get(minusculas(m[0]));
          if (!tecnicismo) continue;
          if (m.index > ultimo) piezas.push(document.createTextNode(valor.slice(ultimo, m.index)));
          piezas.push(marca(m[0], tecnicismo, interactivo));
          ultimo = m.index + m[0].length;
        }
        if (!piezas.length) return;
        if (ultimo < valor.length) piezas.push(document.createTextNode(valor.slice(ultimo)));
        const fragmento = document.createDocumentFragment();
        piezas.forEach((p) => fragmento.appendChild(p));
        texto.parentNode.replaceChild(fragmento, texto);
      });
    });
  }

  // RF-40: globo con la explicación, junto al tecnicismo presionado.
  function cerrar(devolverFoco) {
    if (!globo) return;
    globo.remove();
    globo = null;
    if (origen) {
      origen.setAttribute("aria-expanded", "false");
      if (devolverFoco) origen.focus({ preventScroll: true });
    }
    origen = null;
  }

  function colocar(objetivo) {
    const r = objetivo.getBoundingClientRect();
    const g = globo.getBoundingClientRect();
    const margen = 10;
    let top = r.bottom + 8;
    if (top + g.height > window.innerHeight - margen) top = Math.max(margen, r.top - g.height - 8);
    const left = Math.min(Math.max(margen, r.left + r.width / 2 - g.width / 2), window.innerWidth - g.width - margen);
    globo.style.top = `${top}px`;
    globo.style.left = `${left}px`;
  }

  function abrir(objetivo, tecnicismo) {
    cerrar(false);
    origen = objetivo;
    globo = el("div", "tc-globo");
    globo.id = "tc-globo";
    globo.setAttribute("role", "dialog");
    globo.setAttribute("aria-label", `Tecnicismo: ${tecnicismo.nombre}`);
    const x = el("button", "tc-cerrar", "✕");
    x.type = "button";
    x.setAttribute("aria-label", "Cerrar explicación");
    x.addEventListener("click", () => cerrar(true));
    globo.append(
      el("span", "tc-etiqueta", "🔎 Tecnicismo"),
      el("strong", "tc-nombre", tecnicismo.nombre),
      el("p", "tc-descripcion", tecnicismo.descripcion),
      x
    );
    globo.addEventListener("click", (ev) => ev.stopPropagation());
    document.body.appendChild(globo);
    objetivo.setAttribute("aria-expanded", "true");
    objetivo.setAttribute("aria-controls", "tc-globo");
    colocar(objetivo);
    x.focus({ preventScroll: true });
  }

  function alternar(objetivo, tecnicismo) {
    if (origen === objetivo) cerrar(true);
    else abrir(objetivo, tecnicismo);
  }

  document.addEventListener("click", () => cerrar(false));
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && globo) cerrar(true); });
  window.addEventListener("resize", () => cerrar(false));
  window.addEventListener("scroll", () => { if (globo && origen) colocar(origen); }, { passive: true });

  // Tira con los tecnicismos del evento: así también se puede ver la explicación de los que
  // solo aparecen en las opciones, y se avisa cuáles se acaban de descubrir.
  function tira(tecnicismos, nuevos) {
    if (!tecnicismos || !tecnicismos.length) return null;
    const recien = new Set(nuevos || []);
    const caja = el("div", "tc-tira");
    caja.appendChild(el("span", "tc-tira-titulo", "🔎 Tecnicismos:"));
    tecnicismos.forEach((t) => {
      const chip = el("button", "tc-chip", t.nombre);
      chip.type = "button";
      chip.dataset.tc = t.id;
      chip.setAttribute("aria-haspopup", "dialog");
      chip.setAttribute("aria-expanded", "false");
      if (recien.has(t.id)) {
        chip.classList.add("nuevo");
        chip.appendChild(el("span", "tc-nuevo", "¡nuevo!"));
        chip.setAttribute("aria-label", `${t.nombre}, tecnicismo nuevo descubierto. Ver explicación`);
      } else {
        chip.setAttribute("aria-label", `${t.nombre}. Ver explicación`);
      }
      chip.addEventListener("click", (ev) => { ev.stopPropagation(); alternar(chip, t); });
      caja.appendChild(chip);
    });
    if (recien.size) {
      const nombres = tecnicismos.filter((t) => recien.has(t.id)).map((t) => t.nombre);
      const aviso = el("span", "tc-sr", `Nuevos tecnicismos descubiertos: ${nombres.join(", ")}`);
      aviso.setAttribute("role", "status");
      caja.appendChild(aviso);
    }
    return caja;
  }

  window.CU01Tecnicismos = { resaltar, tira, cerrar };
})();
