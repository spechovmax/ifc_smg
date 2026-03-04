import os
import tempfile
import logging
from flask import Flask, request, jsonify, render_template, send_file, url_for
from datetime import datetime
import traceback
from pathlib import Path

# --- Настройка временной папки ---
TEMP_FOLDER = os.path.join(os.getcwd(), "tmp")
RESULT_FOLDER = 'results'
REPORT_TEMPLATE_PATH = 'report_template/report.html'

os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
os.makedirs('logs', exist_ok=True)

# --- Логирование ---
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# --- Инициализация Flask ---
app = Flask(__name__)
app.template_folder = 'templates'
app.static_folder = 'static'

# --- Импорт сервисов ---
from services.ids_ifc_service import validate_ids_ifc
from services.excel_service import validate_excel
from services.report_service import generate_report


@app.route('/')
def index():
    user_agent = request.headers.get('User-Agent', 'Unknown')
    ip = request.remote_addr
    app.logger.info(f"Посещение главной страницы. IP: {ip}, User-Agent: {user_agent}")
    return render_template('index.html')


@app.route('/validate', methods=['POST'])
def validate_model():
    try:
        file_ids = request.files.get('ids')
        file_ifc = request.files.get('ifc')

        if not file_ids or not file_ifc:
            msg = "Необходимо загрузить оба файла."
            app.logger.warning(msg)
            return jsonify({"error": msg}), 400

        # Сохраняем имена файлов
        ids_filename = file_ids.filename
        ifc_filename = file_ifc.filename

        msg = f"Загружены файлы: {ids_filename}, {ifc_filename}"
        app.logger.info(msg)

        # Текущее время
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        # Временные файлы
        with tempfile.NamedTemporaryFile(suffix=".xml", dir=TEMP_FOLDER, delete=False) as tmp_ids:
            file_ids.save(tmp_ids.name)
            tmp_ids_path = tmp_ids.name

        with tempfile.NamedTemporaryFile(suffix=".ifc", dir=TEMP_FOLDER, delete=False) as tmp_ifc:
            file_ifc.save(tmp_ifc.name)
            tmp_ifc_path = tmp_ifc.name

        try:
            # --- Определение типа файла проверок ---
            if ids_filename.lower().endswith('.ids'):
                validation_result = validate_ids_ifc(tmp_ids_path, tmp_ifc_path)
            elif ids_filename.lower().endswith('.xlsx'):
                validation_result = validate_excel(tmp_ids_path, tmp_ifc_path)
            else:
                return jsonify({"error": "Неподдерживаемый формат файла проверок"}), 400

            # Добавляем метаданные
            validation_result.update({
                "ids_filename": ids_filename,
                "ifc_filename": ifc_filename,
                "timestamp": now
            })

            # Генерация отчёта
            filename = generate_report(validation_result, REPORT_TEMPLATE_PATH, RESULT_FOLDER)
            report_url = url_for('serve_report', filename=filename, _external=True)

            msg = f"Валидация успешно выполнена для файлов: {ids_filename}, {ifc_filename}. Отчёт: {filename}"
            app.logger.info(msg)
            return jsonify({"report_url": report_url})

        finally:
            os.unlink(tmp_ids_path)
            os.unlink(tmp_ifc_path)

    except Exception as e:
        msg = f"Ошибка валидации: {str(e)}"
        app.logger.error(msg)
        app.logger.error(traceback.format_exc())
        return jsonify({"error": msg}), 500


@app.route('/reports/<filename>')
def serve_report(filename):
    app.logger.info(f"Пользователь запрашивает отчёт: {filename}")
    return send_file(Path(RESULT_FOLDER) / filename)


@app.route('/download/html/<filename>')
def download_html(filename):
    app.logger.info(f"Пользователь загружает HTML-отчёт: {filename}")
    return send_file(
        Path(RESULT_FOLDER) / filename,
        as_attachment=True,
        download_name=filename
    )


if __name__ == '__main__':
    app.run(debug=False)