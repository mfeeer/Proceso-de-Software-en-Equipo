
(function () {
  "use strict";

  const CLAVE = "logicteam.ajustes";
  const CLAVE_TIEMPO = "logicteam.musica.t"; // sessionStorage: retoma la música al cambiar de pantalla

  const reduceSistema =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const POR_DEFECTO = Object.freeze({
    tamano: "normal",
    fuente: "libro",
    contraste: "normal",
    movimiento: reduceSistema ? "reducido" : "normal",
    musica: false,
    volumen: 40,
  });

  const VALIDOS = {
    tamano: ["pequeno", "normal", "grande", "muy-grande"],
    fuente: ["libro", "dislexia", "legible"],
    contraste: ["normal", "alto"],
    movimiento: ["normal", "reducido"],
  };

  // --- Elementos (el panel puede no existir si una página no usa base.html) ---
  const raiz = document.documentElement;
  const nodo = document.getElementById("ajustes-root");
  const btn = document.getElementById("ajustes-btn");
  const panel = document.getElementById("ajustes-panel");
  const btnCerrar = document.getElementById("ajustes-cerrar");
  const btnRestaurar = document.getElementById("ajustes-restaurar");
  const aviso = document.getElementById("ajustes-aviso");
  const ctlContraste = document.getElementById("aj-contraste");
  const ctlMovimiento = document.getElementById("aj-movimiento");
  const ctlMusica = document.getElementById("aj-musica");
  const ctlVolumen = document.getElementById("aj-volumen");

  let almacenamientoOk = true;
  let avisadoSinGuardar = false;
  let estado = cargar();
  let audio = null;
  let esperandoGesto = false;
  let temporizadorAviso = null;

  // ---------- Estado y persistencia ----------
  function sanear(obj) {
    const out = Object.assign({}, POR_DEFECTO);
    if (!obj || typeof obj !== "object") return out;
    Object.keys(VALIDOS).forEach((k) => {
      if (VALIDOS[k].indexOf(obj[k]) !== -1) out[k] = obj[k];
    });
    if (typeof obj.musica === "boolean") out.musica = obj.musica;
    const v = Number(obj.volumen);
    if (obj.volumen !== null && obj.volumen !== "" && Number.isFinite(v) && v >= 0 && v <= 100) {
      out.volumen = Math.round(v);
    }
    return out;
  }

  function cargar() {
    try {
      const crudo = window.localStorage.getItem(CLAVE);
      return sanear(crudo ? JSON.parse(crudo) : null);
    } catch (e) {
      // Almacenamiento bloqueado o JSON corrupto
      almacenamientoOk = false;
      return Object.assign({}, POR_DEFECTO);
    }
  }

  function guardar() {
    try {
      window.localStorage.setItem(CLAVE, JSON.stringify(estado));
      almacenamientoOk = true;
    } catch (e) {
      almacenamientoOk = false;
    }
    // FE1 del CU03: se aplican los cambios pero se avisa que solo durarán esta sesión
    if (!almacenamientoOk && !avisadoSinGuardar) {
      avisadoSinGuardar = true;
      avisar("No se pudieron guardar tus ajustes: solo se mantendrán durante la sesión actual.");
    }
  }

  function avisar(texto) {
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.hidden = false;
    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(function () {
      aviso.hidden = true;
    }, 7000);
  }

  // ---------- Aplicar al DOM ----------
  function aplicar() {
    raiz.dataset.tamano = estado.tamano;
    raiz.dataset.fuente = estado.fuente;
    raiz.dataset.contraste = estado.contraste;
    raiz.dataset.movimiento = estado.movimiento;
    sincronizarControles();
    actualizarMusica();
  }

  function sincronizarControles() {
    if (!panel) return;
    panel.querySelectorAll('input[type="radio"]').forEach((r) => {
      r.checked = r.value === estado[r.name];
    });
    if (ctlContraste) ctlContraste.checked = estado.contraste === "alto";
    if (ctlMovimiento) ctlMovimiento.checked = estado.movimiento === "reducido";
    if (ctlMusica) ctlMusica.checked = estado.musica;
    if (ctlVolumen) ctlVolumen.value = String(estado.volumen);
  }

  function cambiar(clave, valor) {
    const nuevo = Object.assign({}, estado);
    nuevo[clave] = valor;
    estado = sanear(nuevo);
    aplicar();
    guardar();
  }

  function restaurar() {
    estado = Object.assign({}, POR_DEFECTO);
    aplicar();
    guardar();
    if (almacenamientoOk) avisar("Ajustes restaurados a los valores por defecto.");
  }

  // ---------- Música ----------
  function iniciarAudio() {
    const src = nodo && nodo.dataset.musicaSrc;
    if (!src || typeof Audio === "undefined") return null;
    const a = new Audio();
    a.loop = true;
    a.preload = "none";
    a.src = src;
    a.addEventListener("loadedmetadata", function () {
      try {
        const t = parseFloat(window.sessionStorage.getItem(CLAVE_TIEMPO));
        if (Number.isFinite(t) && t > 0 && t < a.duration) a.currentTime = t;
      } catch (e) {
        /* sin sessionStorage: la música empieza desde el inicio */
      }
    });
    a.addEventListener("error", function () {
      if (estado.musica) avisar("No se pudo cargar la música ambiental.");
    });
    return a;
  }

  function reproducir() {
    if (!audio) return;
    const p = audio.play();
    // Los navegadores bloquean el autoplay: se reintenta con el primer gesto del usuario
    if (p && typeof p.catch === "function") p.catch(esperarGesto);
  }

  function esperarGesto() {
    if (esperandoGesto) return;
    esperandoGesto = true;
    const alGesto = function () {
      esperandoGesto = false;
      document.removeEventListener("pointerdown", alGesto, true);
      document.removeEventListener("keydown", alGesto, true);
      if (estado.musica) reproducir();
    };
    document.addEventListener("pointerdown", alGesto, true);
    document.addEventListener("keydown", alGesto, true);
  }

  function actualizarMusica() {
    if (!audio) return;
    audio.volume = estado.volumen / 100;
    if (estado.musica) {
      if (audio.paused) reproducir();
    } else if (!audio.paused) {
      audio.pause();
    }
  }

  window.addEventListener("pagehide", function () {
    if (!audio || audio.paused) return;
    try {
      window.sessionStorage.setItem(CLAVE_TIEMPO, String(audio.currentTime));
    } catch (e) {
      /* ignorar */
    }
  });

  // ---------- Panel ----------
  function abrir() {
    panel.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    panel.focus();
  }

  function cerrar(devolverFoco) {
    panel.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    if (devolverFoco) btn.focus();
  }

  if (btn && panel) {
    btn.addEventListener("click", function () {
      if (panel.hidden) abrir();
      else cerrar(true);
    });
    if (btnCerrar) btnCerrar.addEventListener("click", function () { cerrar(true); });
    if (btnRestaurar) btnRestaurar.addEventListener("click", restaurar);

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hidden) cerrar(true);
    });
    document.addEventListener("pointerdown", function (e) {
      if (!panel.hidden && nodo && !nodo.contains(e.target)) cerrar(false);
    });

    panel.addEventListener("change", function (e) {
      const t = e.target;
      if (!t || t.tagName !== "INPUT") return;
      if (t.type === "radio" && VALIDOS[t.name]) cambiar(t.name, t.value);
      else if (t.id === "aj-contraste") cambiar("contraste", t.checked ? "alto" : "normal");
      else if (t.id === "aj-movimiento") cambiar("movimiento", t.checked ? "reducido" : "normal");
      else if (t.id === "aj-musica") cambiar("musica", t.checked);
    });
    panel.addEventListener("input", function (e) {
      if (e.target && e.target.id === "aj-volumen") cambiar("volumen", Number(e.target.value));
    });
  }

  // ---------- Arranque ----------
  audio = iniciarAudio();
  aplicar();

  // API pública (la usan las pruebas y, si hace falta, otras pantallas)
  window.LTAjustes = {
    POR_DEFECTO: POR_DEFECTO,
    obtener: function () { return Object.assign({}, estado); },
    cambiar: cambiar,
    restaurar: restaurar,
  };
})();
