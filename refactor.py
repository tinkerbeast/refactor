import ast
import re

from lxml.builder import E
from lxml import etree as ET


def load(src: str):
    r = Refactor()
    r.load(src)
    return r


class Refactor:

    def __init__(self):
        self.ast_idx = 0
        self.ast_map = dict()
        self.changes = []
        self.xml_filter = []

    def load(self, src: str):
        # Read and parse source file.
        with open(src, 'r') as fd:
            data = fd.read()
        return self.loads(data)

    def loads(self, data: str):
        self.data = data
        self.ast = ast.parse(self.data, mode='exec')
        # Map line numbers to byte index.
        o = {}
        lines = self.data.split('\n')
        prev_len = 0
        for i in range(len(lines)):
            o[i] = prev_len
            prev_len += 1 + len(lines[i])
        self.line_map = o
        self.line_cnt = len(lines)
        # Walk the AST
        self.xml = self.walk_ast_bottom_up_(self.ast, self.lxml_builder_fn_)

    def text(self, node: ast.AST) -> str:
        if not hasattr(node, 'lineno'):
            raise ValueError('Node cannot be converted to text')
        b = self.line_map[node.lineno - 1] + node.col_offset
        e = self.line_map[node.end_lineno - 1] + node.end_col_offset
        return self.data[b:e]

    def sub_(self, pattern, repl, node: ast.AST, count=0, flags=0) -> None:
        if not hasattr(node, 'lineno'):
            raise ValueError('Node cannot be converted to text')
        b = self.line_map[node.lineno - 1] + node.col_offset
        e = self.line_map[node.end_lineno - 1] + node.end_col_offset
        # print((pattern, repl, self.text(node)))
        out = re.sub(pattern, repl, self.text(node), count, flags)
        # print((b, e, out))
        self.changes.append((b, e, out))

    def lxml_builder_fn_(self, node: ast.AST | str, children):
        # print(node, type(node))
        # Filter out nodes which can't be converted to text.
        # TODO(rishigos): Group AST token into similar groups
        if type(node) in (
            ast.Add, ast.And, ast.BitAnd, ast.BitOr, ast.BitXor,
            ast.comprehension, ast.match_case, ast.withitem,
            ast.Del, ast.Div, ast.Eq, ast.FloorDiv, ast.Gt, ast.GtE, ast.In,
            ast.Invert, ast.Is, ast.IsNot, ast.Load, ast.LShift, ast.Lt, ast.LtE,
            ast.Mod, ast.Mult, ast.Not, ast.NotEq, ast.NotIn, ast.Or,
            ast.Pow, ast.RShift, ast.Store, ast.Sub, ast.UAdd, ast.USub,
        ):
            return None
        # Remove None from children
        children = [c for c in children if c is not None]
        if isinstance(node, str):
            return E('_' + node, *children)
        elif isinstance(node, ast.AST):
            # print(node._attributes) # TODO: decide on line numbers
            self.ast_idx += 1
            self.ast_map[self.ast_idx] = node
            attrs = {'idx_': str(self.ast_idx)}
            # Populate the attributes of the node.
            for f in node._fields:
                sub_node = getattr(node, f)
                if isinstance(sub_node, ast.AST) or isinstance(sub_node, list):
                    pass
                else:
                    attrs[f] = str(sub_node)
            #
            for a in node._attributes:
                attrs[a] = str(getattr(node, a))
            # For the xml node
            ntype = type(node).__name__
            return E(ntype, *children, **attrs)
        else:
            raise ValueError('Invalid parser implementation')

    def walk_ast_top_down_(self, node, fn, parent, level):
        # TODO(rishigos): Remove this - Kept for historic reasons
        # if isinstance(node, ast.AST):
        #    if parent is not None:
        #        fn(node, parent, level)
        #    for name in node._fields:
        #        value = getattr(node, name, None)
        #        if value is not None:
        #            self.walk_ast_top_down_(value, fn, node, level + 1)
        # elif isinstance(node, list):
        #    for n in node:
        #        self.walk_ast_top_down_(n, fn, parent, level + 1)
        # else:
        #    pass # terminal string values of tokens
        pass

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
                pass  # Primitive attributes.
        return fn(node, fn_children)

    def collate_changes_(self):
        # Check for overlaps
        overlaps = [0] * len(self.data)
        for b, e, _ in self.changes:
            overlaps[b] += 1
            overlaps[e] -= 1
        for i in range(1, len(overlaps)):
            overlaps[i] += overlaps[i - 1]
            if overlaps[i] > 1:
                raise ValueError('Overlapping changes cannot be processed')
        sorted_changes = sorted(self.changes, key=lambda x: x[0])
        last_e = 0
        prev = ''
        for b, e, out in sorted_changes:
            # print(f'{prev}><{out}')
            prev += self.data[last_e:b]
            prev += out
            last_e = e
        prev += self.data[last_e:]
        self.changes = []
        return prev

    def map_str(self, pattern, repl, count=0, flags=0) -> str:
        flat_ast = self.form_ast_list_from_xml_()
        for i in flat_ast:
            self.sub_(pattern, repl, i[0], count, flags)
        new_data = self.collate_changes_()
        return new_data

    def map_fn(self, fn) -> str:
        flat_ast = self.form_ast_list_from_xml_()
        for i in flat_ast:
            node = i[0]
            if not hasattr(node, 'lineno'):
                raise ValueError('Node cannot be converted to text')
            b = self.line_map[node.lineno - 1] + node.col_offset
            e = self.line_map[node.end_lineno - 1] + node.end_col_offset
            out = fn(self.text(node), node)
            self.changes.append((b, e, out))
        new_data = self.collate_changes_()
        return new_data

    def xpath(self, path):
        xout = []
        if self.xml_filter:
            for x in self.xml_filter:
                xout.extend(x.xpath(path))
        else:
            xout = self.xml.xpath(path)
        self.xml_filter = xout
        return self

    def form_ast_list_from_xml_(self):
        ast_idxs = [int(e.attrib['idx_']) for e in self.xml_filter]
        return [[self.ast_map[int(i)]] for i in ast_idxs]

    def dump_xml(self):
        if self.xml_filter:
            for x in self.xml_filter:
                print(ET.tostring(x, pretty_print=True).decode('utf-8'))
        else:
            print(ET.tostring(self.xml, pretty_print=True).decode('utf-8'))
        return self

    def dump(self):
        flat_ast = self.form_ast_list_from_xml_()
        for idx in range(len(flat_ast)):
            i = flat_ast[idx]
            if not isinstance(i[0], ast.alias):
                print(f'>{idx}: {i} {self.text(i[0])}<')
            else:
                print(f'>{idx}: {i}: ???<')
        return self
