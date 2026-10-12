"""Stable internal identifiers for students without a school enrollment."""
import hashlib
import unicodedata


def student_fields(name, class_code, enrollment="", shift=""):
    name, class_code = name.strip(), class_code.strip()
    enrollment, shift = enrollment.strip(), shift.strip()
    if not name or not class_code:
        raise ValueError("Preencha nome e turma.")
    if len(name) > 180 or len(class_code) > 20 or len(enrollment) > 32 or len(shift) > 30:
        raise ValueError("Um dos campos ultrapassa o tamanho permitido.")
    if not enrollment:
        # Stable across reimports, case and spacing differences. Homonyms in
        # one class must be distinguished using an explicit enrollment/code.
        normalized = [" ".join(unicodedata.normalize("NFKC", value).casefold().split())
                      for value in (name, class_code)]
        digest = hashlib.sha256("\0".join(normalized).encode("utf-8")).hexdigest()
        enrollment = "AUTO-" + digest[:27]
    return dict(name=name, class_code=class_code, enrollment=enrollment,
                shift=shift or "Não informado")
