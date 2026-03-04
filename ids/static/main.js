const dropZones = document.querySelectorAll(".drop-zone");
const fileInputs = document.querySelectorAll(".drop-zone input[type='file']");
const fileNameDisplays = {
  ifc: document.getElementById("ifc-file-name"),
  ids: document.getElementById("ids-file-name"),
};

const statusText = document.getElementById("status");
const validateBtn = document.getElementById("validate-btn");

let files = {
  ifc: null,
  ids: null,
};

let reportUrl = null;

// --- Поддержка drag-and-drop ---
dropZones.forEach((zone) => {
  const type = zone.dataset.type;

  // Mobile-friendly: prevent default on touchmove for dragover effect
  zone.addEventListener("touchmove", (e) => e.preventDefault(), { passive: false });

  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("dragover");
  });

  zone.addEventListener("dragleave", () => {
    zone.classList.remove("dragover");
  });

  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");

    const dt = e.dataTransfer;
    const filesList = dt?.files || [];

    handleFiles(filesList, type);
  });

  // Mobile-friendly click/tap
  zone.addEventListener("click", () => {
    const input = zone.querySelector("input[type='file']");
    input.click();
  });

  // Highlight on tap (for visual feedback)
  zone.addEventListener("touchstart", () => {
    zone.classList.add("dragover");
  });

  zone.addEventListener("touchend", () => {
    zone.classList.remove("dragover");
    setTimeout(() => {
      zone.querySelector("input[type='file']").click();
    }, 100); // slight delay to avoid conflict with touch events
  });
});

// --- Обработка выбора файла через проводник ---
fileInputs.forEach((input) => {
  input.addEventListener("change", (e) => {
    const type = e.target.closest(".drop-zone").dataset.type;
    const filesList = e.target.files;

    handleFiles(filesList, type);
  });
});

// --- Логика обработки файлов ---
function handleFiles(fileList, type) {
  if (!fileList || fileList.length === 0) return;

  const file = Array.from(fileList).find((f) => {
    if (type === "ifc") return f.name.toLowerCase().endsWith(".ifc");
    if (type === "ids")
      return (
        f.name.toLowerCase().endsWith(".ids") ||
        f.name.toLowerCase().endsWith(".xlsx")
      );
    return false;
  });

  if (!file) {
    alert(`Неверный формат файла для ${type.toUpperCase()}`);
    return;
  }

  // Сохраняем файл
  files[type] = file;
  fileNameDisplays[type].textContent = file.name;

  // Активируем кнопку, если загружены оба
  if (files.ids && files.ifc) {
    validateBtn.disabled = false;
    validateBtn.classList.add("active");
  }
}

// --- Обработка нажатия на кнопку "Проверить" / "Открыть отчёт" ---
validateBtn.addEventListener("click", () => {
  // Если уже есть отчёт — открываем его
  if (reportUrl) {
    window.open(reportUrl, "_blank");
    return;
  }

  // Иначе — запускаем проверку
  const formData = new FormData();

  if (!files.ids || !files.ifc) {
    alert("Пожалуйста, загрузите оба файла.");
    return;
  }

  formData.append("ids", files.ids);
  formData.append("ifc", files.ifc);

  statusText.textContent = " Идёт проверка...";
  validateBtn.disabled = true;
  validateBtn.textContent = "Проверка...";

  fetch("/validate", {
    method: "POST",
    body: formData,
  })
    .then(async (res) => {
      try {
        const data = await res.json();
        if (!res.ok) throw new Error("Ошибка сервера");
        return data;
      } catch (err) {
        throw new Error("Не удалось получить ответ от сервера");
      }
    })
    .then((result) => {
      if (result.report_url) {
        statusText.textContent = "Готово!";
        reportUrl = result.report_url;

        // Меняем текст кнопки
        validateBtn.textContent = "Открыть отчёт";
        validateBtn.disabled = false;

      } else {
        statusText.textContent = "Ошибка: отчёт не создан.";
        validateBtn.disabled = false;
      }
    })
    .catch((error) => {
      console.error(error);
      statusText.textContent = "Ошибка: " + error.message;
      validateBtn.disabled = false;
    });
});