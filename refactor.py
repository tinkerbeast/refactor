import ast
import re

from lxml.builder import E


def load(src: str):
    r = Refactor()
    r.load(src)
    return r


class Refactor:

    def __init__(self):
        self.ast_idx = 0
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
        # Walk the AST
        self.xml = self.walk_ast_bottom_up_(self.ast, self.lxml_builder_fn_)

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

    def lxml_builder_fn_(self, node: ast.AST|str, children):
        # Filter out nodes which can't be converted to text.
        if type(node) in (ast.Add, ast.And, ast.arguments, ast.BitAnd,
                ast.BitOr, ast.BitXor, ast.comprehension, ast.Del, ast.Div,
                ast.Eq, ast.FloorDiv, ast.Gt, ast.GtE, ast.In, ast.Invert,
                ast.Is, ast.IsNot, ast.Load, ast.LShift, ast.Lt, ast.LtE,
                ast.match_case, ast.Mod, ast.Mult, ast.Not, ast.NotEq,
                ast.NotIn, ast.Or, ast.Pow, ast.RShift, ast.Store, ast.Sub,
                ast.UAdd, ast.USub, ast.withitem):
            return None
        # Remove None from children
        children = [c for c in children if c is not None]
        if isinstance(node, str):
            return E('_' + node, *children)
        else:
            #print(node._attributes) # TODO: decide on line numbers
            ntype = type(node).__name__
            self.ast_idx += 1
            attrs = {'idx_': str(self.ast_idx)}
            for f in node._fields:
                sub_node = getattr(node, f)
                if isinstance(sub_node, ast.AST) or isinstance(sub_node, list):
                    pass
                else:
                    attrs[f] = str(sub_node)
            # For the xml node
            #print(ntype)
            return E(ntype, *children, **attrs)

    def print_fn_(self, node, parent, level):
        if type(node) in (ast.Add, ast.And, ast.arguments, ast.BitAnd,
                ast.BitOr, ast.BitXor, ast.comprehension, ast.Del, ast.Div,
                ast.Eq, ast.FloorDiv, ast.Gt, ast.GtE, ast.In, ast.Invert,
                ast.Is, ast.IsNot, ast.Load, ast.LShift, ast.Lt, ast.LtE,
                ast.match_case, ast.Mod, ast.Mult, ast.Not, ast.NotEq,
                ast.NotIn, ast.Or, ast.Pow, ast.RShift, ast.Store, ast.Sub,
                ast.UAdd, ast.USub, ast.withitem):
            pass
        else:
            print('{}{}'.format('  ' * level, type(node).__name__))

    def walk_ast_top_down_(self, node, fn, parent, level):
        if isinstance(node, ast.AST):
            if parent is not None:
                fn(node, parent, level)
            for name in node._fields:
                value = getattr(node, name, None)
                if value is not None:
                    self.walk_ast_top_down_(value, fn, node, level + 1)
        elif isinstance(node, list):
            for n in node:
                self.walk_ast_top_down_(n, fn, parent, level + 1)
        else:
            pass # terminal string values of tokens

    def walk_ast_bottom_up_(self, node, fn):
        if not isinstance(node, ast.AST):
            raise ValueError('AST walking error')
        children = {name: getattr(node, name, None) for name in node._fields}
        fn_children = []
        for name, c in children.items():
            if isinstance(c, list):
                fn_sub_children = [self.walk_ast_bottom_up_(i, fn) for i in c]
                fn_children.append(fn(name, fn_sub_children))
            elif isinstance(c, ast.AST):
                fn_children.append(self.walk_ast_bottom_up_(c, fn))
            else:
                pass # Primitive attributes.
        return fn(node, fn_children)


