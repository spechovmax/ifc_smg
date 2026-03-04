# services/excel_service.py

import ifcopenshell
import pandas as pd
from pathlib import Path
from datetime import datetime


def validate_excel(file_path: str, ifc_path: str):
    """
    Читает Excel, определяет типы элементов и параметры из заголовков столбцов.
    Проверяет IFC-модель по этим правилам.
    """

    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        raise ValueError(f"Не удалось прочитать Excel: {e}")

    # Строим правила из заголовков
    rules = {}

    for _, row in df.iterrows():
        elem_type = None
        params = []

        for col in df.columns:
            value = row[col]
            if isinstance(value, str) and value.startswith("Ifc"):
                elem_type = value
            elif isinstance(value, str) and value not in ["", "nan"]:
                params.append(value)

        if elem_type:
            if elem_type not in rules:
                rules[elem_type] = []
            rules[elem_type].extend(params)

    # Убираем дубликаты
    for k in rules:
        rules[k] = list(set(rules[k]))

    # Открываем IFC модель
    try:
        model = ifcopenshell.open(ifc_path)
    except Exception as e:
        raise ValueError(f"Не удалось открыть IFC-файл: {e}")

    results_by_type = {}

    for entity in model:
        if hasattr(entity, "is_a"):
            elem_type = entity.is_a()
            if elem_type in rules:
                if elem_type not in results_by_type:
                    results_by_type[elem_type] = []

                missing = []
                for param in rules[elem_type]:
                    value = getattr(entity, param, None)
                    if value is None or value == "":
                        missing.append(param)

                results_by_type[elem_type].append({
                    "GlobalId": getattr(entity, "GlobalId", "N/A"),
                    "Name": getattr(entity, "Name", "Unnamed"),
                    "MissingFields": missing
                })

    # Сводка
    summary = {}
    for elem_type, items in results_by_type.items():
        total = len(items)
        incomplete = sum(1 for item in items if item["MissingFields"])
        summary[elem_type] = {
            "Total": total,
            "Incomplete": incomplete,
            "Details": items
        }

    return {
        "specifications": [{
            "name": "Excel Specification",
            "description": "Проверки из Excel файла",
            "status": "failed" if any(v["Incomplete"] > 0 for v in summary.values()) else "passed",
            "checks_passed": f"{len(summary) - sum(1 for v in summary.values() if v['Incomplete'] > 0)} / {len(summary)}",
            "elements_passed": f"{sum(v['Total'] - v['Incomplete'] for v in summary.values())} / {sum(v['Total'] for v in summary.values())}",
            "requirements": [
                {
                    "text": f"{item_type} — {', '.join(reqs)}",
                    "status": "failed" if data["Incomplete"] > 0 else "passed",
                    "failed_guids": [e["GlobalId"] for e in data["Details"] if e["MissingFields"]],
                    "failed_names": [f"{e['Name']} ({item_type})" for e in data["Details"] if e["MissingFields"]],
                }
                for item_type, data in summary.items()
                for reqs in [rules.get(item_type, [])]
            ],
        }],
        "total_elements": sum(len(data["Details"]) for data in summary.values()),
        "ids_filename": Path(file_path).name,
        "ifc_filename": Path(ifc_path).name,
        "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }