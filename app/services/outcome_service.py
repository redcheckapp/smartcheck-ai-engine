from datetime import datetime
from typing import Optional

from app.schemas import TaskOutcomePayload
from app.services.vector_store import upsert_task_outcome
from app.services.pattern_service import update_subject_pattern


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


def register_task_outcome(payload: TaskOutcomePayload) -> None:
    fecha_limite = _parse_date(payload.fechaLimite)
    fecha_completado = _parse_date(payload.fechaCompletado)

    dias_retraso = None
    if fecha_limite and fecha_completado:
        dias_retraso = (fecha_completado.date() - fecha_limite.date()).days

    siguio_orden_ia = None
    if payload.ordenSugeridoIA is not None and payload.ordenReal is not None:
        siguio_orden_ia = payload.ordenSugeridoIA == payload.ordenReal

    context_text = _build_context_text(payload, dias_retraso, siguio_orden_ia)

    metadata = {
        "taskId": payload.id,
        "asignatura": payload.asignatura,
        "completada": payload.completada,
    }
    if dias_retraso is not None:
        metadata["diasRetraso"] = dias_retraso
        metadata["cumplioPlazo"] = dias_retraso <= 0
    if siguio_orden_ia is not None:
        metadata["siguioOrdenIA"] = siguio_orden_ia

    upsert_task_outcome(
        task_id=str(payload.id),
        user_id=payload.userId,
        context_text=context_text,
        metadata=metadata,
    )

    update_subject_pattern(payload.userId, payload.asignatura)


def _build_context_text(
    payload: TaskOutcomePayload, dias_retraso: Optional[int], siguio_orden_ia: Optional[bool]
) -> str:
    partes = [f"Tarea '{payload.titulo}'"]
    if payload.asignatura:
        partes.append(f"de la asignatura '{payload.asignatura}'")
    if payload.fechaLimite:
        partes.append(f"con fecha límite {payload.fechaLimite}.")

    if payload.completada and payload.fechaCompletado:
        if dias_retraso is None:
            partes.append(f"Resultado: completada el {payload.fechaCompletado}.")
        elif dias_retraso > 0:
            partes.append(
                f"Resultado: completada el {payload.fechaCompletado}, con {dias_retraso} día(s) de retraso."
            )
        elif dias_retraso == 0:
            partes.append(f"Resultado: completada el {payload.fechaCompletado}, justo en la fecha límite.")
        else:
            partes.append(
                f"Resultado: completada el {payload.fechaCompletado}, con {abs(dias_retraso)} día(s) de antelación."
            )
    else:
        partes.append("Resultado: aún no completada.")

    if siguio_orden_ia is not None:
        if siguio_orden_ia:
            partes.append(
                f"El usuario siguió el orden sugerido por SmartCheck AI (posición {payload.ordenSugeridoIA})."
            )
        else:
            partes.append(
                f"SmartCheck AI había sugerido la posición {payload.ordenSugeridoIA}, "
                f"pero el usuario la abordó en la posición {payload.ordenReal}."
            )

    return " ".join(partes)
