import ast
import re

def load(src: str):
    r = Refactor()
    r.load(src)
    return r

class Refactor:

    def __init__(self):
        self.filters_fn = []
        self.filters_param = []
        self.filter_idx = 0
        self.changes = []

    def load(self, src:str):
        # Read and parse source file.
        with open(src, 'r') as fd:
            data = fd.read()
        return self.loads(data)

    def loads(self, data:str):
        self.data = data
        self.ast = ast.parse(self.data, mode='exec')
        # Map line numbers to byte index.
        o = {}
        lines = self.data.split('\n')
        prev_len = 0
        for i in range(len(lines)):
            o[i] = prev_len
            prev_len += 1 + len(lines[i])
        self.line_map  = o
        self.line_cnt = len(lines)

    def text(self, node:ast.AST) -> str:
        if not hasattr(node, 'lineno'):
            raise ValueError('Node cannot be converted to text')
        b = self.line_map[node.lineno - 1] + node.col_offset
        e = self.line_map[node.end_lineno - 1] + node.end_col_offset
        return self.data[b:e]

    def sub(pattern, repl, node:ast.AST, count=0, flags=0) -> None:
        if not hasattr(node, 'lineno'):
            raise ValueError('Node cannot be converted to text')
        b = self.line_map[node.lineno - 1] + node.col_offset
        e = self.line_map[node.end_lineno - 1] + node.end_col_offset
        out = re.sub(pattern, repl, self.text(node), count, flags)
        self.changes.append((b, e, out))

    def filter_(self, node: ast.AST, filter_type, filter_fn):
        # Filter out nodes which can't be converted to text.
        if type(node) in (ast.Add, ast.And, ast.arguments, ast.BitAnd,
                ast.BitOr, ast.BitXor, ast.comprehension, ast.Del, ast.Div,
                ast.Eq, ast.FloorDiv, ast.Gt, ast.GtE, ast.In, ast.Invert,
                ast.Is, ast.IsNot, ast.Load, ast.LShift, ast.Lt, ast.LtE,
                ast.match_case, ast.Mod, ast.Mult, ast.Not, ast.NotEq,
                ast.NotIn, ast.Or, ast.Pow, ast.RShift, ast.Store, ast.Sub,
                ast.UAdd, ast.USub, ast.withitem):
            return
        #
        else:
            raise ValueError('Filter type not supported yet')

    def filt(self, node_type, fn): # TODO(rishin): Return type must be str
        self.filters_type.append(node_type)
        self.filters_fn.append(fn)
        return self

    def walk_ast_(self, node, fn, parent, level):
        if isinstance(node, ast.AST):
            if parent is not None:
                fn(node, parent, level)
            for name in node._fields:
                value = getattr(node, name, None)
                if value is not None:
                    self.walk_ast_(value, fn, node, level + 1)
        elif isinstance(node, list):
            for n in node:
                self.walk_ast_(n, fn, parent, level + 1)
        else:
            pass # terminal string values of tokens

    def process_(self, node:ast.AST, parent:ast.AST, level:int):
        filter_type = self.filters_type[self.filter_idx]
        filter_fn = self.filters_type[self.filter_idx]
        self.filter_(filters_type, filter_fn)

    def process():
        filters_cnt = len(self.filters_type)
        while self.filter_idx < filters_cnt:
            self.walk_ast_(self.ast, self.process_, None, 0)
            new_data = self.collate_changes_()
            self.loads(new_data)
            self.filter_idx += 1
