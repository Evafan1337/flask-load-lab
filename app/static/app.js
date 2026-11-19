"use strict";

const body = document.getElementById("response-body");
const meta = document.getElementById("response-meta");
document.querySelectorAll("button[data-url]").forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    const started = performance.now();
    meta.textContent = `${button.dataset.label} · ожидание ответа…`;
    try {
      const response = await fetch(button.dataset.url, { cache: "no-store" });
      const text = await response.text();
      const elapsed = Math.round(performance.now() - started);
      meta.textContent = `HTTP ${response.status} · ${elapsed} мс`;
      try {
        body.textContent = JSON.stringify(JSON.parse(text), null, 2);
      } catch {
        body.textContent = text;
      }
    } catch (error) {
      meta.textContent = "Нет ответа";
      body.textContent = `Проверьте, что приложение запущено. ${error.message}`;
    } finally {
      button.disabled = false;
    }
  });
});
