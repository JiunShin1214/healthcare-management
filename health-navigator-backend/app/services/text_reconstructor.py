def _get_field_y(field: dict) -> float:
    vertices = field.get("boundingPoly", {}).get("vertices", [])
    if not vertices:
        return 0
    return sum(v.get("y", 0) for v in vertices) / len(vertices)


def _get_field_x(field: dict) -> float:
    vertices = field.get("boundingPoly", {}).get("vertices", [])
    if not vertices:
        return 0
    return sum(v.get("x", 0) for v in vertices) / len(vertices)


def reconstruct_text_from_ocr_result(result: dict) -> str:
    if not isinstance(result, dict):
        return ""

    all_lines = []

    for image in result.get("images", []):
        fields = image.get("fields", [])
        valid_fields = []

        for field in fields:
            text = field.get("inferText", "")
            if not text:
                continue

            valid_fields.append({
                "text": text.strip(),
                "x": _get_field_x(field),
                "y": _get_field_y(field),
            })

        if not valid_fields:
            continue

        valid_fields.sort(key=lambda f: (f["y"], f["x"]))

        lines = []
        current_line = []
        current_y = None
        y_threshold = 12

        for field in valid_fields:
            if current_y is None:
                current_y = field["y"]
                current_line.append(field)
                continue

            if abs(field["y"] - current_y) <= y_threshold:
                current_line.append(field)
            else:
                current_line.sort(key=lambda f: f["x"])
                lines.append(" ".join(f["text"] for f in current_line))

                current_line = [field]
                current_y = field["y"]

        if current_line:
            current_line.sort(key=lambda f: f["x"])
            lines.append(" ".join(f["text"] for f in current_line))

        all_lines.extend(lines)

    return "\n".join(all_lines)