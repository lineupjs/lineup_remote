import re
from typing import Any, cast, Dict, Optional, Tuple


class NumberFilter:
    def __init__(self, dump: Dict[str, Any]):
        self.min = dump["min"]
        self.max = dump["max"]
        self.filter_missing = dump["filterMissing"]

    def to_sql(self, column: str) -> Tuple[str, Dict[str, float]]:
        args = {}
        if self.min is not None and self.max is not None:
            sql = "{0} between :{0}_min and :{0}_max"
            args[column + "_min"] = self.min
            args[column + "_max"] = self.max
        elif self.min is not None:
            sql = "{0} >= :{0}_min"
            args[column + "_min"] = self.min
        elif self.max is not None:
            sql = "{0} <= :{0}_max"
            args[column + "_max"] = self.max
        if self.filter_missing:
            sql = "({0} is not null AND " + sql + ")"
        return sql.format(column), args


class MappingFunction:
    def __init__(self, dump: Dict[str, Any]):
        self.type = dump["type"]
        self.domain = dump["domain"]
        self.range = dump["range"]

    def to_query(self, column: str):
        return "map_value({column}, '{c.type}', {c.domain[0]}, {c.domain[1]}, {c.range[0]}, {c.range[1]})".format(column=column, c=self)


class DateGrouper:
    def __init__(self, dump: Dict[str, Any]):
        self.granularity = dump["granularity"]
        self.circular = dump["circular"]


class CategoricalFilter:
    def __init__(self, dump: Dict[str, Any]):
        self.filter = dump["filter"]
        self.filter_missing = dump["filterMissing"]

    def to_sql(self, column: str):
        args = {column: self.filter}
        sql = "{0} = any(:{0})"
        if self.filter_missing:
            sql = "({0} is not null AND " + sql + ")"
        return sql.format(column), args


class StringFilter:
    def __init__(self, dump: str):
        self.filter = dump

    def to_sql(self, column: str):
        if self.filter == "__FILTER_MISSING":
            return '({0} is not null AND {0} != ""'.format(column), {}

        if self.filter.startswith("REGEX:"):
            return "{0} ~ {0}".format(column), {column: self.filter[6:]}

        return "lower({0}) = {0}".format(column), {column: self.filter.lower()}


class ColumnDump:
    def __init__(self, dump: Dict[str, Any], column: str = "", type: str = ""):
        self.id = dump["id"]
        self.desc = dump["desc"]
        self.column = column
        self.type = type
        self.filter: Any = None

    def to_filter(self):
        return self.filter.to_sql(self.column) if self.filter else None


class NumberColumnDump(ColumnDump):
    def __init__(self, dump: Dict[str, Any], column: str):
        super(NumberColumnDump, self).__init__(dump, column, "number")
        self.map = MappingFunction(dump["map"])
        self.filter = NumberFilter(dump["filter"]) if dump.get("filter") else None
        self.group_sort_method = dump["groupSortMethod"]
        self.stratify_thresholds = dump["stratifyThresholds"] if dump.get("stratifyThresholds") else None
        assert self.column is not None
        self.mapped_column = self.map.to_query(self.column)


class DateColumnDump(ColumnDump):
    def __init__(self, dump: Dict[str, Any], column: str):
        super(DateColumnDump, self).__init__(dump, column, "date")
        self.filter = NumberFilter(dump["filter"]) if dump.get("filter") else None
        self.grouper = DateGrouper(dump["grouper"]) if dump.get("grouper") else None


class CategoricalColumnDump(ColumnDump):
    def __init__(self, dump: Dict[str, Any], column: str):
        super(CategoricalColumnDump, self).__init__(dump, column, "categorical")
        self.filter = CategoricalFilter(dump["filter"]) if dump.get("filter") else None


class StringColumnDump(ColumnDump):
    def __init__(self, dump: Dict[str, Any], column: str):
        super(StringColumnDump, self).__init__(dump, column, "string")
        self.filter = StringFilter(dump["filter"]) if dump.get("filter") else None
        self.group_criteria = dump.get("groupCriteria")


class CompositeColumnDump(ColumnDump):
    def __init__(self, dump: Dict[str, Any]):
        super(CompositeColumnDump, self).__init__(dump, "", dump["desc"]["type"])
        self.children = [parse_column_dump(c) for c in dump.get("children", [])]


class StackColumnDump(CompositeColumnDump):
    def __init__(self, dump: Dict[str, Any]):
        super(StackColumnDump, self).__init__(dump)
        self.total = dump["width"]


class NestedColumnDump(CompositeColumnDump):
    def __init__(self, dump: Dict[str, Any]):
        super(NestedColumnDump, self).__init__(dump)


def parse_column_dump(dump: Dict[str, Any]):
    desc = dump["desc"]
    if isinstance(desc, str):
        column_type, column = desc.split("@")
        if column_type == "number":
            return NumberColumnDump(dump, column)
        if column_type == "string":
            return StringColumnDump(dump, column)
        if column_type == "categorical":
            return CategoricalColumnDump(dump, column)
        if column_type == "date":
            return DateColumnDump(dump, column)
        return ColumnDump(dump, column, column_type)
    # object dump so a composite for example
    column_type = desc.get("type")
    if column_type == "stack":
        return StackColumnDump(dump)
    elif column_type == "nested":
        return NestedColumnDump(dump)
    return ColumnDump(dump, "", desc["type"])


class ComputeColumnDump:
    def __init__(self, dump: ColumnDump, type: str):
        self.dump = dump
        self.type = type


def parse_compute_column_dump(dump: Dict[str, Any]):
    return ComputeColumnDump(parse_column_dump(dump["dump"]), dump["type"])


class SortCriteria:
    def __init__(self, dump: Dict[str, Any]):
        self.col = parse_column_dump(dump["col"])
        self.asc = dump["asc"]

    def to_clause(self):
        if self.asc:
            return self.col.column
        return self.col.column + " DESC"


class ServerRankingDump:
    def __init__(self, dump: Dict[str, Any]):
        self.filter = [parse_column_dump(d) for d in dump.get("filter", [])]
        self.sort_criteria = [SortCriteria(d) for d in dump.get("sortCriteria", [])]
        self.group_criteria = [parse_column_dump(d) for d in dump.get("groupCriteria", [])]
        self.group_sort_criteria = [SortCriteria(d) for d in dump.get("groupSortCriteria", [])]

        # TODO support nested columns, support boolean columns
        # TODO support stacked columns

    def to_filter(self):
        fs = [f.to_filter() for f in self.filter if f.filter]
        args = dict()
        for f in fs:
            args.update(f[1])
        return " AND ".join(f[0] for f in fs), args

    def to_where(self, group: Optional[str] = None):
        filter_sql, args = self.to_filter()
        where = "WHERE " + filter_sql if filter_sql else ""
        if group:
            args["groupname"] = group
            if not where:
                where = "WHERE {0} = :groupname".format(self.to_group_name())
            else:
                where += " AND {0} = :groupname".format(self.to_group_name())
        return where, args

    def to_sort(self):
        clauses = [c.to_clause() for c in self.sort_criteria]
        if not clauses:
            return ""
        return "ORDER BY " + ", ".join(clauses)

    def to_group_by(self):
        clauses = [c.column for c in self.group_criteria]
        if not clauses:
            return ""
        return "GROUP BY " + ", ".join(clauses)

    def to_group_name(self):
        if not self.group_criteria:
            return "'Default group'"
        return "CONCAT({0})".format(", ".join("COALESCE({0}, 'Missing values')".format(g.column) for g in self.group_criteria))


def parse_ranking_dump(dump: Dict[str, Any]):
    return ServerRankingDump(dump)

