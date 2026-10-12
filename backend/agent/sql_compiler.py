from typing import List, Tuple, Optional, Any
from dataclasses import dataclass
from backend.agent.intent_schema import IntentModel, OperationEnum, LayerEnum

@dataclass
class CompiledSQL:
    sql: str
    params: List[Any]


class SQLCompiler:
    """
    Deterministic compiler that translates a validated IntentModel into
    safe, parameterized SQL queries with $1, $2, ... placeholders.
    """

    ALLOWED_TABLES = {
        LayerEnum.structures: "structures",
        LayerEnum.terrain: "terrain",
        LayerEnum.roads: "roads",
        LayerEnum.vegetation: "vegetation",
    }

    def compile(self, intent: IntentModel) -> Optional[CompiledSQL]:
        if intent.operation == OperationEnum.UNKNOWN:
            return None

        table_name = self.ALLOWED_TABLES.get(intent.layer, "structures")
        conditions: List[str] = []
        params: List[Any] = []
        param_idx = 1

        # Base Select statement
        select_clause = f"""
            SELECT id, project_id, class as class_name, ST_AsGeoJSON(footprint) as footprint,
                   height_m, area_m2, region, splat_bbox, original_height_m, version
            FROM {table_name}
        """.strip()

        if intent.filter:
            # Min height filter
            if intent.filter.min_height_m is not None:
                conditions.append(f"height_m >= ${param_idx}")
                params.append(float(intent.filter.min_height_m))
                param_idx += 1

            # Max height filter
            if intent.filter.max_height_m is not None:
                conditions.append(f"height_m <= ${param_idx}")
                params.append(float(intent.filter.max_height_m))
                param_idx += 1

            # Region filter
            if intent.filter.region:
                conditions.append(f"LOWER(region) = LOWER(${param_idx})")
                params.append(intent.filter.region.strip().lower())
                param_idx += 1

        # If operation is SELECT_REGION or QUERY_HEIGHT with no conditions specified
        where_clause = ""
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)

        order_clause = " ORDER BY height_m DESC"
        full_sql = f"{select_clause}{where_clause}{order_clause};"

        return CompiledSQL(sql=full_sql, params=params)

    def compile_extrude_targets(self, intent: IntentModel) -> Optional[CompiledSQL]:
        """
        Compiles the query that finds the target structures to be edited/extruded.
        """
        table_name = self.ALLOWED_TABLES.get(intent.layer, "structures")
        conditions: List[str] = []
        params: List[Any] = []
        param_idx = 1

        if intent.filter:
            if intent.filter.min_height_m is not None:
                conditions.append(f"height_m >= ${param_idx}")
                params.append(float(intent.filter.min_height_m))
                param_idx += 1
            if intent.filter.max_height_m is not None:
                conditions.append(f"height_m <= ${param_idx}")
                params.append(float(intent.filter.max_height_m))
                param_idx += 1
            if intent.filter.region:
                conditions.append(f"LOWER(region) = LOWER(${param_idx})")
                params.append(intent.filter.region.strip().lower())
                param_idx += 1

        where_clause = ""
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)

        sql = f"""
            SELECT id, project_id, class as class_name, ST_AsGeoJSON(footprint) as footprint,
                   height_m, area_m2, region, splat_bbox, original_height_m, version
            FROM {table_name}{where_clause}
            ORDER BY id ASC;
        """.strip()

        return CompiledSQL(sql=sql, params=params)


sql_compiler = SQLCompiler()

