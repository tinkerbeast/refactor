# refactor

Meta language and tool for large scale refactoring.

# Getting started

### Installation

Getting lxml dependency.
```
python3 -m venv venv
source venv/bin/activate
python3 -m pip install lxml
```

### Usage

Transform all functions with at least 3 arguments, but not having name hello with `@test_dec` decorator.
```
# Load the temp.py file into the refactoring unit.
r = refactor.load("temp.py")
# Selection for all functions with at least 3 arguments.
s1 = r.select(f'//FunctionDef').filter_fn(lambda x: len(x.xpath('./arguments/_args/arg')) > 2)
# Selection for all functions with name hello.
s2 = r.select(f'//FunctionDef[@name="hello"]')
# Selection s1 removes all functions with name hello.
s1.difference(s2)
# Stage changes where a decorator is added.
r.filter(s1).modify_prepend_map(lambda n: '@test_dec\n' + ' ' * n.col_offset)
# Apply all changes.
out = r.execute()
```

### Using recipes

Modify a function like `somefunc(x, y, z=1)` to `somefunc(x: str, y: float, z: int=1) -> None`
```
import recipes
recipes.annotate_fn_params("temp.py", "somefunc", ["str", "float"], {"z": "int"}, "None")
```