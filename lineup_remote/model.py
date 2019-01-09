import re

class NumberFilter:
  def __init__(self, dump):
    self.min = dump['min']
    self.max = dump['max']
    self.filter_missing = dump['filterMissing']


class MappingFunction:
  def __init__(self, dump):
    self.type = dump['type']
    self.domain = dump['domain']
    self.range = dump['range']


class DateGrouper:
  def __init__(self, dump):
    self.granularity = dump['granularity']
    self.circular = dump['circular']


class CategoricalFilter:
  def __init__(self, dump):
    self.filter = dump['filter']
    self.filter_missing = dump['filterMissing']


class StringFilter:
  def __init__(self, dump):
    self.filter = dump


class ColumnDump:
  def __init__(self, dump, column = None):
    self.id = dump['id']
    self.desc = dump['desc']
    self.column = column


class NumberColumnDump(ColumnDump):
  def __init__(self, dump, column):
    super(NumberColumnDump, self).__init__(dump, column)
    self.map = MappingFunction(dump['map'])
    self.filter = NumberFilter(dump['filter']) if dump.get('filter') else None
    self.group_sort_method = dump['groupSortMethod']
    self.stratify_thresholds = dump['stratifyThresholds'] if dump.get('stratifyThresholds') else None


class DateColumnDump(ColumnDump):
  def __init__(self, dump, column):
    super(DateColumnDump, self).__init__(dump, column)
    self.filter = NumberFilter(dump['filter']) if dump.get('filter') else None
    self.grouper = DateGrouper(dump['grouper']) if dump.get('grouper') else None


class CategoricalColumnDump(ColumnDump):
  def __init__(self, dump, column):
    super(CategoricalColumnDump, self).__init__(dump, column)
    self.filter = CategoricalFilter(dump['filter']) if dump.get('filter') else None


class StringColumnDump(ColumnDump):
  def __init__(self, dump, column):
    super(StringColumnDump, self).__init__(dump, column)
    self.filter = StringFilter(dump['filter']) if dump.get('filter') else None
    self.group_criteria = dump.get('groupCriteria')


def parse_column_dump(dump):
  desc = dump['desc']
  if isinstance(desc, str):
    column_type, column = desc.split('@')
    if column_type == 'number':
      return NumberColumnDump(dump, column)
    if column_type == 'string':
      return StringColumnDump(dump, column)
    if column_type == 'categorical':
      return CategoricalColumnDump(dump, column)
    if column_type == 'date':
      return DateColumnDump(dump, column)
  return ColumnDump(dump)


class SortCriteria:
  def __init__(self, dump):
    self.col = parse_column_dump(dump['col'])
    self.asc = dump['asc']


class ServerRankingDump:
  def __init__(self, dump):
    self.filter = [parse_column_dump(d) for d in dump.get('filter', [])]
    self.sort_criteria = [SortCriteria(d) for d in dump.get('sortCriteria', [])]
    self.group_criteria = [parse_column_dump(d) for d in dump.get('groupCriteria', [])]
    self.group_sort_criteria = [SortCriteria(d) for d in dump.get('groupSortCriteria', [])]


def parse_ranking_dump(dump):
  return ServerRankingDump(dump)
