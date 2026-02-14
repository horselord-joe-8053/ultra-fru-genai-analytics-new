#!/usr/bin/env python3
"""
Parse SQL file into individual statements for RDS Data API (one statement per execute).

Usage:
    python tools/sql/parse_sql_statements.py <schema_file>
"""
import re
import sys


def parse_sql_statements(sql_content: str) -> list[str]:
    """Parse SQL content into individual statements."""
    content = re.sub(r'--.*?$', '', sql_content, flags=re.MULTILINE)
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    sql = ' '.join(lines)

    statements = []
    current = []
    paren_depth = 0
    in_string = False
    string_char = None
    i = 0

    while i < len(sql):
        char = sql[i]
        if char in ("'", '"') and (i == 0 or sql[i - 1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
        elif not in_string:
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ';' and paren_depth == 0:
                stmt = ''.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                i += 1
                while i < len(sql) and sql[i] in ' \t\n':
                    i += 1
                continue
        current.append(char)
        i += 1

    if current:
        stmt = ''.join(current).strip()
        if stmt:
            statements.append(stmt)
    return statements


def main():
    if len(sys.argv) != 2:
        print("Usage: parse_sql_statements.py <schema_file>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        content = f.read()
    for stmt in parse_sql_statements(content):
        print(stmt)


if __name__ == "__main__":
    main()
