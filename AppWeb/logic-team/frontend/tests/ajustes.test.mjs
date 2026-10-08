// Pruebas de ajustes.js (CU03). Cargan el panel real (ajustes_panel.html) y el script real en jsdom.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const panelHtml = readFileSync(join(raiz, "ajustes_panel.html"), "utf8")
  .replace(/\{%\s*comment\s*%\}[\s\S]*?\{%\s*endcomment\s*%\}/g, "")
  .replace(/\{%\s*load static\s*%\}/g, "")
  .replace(/\{%\s*static\s+'([^']+)'\s*%\}/g, "/static/$1");
const script = readFileSync(join(raiz, "js", "ajustes.js"), "utf8");

function crear({ guardado, bloqueado = false, rechazarPlay = false, reduceMotion = false } = {}) {
  const llamadas = [];
  const dom = new JSDOM(`<!DOCTYPE html><html><body>${panelHtml}</body></html>`, {
    url: "http://localhost/",
    runScripts: "outside-only",
    beforeParse(w) {
      if (bloqueado) {
        Object.defineProperty(w, "localStorage", { get() { throw new Error("bloqueado"); } });
      } else if (guardado !== undefined) {
        w.localStorage.setItem("logicteam.ajustes", typeof guardado === "string" ? guardado : JSON.stringify(guardado));
      }
      w.matchMedia = () => ({ matches: reduceMotion });
      w.Audio = class {
        constructor() { this.paused = true; this.volume = 1; this.loop = false; }
        addEventListener() {}
        play() {
          llamadas.push("play");
          if (rechazarPlay) return Promise.reject(new Error("autoplay bloqueado"));
          this.paused = false;
          return Promise.resolve();
        }
        pause() { llamadas.push("pause"); this.paused = true; }
      };
    },
  });
  dom.window.eval(script);
  const d = dom.window.document;
  return { w: dom.window, d, llamadas, html: d.documentElement };
}
const marcar = (w, el, valor) => {
  if (valor !== undefined) el.checked = valor; else el.checked = true;
  el.dispatchEvent(new w.Event("change", { bubbles: true }));
};
const guardadoEn = (w) => JSON.parse(w.localStorage.getItem("logicteam.ajustes"));

test("sin preferencias guardadas usa los valores por defecto", () => {
  const { html, d } = crear();
  assert.equal(html.dataset.tamano, "normal");
  assert.equal(html.dataset.fuente, "libro");
  assert.equal(html.dataset.contraste, "normal");
  assert.equal(html.dataset.movimiento, "normal");
  assert.equal(d.querySelector('input[name="tamano"][value="normal"]').checked, true);
  assert.equal(d.getElementById("aj-musica").checked, false);
});

test("respeta prefers-reduced-motion del sistema como valor inicial", () => {
  const { html } = crear({ reduceMotion: true });
  assert.equal(html.dataset.movimiento, "reducido");
});

test("aplica las preferencias guardadas al cargar", () => {
  const { html, d } = crear({ guardado: { tamano: "muy-grande", fuente: "dislexia", contraste: "alto", musica: false, volumen: 70 } });
  assert.equal(html.dataset.tamano, "muy-grande");
  assert.equal(html.dataset.fuente, "dislexia");
  assert.equal(html.dataset.contraste, "alto");
  assert.equal(d.querySelector('input[name="fuente"][value="dislexia"]').checked, true);
  assert.equal(d.getElementById("aj-volumen").value, "70");
});

test("ignora valores inválidos o JSON corrupto", () => {
  assert.equal(crear({ guardado: { tamano: "gigante", fuente: "comic" } }).html.dataset.tamano, "normal");
  const { html } = crear({ guardado: "{no es json" });
  assert.equal(html.dataset.fuente, "libro");
});

test("cambiar tamaño y tipo de letra se aplica al instante y se guarda", () => {
  const { w, d, html } = crear();
  marcar(w, d.querySelector('input[name="tamano"][value="grande"]'));
  marcar(w, d.querySelector('input[name="fuente"][value="dislexia"]'));
  assert.equal(html.dataset.tamano, "grande");
  assert.equal(html.dataset.fuente, "dislexia");
  assert.deepEqual([guardadoEn(w).tamano, guardadoEn(w).fuente], ["grande", "dislexia"]);
});

test("alto contraste y reducir animaciones", () => {
  const { w, d, html } = crear();
  marcar(w, d.getElementById("aj-contraste"), true);
  marcar(w, d.getElementById("aj-movimiento"), true);
  assert.equal(html.dataset.contraste, "alto");
  assert.equal(html.dataset.movimiento, "reducido");
  marcar(w, d.getElementById("aj-contraste"), false);
  assert.equal(html.dataset.contraste, "normal");
});

test("restaurar valores por defecto revierte todo y sincroniza el panel", () => {
  const { w, d, html } = crear({ guardado: { tamano: "pequeno", fuente: "legible", contraste: "alto", musica: false, volumen: 10 } });
  d.getElementById("ajustes-restaurar").click();
  assert.equal(html.dataset.tamano, "normal");
  assert.equal(html.dataset.fuente, "libro");
  assert.equal(html.dataset.contraste, "normal");
  assert.equal(d.querySelector('input[name="fuente"][value="libro"]').checked, true);
  assert.equal(d.getElementById("aj-volumen").value, "40");
  assert.equal(guardadoEn(w).tamano, "normal");
  assert.match(d.getElementById("ajustes-aviso").textContent, /restaurados/i);
});

test("FE1: con almacenamiento bloqueado aplica los cambios y avisa que solo duran la sesión", () => {
  const { w, d, html } = crear({ bloqueado: true });
  marcar(w, d.querySelector('input[name="tamano"][value="grande"]'));
  assert.equal(html.dataset.tamano, "grande");
  const aviso = d.getElementById("ajustes-aviso");
  assert.equal(aviso.hidden, false);
  assert.match(aviso.textContent, /sesión actual/);
});

test("música: activar reproduce, desactivar pausa y el volumen se aplica", () => {
  const { w, d, llamadas } = crear();
  marcar(w, d.getElementById("aj-musica"), true);
  assert.deepEqual(llamadas, ["play"]);
  const vol = d.getElementById("aj-volumen");
  vol.value = "80";
  vol.dispatchEvent(new w.Event("input", { bubbles: true }));
  assert.equal(w.LTAjustes.obtener().volumen, 80);
  marcar(w, d.getElementById("aj-musica"), false);
  assert.deepEqual(llamadas, ["play", "pause"]);
  assert.equal(guardadoEn(w).musica, false);
});

test("música guardada como activa: si el navegador bloquea el autoplay, reintenta con el primer gesto", async () => {
  const { w, d, llamadas } = crear({ guardado: { musica: true }, rechazarPlay: true });
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(llamadas, ["play"]);
  d.dispatchEvent(new w.Event("pointerdown", { bubbles: true }));
  assert.deepEqual(llamadas, ["play", "play"]);
});

test("el engranaje abre y cierra el panel; Escape lo cierra", () => {
  const { w, d } = crear();
  const btn = d.getElementById("ajustes-btn");
  const panel = d.getElementById("ajustes-panel");
  assert.equal(panel.hidden, true);
  btn.click();
  assert.equal(panel.hidden, false);
  assert.equal(btn.getAttribute("aria-expanded"), "true");
  d.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  assert.equal(panel.hidden, true);
  assert.equal(btn.getAttribute("aria-expanded"), "false");
});

test("los ajustes no tocan nada de la partida (solo atributos de <html> y su propia clave)", () => {
  const { w, d } = crear();
  marcar(w, d.querySelector('input[name="tamano"][value="grande"]'));
  const claves = Array.from({ length: w.localStorage.length }, (_, i) => w.localStorage.key(i));
  assert.deepEqual(claves, ["logicteam.ajustes"]);
});
