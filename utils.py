import refactor

import ast
import re
import sys
import uuid


def decorate_fns(src, decorator):
    # Function to return annotated body
    def indented_replace(txt, node: ast.AST):
        p = '^.*$'
        s = f'{decorator}\n' + ' ' * node.col_offset + '\\g<0>'
        return re.sub(p, s, txt, flags=re.DOTALL)

    # Search and replace
    r = refactor.load(src)
    s = r.select('//FunctionDef')
    return r.filter(s).map_fn(indented_replace)    


class ArgReplacer:
    def __init__(self, args, kwargs):
        self.arg_idx = 0
        self.args = args
        self.kwargs = kwargs

    def __call__(self, txt, node: ast.AST):
        p = '^.*$'
        if self.arg_idx < len(self.args):
            s = '\\g<0>: {}'.format(self.args[self.arg_idx])
            self.arg_idx += 1
            return re.sub(p, s, txt)
        else:
            s = '\\g<0>: {}'.format(self.kwargs[node.arg])
            return re.sub(p, s, txt)


def annotate_fn_params(src, func_name, args, kwargs, ret):
    # Add return type
    r = refactor.load(src)
    s = r.select(f'//FunctionDef[@name="{func_name}"]')
    out = r.filter(s).map_str(r'^(.+?):(.+)$', r'\1 -> {}:\2'.format(ret), flags=re.DOTALL)    
    # Add type to args
    r = refactor.loads(out)
    s = r.select(f'//FunctionDef[@name="{func_name}"]//arg')
    return r.filter(s).map_fn(ArgReplacer(args, kwargs))



def print_fn_def(node: lxml.etree._Element):
    names = [node.attrib["name"]]
    p = node.getparent()
    while p is not None:
        if p.tag in ("ClassDef", "FunctionDef"):
            names.append(p.attrib["name"])
        p = p.getparent()
    names.reverse()
    print('.'.join(names), node.attrib["idx_"])
    return node

def print_call_def_simple(node: lxml.etree._Element):
    enclosing = node.xpath("ancestor::FunctionDef[1]")
    print(node.attrib["id"], enclosing[0].attrib["idx_"] if enclosing else None)
    return node

def print_call_def_attr(node: lxml.etree._Element):
    enclosing = node.xpath("ancestor::FunctionDef[1]")
    print(node.attrib["attr"], enclosing[0].attrib["idx_"] if enclosing else None)
    return node

def form_db():
    print("Function defs and corresponding id")
    r = refactor.load("temp.py")
    s = (
        r.select("//FunctionDef")
        .map_fn(print_fn_def)
    )
    
    print("Calls and caller id")
    s = (
        r.select("//Call/Name")
        .map_fn(print_call_def_simple)
    )
    s = (
        r.select("//Call/Attribute")
        .map_fn(print_call_def_attr)
    )
