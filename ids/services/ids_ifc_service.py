# ids_ifc_service.py

from ifctester import ids
import ifcopenshell


def validate_ids_ifc(ids_path: str, ifc_path: str):
    """
    Валидирует модель IFC по спецификации IDS.
    Возвращает результаты в форматированном виде.
    """
    specification = ids.open(ids_path)
    ifc = ifcopenshell.open(ifc_path)
    specification.validate(ifc)

    result = {
        "specifications": [],
        "total_elements": len(ifc.by_type("IfcElement"))
    }

    for spec in specification.specifications:
        total_requirements = len(spec.requirements)
        passed_requirements = sum(1 for req in spec.requirements if req.status)

        applicable_entities = set(spec.applicable_entities)
        passed_entities = set()
        failed_entities = set()

        for req in spec.requirements:
            if hasattr(req, "passed_entities"):
                passed_entities.update(req.passed_entities)
            if hasattr(req, "failed_entities"):
                failed_entities.update(req.failed_entities)

        passed_count = len(passed_entities.intersection(applicable_entities))
        failed_count = len(applicable_entities) - passed_count

        requirements_data = []
        for req in spec.requirements:
            failed_guids = []
            failed_names = []

            if hasattr(req, "failed_entities") and req.failed_entities:
                for e in req.failed_entities:
                    if e.id() in ifc.guid_map:
                        failed_guids.append(ifc.guid_map[e.id()])
                    name = getattr(e, "Name", None) or getattr(e, "name", None) or "Без имени"
                    etype = getattr(e, "is_a", lambda: "Unknown")()
                    failed_names.append(f"{name} ({etype})")
            else:
                if not req.status:
                    failed_guids = ["Не найдены"]
                    failed_names = ["Не найдены элементы, не прошедшие проверку"]

            requirements_data.append({
                "text": req.to_string("requirement"),
                "status": "passed" if req.status else "failed",
                "failed_guids": failed_guids,
                "failed_names": failed_names,
            })

        spec_result = {
            "name": spec.name,
            "description": spec.description or "",
            "status": "passed" if spec.status else "failed",
            "checks_passed": f"{passed_requirements} / {total_requirements}",
            "elements_passed": f"{passed_count} / {len(spec.applicable_entities)}",
            "requirements": requirements_data,
        }

        result["specifications"].append(spec_result)

    return result