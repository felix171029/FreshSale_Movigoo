"""
Historial genérico de cambios (tareas, citas y notas de deals), mismo esquema que deal_history.

Cada tabla de historial guarda una fila por campo vigilado que cambia. Nunca se borra.
tipo: 'inicial' (estado al activar el historial), 'nuevo', 'cambio', 'eliminado'.
Las funciones deben llamarse antes del MERGE/DELETE y dentro de la misma transacción.
"""

from typing import Dict, List, Optional, Tuple

# Normalización a texto para comparar sin cambios falsos (las tablas usan DATETIME y las temporales DATETIME2)
_TXT = "CONVERT(NVARCHAR(MAX), {col})"
_FECHA = "CONVERT(NVARCHAR(MAX), {col}, 120)"
_BIT = "CONVERT(NVARCHAR(MAX), ISNULL({col}, 0))"


def _f(campo: str, plantilla: str = _TXT) -> Tuple[str, str]:
    return campo, plantilla.format(col="{a}." + campo)


# Configuración por entidad: tabla, historial, claves (columna en la tabla, columna en el historial),
# campos vigilados, hora del cambio según Freshsales y qué guardar como valor anterior al eliminar.
ENTIDADES: Dict[str, dict] = {
    "tasks": {
        "tabla": "freshsale.tasks",
        "historial": "freshsale.task_history",
        "claves": [("id", "task_id")],
        "campos": [
            _f("title"), _f("description"), _f("due_date", _FECHA), _f("status"), _f("owner_id"),
            _f("targetable_type"), _f("targetable_id"), _f("completed_at", _FECHA), _f("is_deleted", _BIT),
        ],
        "resumen": "{a}.title",
    },
    "appointments": {
        "tabla": "freshsale.appointments",
        "historial": "freshsale.appointment_history",
        "claves": [("id", "appointment_id")],
        "campos": [
            _f("title"), _f("description"), _f("from_date", _FECHA), _f("end_date", _FECHA), _f("location"),
            _f("owner_id"), _f("targetable_type"), _f("targetable_id"), _f("is_deleted", _BIT),
        ],
        "resumen": "{a}.title",
    },
    "deal_notes": {
        "tabla": "freshsale.deal_notes",
        "historial": "freshsale.deal_note_history",
        "claves": [("id", "note_id"), ("deal_id", "deal_id")],
        "campos": [_f("description"), _f("creator_id")],
        "resumen": "{a}.description",
    },
}


def ddl() -> List[str]:
    """CREATE de las tablas de historial (idempotente)."""
    sentencias = []
    for cfg in ENTIDADES.values():
        nombre = cfg["historial"].split(".")[1]
        claves = ",\n".join(f"{col} BIGINT NOT NULL" for _, col in cfg["claves"])
        indice = ", ".join(col for _, col in cfg["claves"])
        sentencias.append(f"""IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'{cfg["historial"]}') AND type = 'U')
                CREATE TABLE {cfg["historial"]} (
                    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    {claves},
                    campo VARCHAR(50) NOT NULL,
                    valor_anterior NVARCHAR(MAX) NULL,
                    valor_nuevo NVARCHAR(MAX) NULL,
                    tipo VARCHAR(10) NOT NULL,
                    fecha_cambio_fs DATETIME2 NULL,
                    updated_at_fs DATETIME2 NULL,
                    detectado_en DATETIME2 NOT NULL DEFAULT SYSDATETIME()
                )""")
        sentencias.append(
            f"IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_{nombre}_registro' "
            f"AND object_id = OBJECT_ID(N'{cfg['historial']}')) "
            f"CREATE INDEX IX_{nombre}_registro ON {cfg['historial']} ({indice}, campo, detectado_en)")
    sentencias.append(_VISTA)
    return sentencias


# vw_actividad_history: tareas, citas y notas en una sola vista, con el deal al que pertenecen
# y nombres de usuario en vez de IDs (owner_id, creator_id)
_TEXTO = """COALESCE(CASE WHEN h.campo IN ('owner_id', 'creator_id')
                     THEN (SELECT display_name FROM freshsale.users WHERE id = TRY_CONVERT(BIGINT, h.{col})) END,
                h.{col})"""
_VISTA = f"""CREATE OR ALTER VIEW freshsale.vw_actividad_history AS
                WITH a AS (
                    SELECT 'tarea' AS entidad, h.id, h.task_id AS registro_id,
                           CASE WHEN x.targetable_type = 'Deal' THEN x.targetable_id END AS deal_id,
                           x.title AS titulo, h.campo, h.tipo, h.valor_anterior, h.valor_nuevo,
                           h.fecha_cambio_fs, h.updated_at_fs, h.detectado_en
                    FROM freshsale.task_history h LEFT JOIN freshsale.tasks x ON x.id = h.task_id
                    UNION ALL
                    SELECT 'cita', h.id, h.appointment_id,
                           CASE WHEN x.targetable_type = 'Deal' THEN x.targetable_id END,
                           x.title, h.campo, h.tipo, h.valor_anterior, h.valor_nuevo,
                           h.fecha_cambio_fs, h.updated_at_fs, h.detectado_en
                    FROM freshsale.appointment_history h LEFT JOIN freshsale.appointments x ON x.id = h.appointment_id
                    UNION ALL
                    SELECT 'nota', h.id, h.note_id, h.deal_id, NULL, h.campo, h.tipo, h.valor_anterior, h.valor_nuevo,
                           h.fecha_cambio_fs, h.updated_at_fs, h.detectado_en
                    FROM freshsale.deal_note_history h
                )
                SELECT h.entidad, h.id, h.registro_id, h.deal_id, d.name AS deal_name, h.titulo, h.campo, h.tipo,
                       h.valor_anterior, h.valor_nuevo,
                       {_TEXTO.format(col='valor_anterior')} AS valor_anterior_texto,
                       {_TEXTO.format(col='valor_nuevo')} AS valor_nuevo_texto,
                       h.fecha_cambio_fs, h.updated_at_fs, h.detectado_en
                FROM a h
                LEFT JOIN freshsale.deals d ON d.id = h.deal_id"""


def _join(cfg: dict, a: str, b: str) -> str:
    return " AND ".join(f"{a}.{col} = {b}.{col}" for col, _ in cfg["claves"])


def _join_hist(cfg: dict, a: str) -> str:
    return " AND ".join(f"h.{hcol} = {a}.{col}" for col, hcol in cfg["claves"])


def registrar_cambios(cursor, entidad: str, temp: str, alcance_eliminados: Optional[str] = None) -> Dict[str, int]:
    """
    Compara `temp` (lo que llegó de Freshsales) con la tabla final y escribe el historial.
    `alcance_eliminados`: condición sobre la tabla final (alias t) que delimita los registros
    que debían venir completos en `temp`; los que falten se registran como 'eliminado'.
    Sin alcance (carga incremental) no se detectan eliminados aquí (lo hace el reconciler).
    """
    cfg = ENTIDADES[entidad]
    stats = {"inicial": 0, "nuevo": 0, "cambio": 0, "eliminado": 0}
    hist_cols = ", ".join(hcol for _, hcol in cfg["claves"])
    insert = f"""INSERT INTO {cfg["historial"]}
        ({hist_cols}, campo, valor_anterior, valor_nuevo, tipo, fecha_cambio_fs, updated_at_fs, detectado_en)"""

    def values(alias: str) -> str:
        return ",\n".join(f"('{campo}', {expr.format(a=alias)})" for campo, expr in cfg["campos"])

    def claves(alias: str) -> str:
        return ", ".join(f"{alias}.{col}" for col, _ in cfg["claves"])

    cambios = ",\n".join(
        f"('{campo}', {expr.format(a='t')}, {expr.format(a='s')})" for campo, expr in cfg["campos"])

    cursor.execute("SELECT SYSDATETIME()")
    ahora = cursor.fetchone()[0]

    # Punto de partida: registros que ya estaban y aún no tienen historial
    cursor.execute(f"""{insert}
        SELECT {claves('t')}, v.campo, NULL, v.valor, 'inicial', t.updated_at, t.updated_at, %s
        FROM {cfg["tabla"]} t
        CROSS APPLY (VALUES {values('t')}) v(campo, valor)
        WHERE v.valor IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM {cfg["historial"]} h WHERE {_join_hist(cfg, 't')})
    """, (ahora,))
    stats["inicial"] = cursor.rowcount

    # Registros nuevos
    cursor.execute(f"""{insert}
        SELECT {claves('s')}, v.campo, NULL, v.valor, 'nuevo', s.updated_at, s.updated_at, %s
        FROM {temp} s
        CROSS APPLY (VALUES {values('s')}) v(campo, valor)
        WHERE v.valor IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM {cfg["tabla"]} t WHERE {_join(cfg, 't', 's')})
    """, (ahora,))
    stats["nuevo"] = cursor.rowcount

    # Cambios (EXCEPT compara bien los NULL)
    cursor.execute(f"""{insert}
        SELECT {claves('s')}, v.campo, v.anterior, v.nuevo, 'cambio', s.updated_at, s.updated_at, %s
        FROM {temp} s
        JOIN {cfg["tabla"]} t ON {_join(cfg, 't', 's')}
        CROSS APPLY (VALUES {cambios}) v(campo, anterior, nuevo)
        WHERE EXISTS (SELECT v.anterior EXCEPT SELECT v.nuevo)
    """, (ahora,))
    stats["cambio"] = cursor.rowcount

    if alcance_eliminados:
        stats["eliminado"] = registrar_eliminados(
            cursor, entidad,
            f"({alcance_eliminados}) AND NOT EXISTS (SELECT 1 FROM {temp} s WHERE {_join(cfg, 't', 's')})",
            ahora)

    return stats


def registrar_eliminados(cursor, entidad: str, condicion: str, ahora=None) -> int:
    """Una fila 'eliminado' (campo 'registro', valor anterior = título o texto) por cada registro de la
    tabla final (alias t) que cumple `condicion`. Llamar antes del DELETE, en la misma transacción."""
    cfg = ENTIDADES[entidad]
    if ahora is None:
        cursor.execute("SELECT SYSDATETIME()")
        ahora = cursor.fetchone()[0]
    hist_cols = ", ".join(hcol for _, hcol in cfg["claves"])
    claves = ", ".join(f"t.{col}" for col, _ in cfg["claves"])
    cursor.execute(f"""INSERT INTO {cfg["historial"]}
            ({hist_cols}, campo, valor_anterior, valor_nuevo, tipo, fecha_cambio_fs, updated_at_fs, detectado_en)
        SELECT {claves}, 'registro', CONVERT(NVARCHAR(MAX), {cfg["resumen"].format(a='t')}), NULL,
               'eliminado', NULL, t.updated_at, %s
        FROM {cfg["tabla"]} t
        WHERE {condicion}
    """, (ahora,))
    return cursor.rowcount
