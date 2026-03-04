# services/report_service.py

from pathlib import Path
from jinja2 import Template
import uuid
from datetime import datetime
from flask import url_for


def generate_report(spec_data, template_path, result_folder):
    """
    Генерирует HTML-отчет на основе данных валидации.
    Возвращает путь к файлу отчёта.
    """

    # --- Генерация имени файла ---
    filename = f"report_{uuid.uuid4()}.html"
    report_path = Path(result_folder) / filename

    # --- Чтение шаблона и рендеринг ---
    with open(template_path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    html_report = template.render(
        specs=spec_data["specifications"],
        total_elements=spec_data["total_elements"],
        ids_filename=spec_data["ids_filename"],
        ifc_filename=spec_data["ifc_filename"],
        timestamp=spec_data.get("timestamp", datetime.now().strftime("%d.%m.%Y %H:%M:%S")),
        filename=filename,
        url_for=url_for
    )

    # --- Сохранение отчёта ---
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_report)

    return filename