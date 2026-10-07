const statusEl = document.getElementById("status");

fetch("/api/health/")
  .then((res) => res.json())
  .then((data) => {
    statusEl.textContent = `Servidor: ${data.status} · Base de datos: ${data.database}`;
    statusEl.classList.add("ok");
  })
  .catch(() => {
    statusEl.textContent = "No se pudo conectar con el servidor.";
    statusEl.classList.add("error");
  });
