import refactor

import ast
import re
import sys
import uuid


def decorate_fns(src, decorator):
    # Function to return annotated body
    def indented_replace(txt, node:ast.AST):
        p = '^.*$'
        s = f'{decorator}\n' + ' ' * node.col_offset + '\\g<0>'
        return re.sub(p, s, txt, flags=re.DOTALL)
    # Search and replace
    out = refactor.load(src) \
        .xpath('//FunctionDef') \
        .map_fn(indented_replace)
    #
    return out


class ArgReplacer:
    def __init__(self, args, kwargs):
        self.arg_idx = 0
        self.args = args
        self.kwargs = kwargs
    def __call__(self, txt, node:ast.AST):
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
    out = refactor.load(src) \
        .xpath(f'//FunctionDef[@name="{func_name}"]') \
        .map_str(r'^(.+?):(.+)$', r'\1 -> {}:\2'.format(ret), flags=re.DOTALL)
    # Add type to args
    r = refactor.Refactor()
    r.loads(out)
    out = r.xpath(f'//FunctionDef[@name="{func_name}"]//arg') \
        .map_fn(ArgReplacer(args, kwargs))
    #
    return out




