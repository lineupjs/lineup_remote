import re

class NumberFilter:
  def __init__(self, dump):
    self.min = dump['min']
    self.max = dump['max']
    self.filter_missing = dump['filterMissing']

  def to_sql(self, column):
    args = dict()
    if self.min is not None and self.max is not None:
      sql = '{0} between :{0}_min and {0}_max'
      args[column + '_min'] = self.min
      args[column + '_max'] = self.max
    elif self.min is not None:
      sql = '{0} >= :{0}_min'
      args[column + '_min'] = self.min
    elif self.max is not None:
      sql = '{0} <= :{0}_max'
      args[column + '_max'] = self.max
    if self.filter_missing:
      sql = '({0} is not null AND ' + sql + ')'
    return sql.format(column), args


class MappingFunction:
  def __init__(self, dump):
    self.type = dump['type']
    self.domain = dump['domain']
    self.range = dump['range']

  def to_query(self, column):
    return '{c.type}_mapping({column}, {c.domain[0]}, {c.domain[1]}, {c.range[0]}, {c.range[1]})'.format(column=column, c=self)


class DateGrouper:
  def __init__(self, dump):
    self.granularity = dump['granularity']
    self.circular = dump['circular']


class CategoricalFilter:
  def __init__(self, dump):
    self.filter = dump['filter']
    self.filter_missing = dump['filterMissing']

  def to_sql(self, column):
    args = {column : self.filter}
    sql = '{0} = any(:{0})'
    if self.filter_missing:
      sql = '({0} is not null AND ' + sql + ')'
    return sql.format(column), args


class StringFilter:
  def __init__(self, dump):
    self.filter = dump

  def to_sql(self, column):
    if self.filter == '__FILTER_MISSING':
      return '({0} is not null AND {0} != ""'.format(column), dict()

    if self.filter.startswith('REGEX:'):
      return '{0} ~ {0}'.format(column), {column: self.filter[6:]}

    return 'lower({0}) = {0}'.format(column), {column: self.filter.lower()}


class ColumnDump:
  def __init__(self, dump, column=None, type=None):
    self.id = dump['id']
    self.desc = dump['desc']
    self.column = column
    self.type = type
    self.filter = None

  def to_filter(self):
    return self.filter.to_sql(self.column) if self.filter else None


class NumberColumnDump(ColumnDump):
  def __init__(self, dump, column):
    super(NumberColumnDump, self).__init__(dump, column, 'number')
    self.map = MappingFunction(dump['map'])
    self.filter = NumberFilter(dump['filter']) if dump.get('filter') else None
    self.group_sort_method = dump['groupSortMethod']
    self.stratify_thresholds = dump['stratifyThresholds'] if dump.get('stratifyThresholds') else None
    self.mapped_column = self.map.to_query(self.column)


class DateColumnDump(ColumnDump):
  def __init__(self, dump, column):
    super(DateColumnDump, self).__init__(dump, column, 'date')
    self.filter = NumberFilter(dump['filter']) if dump.get('filter') else None
    self.grouper = DateGrouper(dump['grouper']) if dump.get('grouper') else None


class CategoricalColumnDump(ColumnDump):
  def __init__(self, dump, column):
    super(CategoricalColumnDump, self).__init__(dump, column, 'categorical')
    self.filter = CategoricalFilter(dump['filter']) if dump.get('filter') else None


class StringColumnDump(ColumnDump):
  def __init__(self, dump, column):
    super(StringColumnDump, self).__init__(dump, column, 'string')
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
    return ColumnDump(dump, column, column_type)
  return ColumnDump(dump, None, desc['type'])


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

  def to_filter(self):
    fs = [f.to_filter() for f in self.filter if f.filter]
    args = dict()
    for f in fs:
      args.update(f[1])
    return ' AND '.join(f[0] for f in fs), args


  def to_sort(self):
    return ''  # TODO


def parse_ranking_dump(dump):
  return ServerRankingDump(dump)
