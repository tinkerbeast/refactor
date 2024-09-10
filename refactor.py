import ast
import enum
import re

from lxml.builder import E
from lxml import etree as ET


def load(src: str):
    # Read and parse source file.
    with open(src, 'r') as fd:
        data = fd.read()
    return Refactor(data)

def loads(data: str):
    return Refactor(data)


class Selection:

    def __init__(self, xml, path: str):
        self.xml_filter = xml.xpath(path)

    def select(self, path: str):
        xout = []
        for x in self.xml_filter:
            xout.extend(x.xpath(path))
        self.xml_filter = xout
        return self

    def filter_fn(self, fn):
        self.xml_filter = [x for x in self.xml_filter if fn(x)]
        return self

    def map_fn(self, fn):
        self.xml_filter = [fn(x) for x in self.xml_filter]
        return self

    def union(self, sel):
        self.xml_filter = list(set(self.xml_filter).union(set(sel.xml_filter)))
        return self

    def intersection(self, sel):
        self.xml_filter = list(set(self.xml_filter).intersection(set(sel.xml_filter)))
        return self

    def difference(self, sel):
        self.xml_filter = list(set(self.xml_filter).difference(set(sel.xml_filter)))
        return self
    
    def dump_xml(self):
        for x in self.xml_filter:
            print(ET.tostring(x, pretty_print=True).decode('utf-8'))
        return self


class ChangeType(enum.Enum):
    # NOTE: Collation algorithm depens on absoulute values of these
    PREPEND = 1
    SUBSTITUTE = 2


class Refactor:

    def __init__(self, data: str):
        self.ast_idx = 0
        self.ast_map = dict()
        self.changes = []
        self.ast_idxs = []
        #
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

    def lxml_builder_fn_(self, node: ast.AST | str, children):
        # print(node, type(node))
        # TODO(rishin): Remove this - This check validates that new AST 
        #       parsing mechanism doesn't have None children.
        if any([c is None for c in children]): raise ValueError("None children")
        # Return equivalent XML node.
        if isinstance(node, str):
            # A str type node represents container tags for nodes with list 
            # type attributes (eg. a function body).
            return E('_' + node, *children)
        elif isinstance(node, ast.AST):
            self.ast_idx += 1
            self.ast_map[self.ast_idx] = node
            attrs = {'idx_': str(self.ast_idx)}
            # Populate the attributes of the node.
            for f in node._fields:
                sub_node = getattr(node, f)
                if isinstance(sub_node, ast.AST) or isinstance(sub_node, list):
                    pass
                else:
                    # TODO(rishin): Document when we hit this.
                    attrs[f] = str(sub_node)
            # Populate AST context like line number, column, etc.
            for a in node._attributes:
                attrs[a] = str(getattr(node, a))
            # For the xml node.
            ntype = type(node).__name__
            return E(ntype, *children, **attrs)
        else:
            raise ValueError('Invalid parser implementation')

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
        # Check for overlaps in substitue type changes
        # TODO(rishin): Should change overlap be calculated during addition?
        overlaps = [0] * len(self.data)
        sub_changes = [c for c in self.changes if c[3] == ChangeType.SUBSTITUTE]
        for b, e, _, _ in sub_changes:
            overlaps[b] += 1
            overlaps[e] -= 1
        for i in range(1, len(overlaps)):
            overlaps[i] += overlaps[i - 1]
            if overlaps[i] > 1:
                raise ValueError('Overlapping changes cannot be processed', i, overlaps[i])
        # Sort the changes by being offset and chage type (PREPEND < SUBSTITUTE)
        sorted_changes = sorted(self.changes, key=lambda x: (x[0], x[3].value))
        # Make the changes
        last_e = 0
        prev = ''
        for b, e, out, c in sorted_changes:
            prev += self.data[last_e:b]
            if c == ChangeType.SUBSTITUTE:
                prev += out
                last_e = e
            elif c == ChangeType.PREPEND:
                prev += out
                last_e = b
            else:
                raise ValueError("Unsupported operatin")
        prev += self.data[last_e:]
        self.changes = []
        return prev

    def modify_prepend_map(self, fn) -> str:
        flat_ast = self.form_ast_list_from_xml_()
        for i in flat_ast:
            node = i[0]
            if not hasattr(node, 'lineno'):
                raise ValueError('Node cannot be converted to text')
            b = self.line_map[node.lineno - 1] + node.col_offset
            e = self.line_map[node.end_lineno - 1] + node.end_col_offset
            out = fn(self.text(node), node)
            self.changes.append((b, e, out, ChangeType.PREPEND))
        return self

    def modify_sub(self, pattern, repl, count=0, flags=0) -> str:
        # TODO(rishin): Combine the modify_sub functions to reduce code.
        flat_ast = self.form_ast_list_from_xml_()
        for i in flat_ast:
            node = i[0]
            if not hasattr(node, 'lineno'):
                raise ValueError('Node cannot be converted to text')
            b = self.line_map[node.lineno - 1] + node.col_offset
            e = self.line_map[node.end_lineno - 1] + node.end_col_offset
            out = re.sub(pattern, repl, self.text(node), count, flags)
            self.changes.append((b, e, out, ChangeType.SUBSTITUTE))
        return self

    def modify_sub_map(self, fn) -> str:
        flat_ast = self.form_ast_list_from_xml_()
        for i in flat_ast:
            node = i[0]
            if not hasattr(node, 'lineno'):
                raise ValueError('Node cannot be converted to text')
            b = self.line_map[node.lineno - 1] + node.col_offset
            e = self.line_map[node.end_lineno - 1] + node.end_col_offset
            out = fn(self.text(node), node)
            self.changes.append((b, e, out, ChangeType.SUBSTITUTE))
        return self

    def select(self, path: str):
        return Selection(self.xml, path)

    def filter(self, sel: Selection):
        self.ast_idxs = [int(e.attrib['idx_']) for e in sel.xml_filter]
        return self        
    
    def execute(self):
        return self.collate_changes_()
    
    def form_ast_list_from_xml_(self):
        return [[self.ast_map[int(i)]] for i in self.ast_idxs]

    def dump(self):
        flat_ast = self.form_ast_list_from_xml_()
        for idx in range(len(flat_ast)):
            i = flat_ast[idx]
            if not isinstance(i[0], ast.alias):
                print(f'>{idx}: {i} {self.text(i[0])}<')
            else:
                print(f'>{idx}: {i}: ???<')
        return self
