from app.services.vector_store import get_task_outcomes, upsert_user_pattern


def update_subject_pattern(user_id: str, asignatura: str) -> None:
    """Recalcula y reescribe el patrón agregado de una asignatura a partir de
    TODOS sus registros de task_outcomes hasta ahora (no incremental: relee y
    recomputa entero cada vez — el volumen por usuario/asignatura es pequeño,
    así que no compensa la complejidad de un acumulador incremental).
    """
    if not asignatura:
        return

    resultados = get_task_outcomes(user_id, asignatura)
    metadatas = resultados.get("metadatas") or []
    if not metadatas:
        return

    total = len(metadatas)
    completadas = [m for m in metadatas if m.get("completada")]
    n_completadas = len(completadas)
    tasa_completado = round((n_completadas / total) * 100)

    retrasos = [m["diasRetraso"] for m in completadas if "diasRetraso" in m]
    retraso_promedio = round(sum(retrasos) / len(retrasos), 1) if retrasos else None

    seguimientos = [m["siguioOrdenIA"] for m in metadatas if "siguioOrdenIA" in m]
    tasa_seguimiento_ia = round((sum(seguimientos) / len(seguimientos)) * 100) if seguimientos else None

    context_text = _build_pattern_text(
        asignatura, total, tasa_completado, retraso_promedio, tasa_seguimiento_ia
    )

    metadata = {
        "asignatura": asignatura,
        "totalRegistros": total,
        "tasaCompletado": tasa_completado,
    }
    if retraso_promedio is not None:
        metadata["retrasoPromedioDias"] = retraso_promedio
    if tasa_seguimiento_ia is not None:
        metadata["tasaSeguimientoIA"] = tasa_seguimiento_ia

    upsert_user_pattern(
        pattern_id=f"{user_id}:{asignatura}",
        user_id=user_id,
        context_text=context_text,
        metadata=metadata,
    )


def _build_pattern_text(
    asignatura: str,
    total: int,
    tasa_completado: int,
    retraso_promedio: float | None,
    tasa_seguimiento_ia: int | None,
) -> str:
    partes = [
        f"Patrón de rendimiento en '{asignatura}' (basado en {total} tarea(s) registrada(s)): "
        f"tasa de finalización del {tasa_completado}%."
    ]

    if retraso_promedio is not None:
        if retraso_promedio > 0:
            partes.append(f"Cuando completa tareas de esta asignatura, suele llevar un retraso medio de {retraso_promedio} día(s).")
        elif retraso_promedio < 0:
            partes.append(f"Suele completar las tareas de esta asignatura con {abs(retraso_promedio)} día(s) de antelación de media.")
        else:
            partes.append("Suele completar las tareas de esta asignatura justo en la fecha límite.")

    if tasa_seguimiento_ia is not None:
        partes.append(f"Ha seguido el orden sugerido por SmartCheck AI en esta asignatura el {tasa_seguimiento_ia}% de las veces.")

    return " ".join(partes)
