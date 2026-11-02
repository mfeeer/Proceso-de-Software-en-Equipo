// Pruebas del frontend del CU05 y de sus cambios al CU01. Cargan los scripts reales en jsdom.
//   tecnicismos.js     RF-39 (resaltar) y RF-40 (explicación al presionar)
//   cuestionario.js    RN07, FA3, resumen (RN06) y FE1
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const leer = (nombre) => readFileSync(join(raiz, "js", nombre), "utf8");

const TECNICISMOS = [
  { id: "clase", nombre: "Clase", descripcion: "Plantilla de objetos.", formas: ["clase", "clases"] },
  { id: "clase-base", nombre: "Clase base", descripcion: "Clase general.", formas: ["clase base"] },
  { id: "try-except", nombre: "Bloque try/except", descripcion: "Captura excepciones.", formas: ["try/except", "except"] },
];

function libro(html) {
  const dom = new JSDOM(`<!DOCTYPE html><html><body>${html}</body></html>`, {
    url: "http://localhost/",
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  dom.window.eval(leer("tecnicismos.js"));
  return { w: dom.window, d: dom.window.document, api: dom.window.CU01Tecnicismos };
}

// ------------------------------------------------------------ RF-39 y RF-40
test("RF-39 resalta cada tecnicismo como palabra completa y sin importar mayúsculas", () => {
  const { d, api } = libro('<p id="p">La CLASE Personaje usa un except vacío y captura excepciones.</p>');
  api.resaltar(d.getElementById("p"), TECNICISMOS);
  const marcas = [...d.querySelectorAll(".tc-termino")].map((m) => [m.textContent, m.dataset.tc]);
  assert.deepEqual(marcas, [["CLASE", "clase"], ["except", "try-except"]]);
  assert.equal(d.getElementById("p").textContent, "La CLASE Personaje usa un except vacío y captura excepciones.");
});

test("RF-39 la forma más larga gana: «clase base» no se parte en «clase»", () => {
  const { d, api } = libro('<p id="p">Revisa la clase base antes de heredar de otras clases.</p>');
  api.resaltar(d.getElementById("p"), TECNICISMOS);
  const marcas = [...d.querySelectorAll(".tc-termino")].map((m) => m.dataset.tc);
  assert.deepEqual(marcas, ["clase-base", "clase"]);
});

test("dentro de una opción solo se colorea (sin botones anidados)", () => {
  const { d, api } = libro('<button class="choice"><p id="p">Rodear con try/except</p></button>');
  api.resaltar(d.getElementById("p"), TECNICISMOS, { interactivo: false });
  const marca = d.querySelector(".tc-termino");
  assert.equal(marca.tagName, "SPAN");
  assert.ok(marca.classList.contains("tc-pasivo"));
  assert.equal(d.querySelectorAll("button button").length, 0);
});

test("resaltar dos veces el mismo texto no anida marcas", () => {
  const { d, api } = libro('<p id="p">Una clase</p>');
  api.resaltar(d.getElementById("p"), TECNICISMOS);
  api.resaltar(d.getElementById("p"), TECNICISMOS);
  assert.equal(d.querySelectorAll(".tc-termino").length, 1);
  assert.equal(d.querySelectorAll(".tc-termino .tc-termino").length, 0);
});

test("RF-40 al presionar un tecnicismo se abre su explicación y Escape la cierra", () => {
  const { w, d, api } = libro('<p id="p">Una clase</p>');
  api.resaltar(d.getElementById("p"), TECNICISMOS);
  const termino = d.querySelector(".tc-termino");
  termino.click();
  const globo = d.getElementById("tc-globo");
  assert.ok(globo);
  assert.match(globo.textContent, /Clase/);
  assert.match(globo.textContent, /Plantilla de objetos\./);
  assert.equal(termino.getAttribute("aria-expanded"), "true");
  d.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape" }));
  assert.equal(d.getElementById("tc-globo"), null);
  assert.equal(termino.getAttribute("aria-expanded"), "false");
  assert.equal(d.activeElement, termino); // el foco regresa al término
});

test("la tira muestra los tecnicismos del evento y marca los recién descubiertos (RF-41)", () => {
  const { d, api } = libro("");
  const tira = api.tira(TECNICISMOS, ["clase-base"]);
  d.body.appendChild(tira);
  const chips = [...tira.querySelectorAll(".tc-chip")];
  assert.equal(chips.length, 3);
  assert.deepEqual(chips.filter((c) => c.classList.contains("nuevo")).map((c) => c.dataset.tc), ["clase-base"]);
  assert.match(tira.querySelector("[role=status]").textContent, /Clase base/);
  chips[0].click();
  assert.match(d.getElementById("tc-globo").textContent, /Plantilla de objetos/);
  assert.equal(api.tira([], []), null);
});

// ------------------------------------------------------------ cuestionario.js
const PREGUNTAS = [
  { numero: 1, tecnicismo_id: "a", tecnicismo: "Trazabilidad", tipo: "A", tipo_nombre: "Definición", nombre: "", texto: "Seguir la vida de un requerimiento.", pide: "¿Qué tecnicismo es?", opciones: ["Elicitación", "Trazabilidad", "Sprint", "SRS"], correcta: 1, explicacion: "Trazabilidad: seguir la vida." },
  { numero: 2, tecnicismo_id: "b", tecnicismo: "Búsqueda binaria", tipo: "B", tipo_nombre: "Aplicación", nombre: "Búsqueda binaria", texto: "Descarta la mitad.", pide: "¿En qué situación se aplica?", opciones: ["Diccionario ordenado", "Lista desordenada", "Sumar", "Contraseña"], correcta: 0, explicacion: "Necesita datos ordenados." },
  { numero: 3, tecnicismo_id: "c", tecnicismo: "Clase", tipo: "C", tipo_nombre: "Completar", nombre: "Clase", texto: "_____ que define atributos.", pide: "¿Qué palabra falta?", opciones: ["Instancia", "Plantilla", "Captura", "Mitad"], correcta: 1, explicacion: "La palabra que falta es «Plantilla»." },
  { numero: 4, tecnicismo_id: "d", tecnicismo: "Sprint", tipo: "A", tipo_nombre: "Definición", nombre: "", texto: "Iteración corta.", pide: "¿Qué tecnicismo es?", opciones: ["SRS", "Clase", "Sprint", "Trazabilidad"], correcta: 2, explicacion: "Sprint: iteración corta." },
];
const GENERADO = { cuestionario_id: "id-1", token: "tok-1", generado: "2026-10-21T18:00:00-06:00", total: 4, preguntas: PREGUNTAS };

async function cuestionario({ generar = { status: 200, cuerpo: GENERADO }, resultado = { status: 201 }, guardado } = {}) {
  const envios = [];
  const dom = new JSDOM(
    `<!DOCTYPE html><html><body><div id="c5-mesa" data-generar="/api/cuestionario/generar/" data-resultado="/api/cuestionario/resultado/" data-menu="/jugar/" data-historia="/personalizar/"></div></body></html>`,
    { url: "http://localhost/jugar/cuestionario/", runScripts: "outside-only", pretendToBeVisual: true }
  );
  const w = dom.window;
  w.matchMedia = () => ({ matches: true }); // sin animaciones: no hay pausas
  if (guardado) w.localStorage.setItem("logicteam.cuestionario.actual", JSON.stringify(guardado));
  w.fetch = async (url, opciones) => {
    if (url.includes("generar")) {
      return { ok: generar.status < 400, status: generar.status, json: async () => generar.cuerpo };
    }
    envios.push(JSON.parse(opciones.body));
    if (resultado.red) throw new TypeError("Failed to fetch");
    const cuerpo = { cuestionario_id: "id-1", puntaje: resultado.puntaje ?? 75, aciertos: 3, total: 4, origen: "en_linea" };
    return { ok: resultado.status < 400, status: resultado.status, json: async () => cuerpo };
  };
  w.eval(leer("cuestionario_sync.js"));
  w.eval(leer("cuestionario.js"));
  await espera();
  return { w, d: w.document, envios };
}

const espera = () => new Promise((r) => setTimeout(r, 15));

async function elegir(d, indice) {
  d.querySelectorAll(".c5-op")[indice].click();
  await espera();
}

test("RN07 al responder la opción se marca en dorado sin decir si es correcta", async () => {
  const { d, w } = await cuestionario();
  assert.equal(d.querySelector(".tl-chip").textContent, "1 / 4");
  const op = d.querySelectorAll(".c5-op")[0]; // incorrecta
  op.click();
  assert.ok(op.classList.contains("elegida"));
  assert.equal(d.querySelectorAll(".sello-ok, .sello-mal, .ok, .mal").length, 0);
  await espera();
  assert.equal(d.querySelector(".tl-chip").textContent, "2 / 4");
  const guardado = JSON.parse(w.localStorage.getItem("logicteam.cuestionario.actual"));
  assert.deepEqual(guardado.respuestas, [0]); // las respuestas se guardan localmente
});

test("tipo B usa renglones y tipo C dibuja el hueco de la palabra faltante", async () => {
  const { d } = await cuestionario();
  await elegir(d, 1);
  assert.ok(d.querySelector(".c5-opciones").classList.contains("renglones"));
  await elegir(d, 0);
  assert.ok(d.querySelector(".c5-hueco"));
  assert.ok(!d.querySelector(".c5-pregunta .texto").textContent.includes("_____"));
});

test("pasos 10 y 11: resumen con puntaje, errores con su explicación y resultado enviado", async () => {
  const { d, envios } = await cuestionario();
  for (const i of [0, 0, 1, 2]) await elegir(d, i); // 1 error, 3 aciertos
  assert.equal(envios.length, 1);
  assert.deepEqual(envios[0].respuestas, [0, 0, 1, 2]);
  assert.equal(envios[0].token, "tok-1");
  assert.equal(envios[0].pendiente, false);
  assert.equal(d.querySelector(".c5-anillo b").textContent, "75");
  const errores = d.querySelectorAll(".c5-error");
  assert.equal(errores.length, 1);
  assert.match(errores[0].textContent, /Trazabilidad/);
  assert.match(errores[0].textContent, /Elicitación/);
  assert.match(errores[0].textContent, /Trazabilidad: seguir la vida\./);
  assert.match(d.querySelector(".c5-sello").textContent, /Guardado en tu historial/);
});

test("FE1 sin conexión el resultado queda pendiente en el dispositivo", async () => {
  const { d, w } = await cuestionario({ resultado: { red: true } });
  for (const i of [1, 0, 1, 2]) await elegir(d, i);
  const pendientes = JSON.parse(w.localStorage.getItem("logicteam.cuestionario.pendientes"));
  assert.equal(pendientes.length, 1);
  assert.equal(pendientes[0].token, "tok-1");
  assert.match(d.querySelector(".c5-sin-red").textContent, /pendiente de sincronizar/i);
  assert.match(d.querySelector(".c5-sello").textContent, /Pendiente/);
  assert.equal(d.querySelector(".c5-anillo b").textContent, "100"); // RN06 calculado en el dispositivo
});

test("FE1 al volver la conexión se sincroniza y se quita de pendientes", async () => {
  const { d, w, envios } = await cuestionario({ resultado: { red: true } });
  for (const i of [1, 0, 1, 2]) await elegir(d, i);
  w.fetch = async (url, opciones) => {
    envios.push(JSON.parse(opciones.body));
    return { ok: true, status: 201, json: async () => ({ cuestionario_id: "id-1", puntaje: 100 }) };
  };
  w.dispatchEvent(new w.Event("online"));
  await espera();
  assert.equal(envios.at(-1).pendiente, true);
  assert.equal(w.localStorage.getItem("logicteam.cuestionario.pendientes"), null);
  assert.match(d.querySelector(".c5-sello").textContent, /Guardado en tu historial/);
});

test("FA3 «Salir» pide confirmación; cancelar sigue en la misma pregunta", async () => {
  const { d } = await cuestionario();
  await elegir(d, 1);
  d.querySelector(".tl-salir").click();
  const ventana = d.querySelector(".tl-velo [role=alertdialog]");
  assert.match(ventana.textContent, /Se perderá tu progreso/);
  [...ventana.querySelectorAll("button")].find((b) => /Seguir/.test(b.textContent)).click();
  assert.equal(d.querySelector(".tl-velo"), null);
  assert.equal(d.querySelector(".tl-chip").textContent, "2 / 4");
});

test("FA1 sin tecnicismos suficientes muestra el avance y el botón a Historia narrativa", async () => {
  const cuerpo = { error: "insuficientes", registrados: 2, necesarios: 4, mensaje: "Has descubierto 2 de 4 tecnicismos necesarios. ¡Juega más partidas para desbloquear el cuestionario!" };
  const { d } = await cuestionario({ generar: { status: 409, cuerpo } });
  assert.match(d.body.textContent, /Has descubierto 2 de 4/);
  assert.equal(d.querySelectorAll(".c5-meter span.on").length, 2);
  assert.equal(d.querySelector("a.go").getAttribute("href"), "/personalizar/");
});

test("recargar a mitad del cuestionario retoma la misma pregunta", async () => {
  const { d } = await cuestionario({ guardado: { datos: GENERADO, respuestas: [1, 0] } });
  assert.equal(d.querySelector(".tl-chip").textContent, "3 / 4");
});
