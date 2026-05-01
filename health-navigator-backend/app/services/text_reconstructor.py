def reconstruct_text_from_ocr_result(result: dict) -> str:
    lines = []
    current_line = ""

    for image in result.get("images", []):
        for field in image.get("fields", []):
            text = field.get("inferText", "")
            if not text:
                continue

            if current_line:
                current_line += " " + text
            else:
                current_line = text

            if field.get("lineBreak", False):
                lines.append(current_line)
                current_line = ""

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)