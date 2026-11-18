"""Fail-closed SQL subset. Both generated and reference SQL pass through this guard."""
import re
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from .schema import SCHEMA, allowed_columns

MAX_ROWS = 100
MAX_SQL_LENGTH = 6000


class ReportError(Exception):
    """A message safe to display or save; never wrap raw provider/driver errors."""


class UnsafeSQL(ReportError):
    pass


class NoAnswer(ReportError):
    pass


# A positive allowlist also rejects new SQLGlot node types until reviewed.
ALLOWED_NODES = frozenset("""
Select From Table Identifier TableAlias Column Alias Literal Star Distinct
Join Where And Or Not EQ NEQ GT GTE LT LTE Is Null Boolean Like ILike
Between In Paren Group Having Order Ordered Limit Count Sum Avg Min Max
Round Coalesce Nullif CurrentDate CurrentTimestamp TimestampTrunc DateTrunc
Extract Cast DataType Interval Var Add Sub Mul Div Neg
""".split())
ALLOWED_TYPES = {"DATE", "TIMESTAMP", "TIMESTAMPTZ", "INT", "BIGINT", "DECIMAL", "DOUBLE", "TEXT"}
DATE_PARTS = {"YEAR", "MONTH", "DAY", "WEEK", "QUARTER", "HOUR", "MINUTE", "SECOND", "DOW", "DOY", "EPOCH"}


def extract_sql(raw):
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_SQL_LENGTH + 20:
        raise UnsafeSQL("Модель жарамды қысқа SQL қайтармады.")
    text = raw.strip()
    fence = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", text, re.I | re.S)
    return fence.group(1).strip() if fence else text


def validate_sql(sql):
    if not isinstance(sql, str) or not sql.strip() or len(sql) > MAX_SQL_LENGTH:
        raise UnsafeSQL("SQL ұзындығы жарамсыз.")
    try:
        queries = sqlglot.parse(sql, read="postgres")
    except (SqlglotError, RecursionError):
        raise UnsafeSQL("SQL құрылымы жарамсыз.") from None
    if len(queries) != 1 or not isinstance(queries[0], exp.Select):
        raise UnsafeSQL("Тек бір SELECT сұранысына рұқсат.")
    tree = queries[0]
    nodes = list(tree.walk())
    if len(nodes) > 250 or sum(isinstance(n, exp.Select) for n in nodes) != 1:
        raise UnsafeSQL("Ішкі немесе күрделі сұраныстарға рұқсат жоқ.")
    for node in nodes:
        if type(node).__name__ not in ALLOWED_NODES or node.comments:
            raise UnsafeSQL("Бұл SQL әрекетіне немесе функциясына рұқсат жоқ.")
        if isinstance(node, exp.Identifier) and not re.fullmatch(r"[a-z_][a-z0-9_]*", node.name):
            raise UnsafeSQL("Кесте, баған және бүркеншік атаулар латын әріптерімен жазылады.")
        if isinstance(node, exp.Literal) and len(str(node.this)) > 200:
            raise UnsafeSQL("SQL мәні тым ұзын.")
        if isinstance(node, exp.Star) and not isinstance(node.parent, exp.Count):
            raise UnsafeSQL("SELECT * орнына нақты бағандарды көрсетіңіз.")
        if isinstance(node, exp.DataType):
            if node.this.value not in ALLOWED_TYPES or node.expressions:
                raise UnsafeSQL("Бұл түрге айналдыруға рұқсат жоқ.")
        if isinstance(node, exp.Var) and str(node.this).upper() not in DATE_PARTS:
            raise UnsafeSQL("Күн аралығы жарамсыз.")
    if (len(tree.expressions) == 1 and isinstance(tree.expressions[0], exp.Literal)
            and tree.expressions[0].this == "NO_ANSWER" and not list(tree.find_all(exp.Table))):
        raise NoAnswer("Бұл сұраққа деректер бойынша жауап беру мүмкін емес. Тек есеп сұраңыз.")
    tables = list(tree.find_all(exp.Table))
    columns = allowed_columns()
    if not tables or len(tables) > 3:
        raise UnsafeSQL("Тек емхананың рұқсат етілген есеп кестелерін қолданыңыз.")
    aliases = {}
    for table in tables:
        if (not isinstance(table.this, exp.Identifier) or table.name not in columns
                or table.catalog or table.db not in {"", SCHEMA}
                or any(table.args.get(k) for k in ("pivots", "sample", "version", "when", "only"))):
            raise UnsafeSQL("Бұл кестеге қол жеткізуге рұқсат жоқ.")
        alias = table.alias_or_name
        if alias in aliases or (table.args.get("alias") and table.args["alias"].args.get("columns")):
            raise UnsafeSQL("Кесте бүркеншік атауы бірегей болуы керек.")
        aliases[alias] = columns[table.name]
    for join in tree.args.get("joins", []):
        if (join.side not in {"", "LEFT"} or join.kind not in {"", "INNER"}
                or not isinstance(join.args.get("on"), exp.EQ)
                or not all(isinstance(v, exp.Column) for v in (join.args["on"].this, join.args["on"].expression))):
            raise UnsafeSQL("JOIN тек бағандардың теңдігі арқылы орындалады.")
    output_aliases = {e.alias for e in tree.expressions if e.alias}
    for column in tree.find_all(exp.Column):
        if column.db or column.catalog:
            raise UnsafeSQL("Баған жолы жарамсыз.")
        if column.table:
            valid = column.table in aliases and column.name in aliases[column.table]
        elif column.name in output_aliases and column.find_ancestor(exp.Order, exp.Group):
            valid = True
        else:
            valid = sum(column.name in names for names in aliases.values()) == 1
        if not valid:
            raise UnsafeSQL("Баған жоқ, екіұшты немесе оған рұқсат берілмеген.")
    limit = tree.args.get("limit")
    size = MAX_ROWS
    if limit:
        value = limit.expression
        if not isinstance(value, exp.Literal) or value.is_string or not re.fullmatch(r"[0-9]+", str(value.this)):
            raise UnsafeSQL("LIMIT бүтін оң сан болуы керек.")
        size = min(int(value.this), MAX_ROWS)
    tree = tree.limit(size)
    for table in tree.find_all(exp.Table):
        table.set("db", exp.to_identifier(SCHEMA))
    return tree.sql(dialect="postgres")
