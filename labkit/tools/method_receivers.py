"""method_receivers — which method a call on an object reaches, read from
the annotations around it: `state.measured_of(pid).told(text)` reaches
`Measured.told` because `state` is annotated `AreaState` and
`AreaState.measured_of` returns `Measured`.

The part of the static call graph (`check_inventory.unit_references`) that
a name alone does not give. Never runs the code and never imports it; what
it knows of an object is the class its annotation names:

  - a parameter's annotation, `self` in a method
  - what a called function, method or property is annotated to return; a
    class called returns itself
  - an annotated field in a class body (a dataclass field), an annotated
    local
  - through `X | None` and `Optional[X]` (the class), `tuple[X, Y]` (by
    position, also when unpacked), and `list[X]`, `Sequence[X]` and their
    like (by `for`, a comprehension or an index)
  - a method or field of a base class, where the base is a class of the
    index

Its limits: an object without such an annotation is of no known class, and
a method called on it is not followed — a value out of a `dict`, an
unannotated return, a quoted annotation, a class from outside the package.
Where a base class is annotated and a subclass overrides the method, the
base's method is the one named. In `with X() as x` the name `x` is taken
for the `X`, whatever its `__enter__` returns. A name stands for every
class it was given anywhere in its unit (a nested function's parameters
included), so a name reused for two classes reaches the methods of both.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

#: annotation heads that hold many values of one shape
COLLECTIONS = frozenset(
    {"list", "set", "frozenset", "Sequence", "Iterable", "Iterator", "Collection"}
)
#: decorators that make a method read like a field
PROPERTY_DECORATORS = frozenset({"property", "cached_property"})


@dataclass(frozen=True)
class Instance:
    """An object of one of CLASSES (`module.Class`)."""

    classes: frozenset[str]


@dataclass(frozen=True)
class Each:
    """A collection whose members have the shape OF (None: not known)."""

    of: Shape | None


@dataclass(frozen=True)
class Parts:
    """A tuple of fixed length, ITEMS the shape at each position."""

    items: tuple[Shape | None, ...]


#: what an annotation tells of a value
Shape = Instance | Each | Parts


@dataclass(frozen=True)
class UnitIndex:
    """The units an object's class is looked up in.

    Attributes:
        units: `module.qualname` → the node of every function, class and
            method (`check_inventory.units` over all modules).
        refer_in: A unit → the function that tells which unit a name or
            `a.b` node names in that unit's module, or None.
    """

    units: Mapping[str, ast.AST]
    refer_in: Callable[[str], Callable[[ast.AST], str | None]]


def annotated_shape(
    annotation: ast.AST | None, unit: str, index: UnitIndex
) -> Shape | None:
    """The shape the ANNOTATION standing in UNIT's module tells, or None
    where it names no class of the package (the module docstring lists the
    forms read)."""
    a = annotation
    if isinstance(a, (ast.Name, ast.Attribute)):
        named = index.refer_in(unit)(a)
        if isinstance(index.units.get(named or ""), ast.ClassDef):
            return Instance(frozenset({named or ""}))
        return None
    if isinstance(a, ast.BinOp) and isinstance(a.op, ast.BitOr):
        return _merged(
            annotated_shape(a.left, unit, index),
            annotated_shape(a.right, unit, index),
        )
    if isinstance(a, ast.Subscript) and isinstance(a.value, ast.Name):
        inner = list(a.slice.elts) if isinstance(a.slice, ast.Tuple) else [a.slice]
        if a.value.id == "Optional":
            return annotated_shape(inner[0], unit, index)
        if a.value.id in COLLECTIONS:
            return Each(annotated_shape(inner[0], unit, index))
        if a.value.id == "tuple":
            if len(inner) == 2 and _is_ellipsis(inner[1]):
                return Each(annotated_shape(inner[0], unit, index))
            return Parts(tuple(annotated_shape(i, unit, index) for i in inner))
    return None


def _is_ellipsis(node: ast.AST) -> bool:
    """Is NODE the `...` of `tuple[X, ...]`?"""
    return isinstance(node, ast.Constant) and node.value is Ellipsis


def _merged(old: Shape | None, new: Shape | None) -> Shape | None:
    """What a name stands for after it was given OLD and then NEW: two
    objects are an object of either class; of any other pair the first
    known one stays."""
    if isinstance(old, Instance) and isinstance(new, Instance):
        return Instance(old.classes | new.classes)
    return old if old is not None else new


def _either(shapes: Iterable[Shape | None]) -> Shape | None:
    """The one shape for a value that has any of SHAPES."""
    out: Shape | None = None
    for s in shapes:
        out = _merged(out, s)
    return out


def class_and_bases(cls: str, index: UnitIndex) -> tuple[str, ...]:
    """The class CLS and the classes of the package it inherits from, the
    nearest first."""
    out: list[str] = []
    waiting = [cls]
    while waiting:
        c = waiting.pop(0)
        if c in out:
            continue
        out.append(c)
        node = index.units[c]
        assert isinstance(node, ast.ClassDef), f"{c} is no class"
        for base in node.bases:
            named = index.refer_in(c)(base)
            if isinstance(index.units.get(named or ""), ast.ClassDef):
                waiting.append(named or "")
    return tuple(out)


def method_named(cls: str, name: str, index: UnitIndex) -> str | None:
    """The unit of the method NAME an object of CLS has — its own or the
    nearest base's — or None."""
    for c in class_and_bases(cls, index):
        if f"{c}.{name}" in index.units:
            return f"{c}.{name}"
    return None


def field_shape(cls: str, name: str, index: UnitIndex) -> Shape | None:
    """The shape of the annotated field NAME in the body of CLS or of its
    nearest base that has it, or None."""
    for c in class_and_bases(cls, index):
        node = index.units[c]
        assert isinstance(node, ast.ClassDef), f"{c} is no class"
        for item in node.body:
            if (
                isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
                and item.target.id == name
            ):
                return annotated_shape(item.annotation, c, index)
    return None


def returned_shape(unit: str, index: UnitIndex) -> Shape | None:
    """What calling UNIT gives: an object of the class for a class, else
    the shape its return annotation tells."""
    node = index.units[unit]
    if isinstance(node, ast.ClassDef):
        return Instance(frozenset({unit}))
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return annotated_shape(node.returns, unit, index)
    return None


def is_property(unit: str, index: UnitIndex) -> bool:
    """Is UNIT a method read like a field (`PROPERTY_DECORATORS`)?"""
    node = index.units[unit]
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    names = {
        d.id
        if isinstance(d, ast.Name)
        else d.attr
        if isinstance(d, ast.Attribute)
        else ""
        for d in node.decorator_list
    }
    return bool(names & PROPERTY_DECORATORS)


@dataclass
class _Reading:
    """One unit being read: UNIT, the class around it (CLS, None for a
    function), the PACKAGE, and NAMES — what each local name stands for,
    filled by `_bind_names`."""

    unit: str
    cls: str | None
    index: UnitIndex
    names: dict[str, Shape]

    def methods_at(self, node: ast.Attribute) -> list[str]:
        """The methods `<object>.attr` at NODE names: one per class the
        object may be of that has the method; empty for an object of no
        known class."""
        on = self.shape_of(node.value)
        if not isinstance(on, Instance):
            return []
        found = (method_named(c, node.attr, self.index) for c in sorted(on.classes))
        return [m for m in found if m is not None]

    def shape_of(self, node: ast.AST) -> Shape | None:
        """The shape of the expression NODE, or None where no annotation
        tells it."""
        if isinstance(node, ast.Name):
            return self.names.get(node.id)
        if isinstance(node, ast.Await):
            return self.shape_of(node.value)
        if isinstance(node, ast.Call):
            return self._shape_of_call(node)
        if isinstance(node, ast.Attribute):
            return self._shape_of_attribute(node)
        if isinstance(node, ast.Subscript):
            return self._shape_of_item(node)
        return None

    def _shape_of_call(self, node: ast.Call) -> Shape | None:
        """What the call NODE gives: of a unit named, what it returns; of a
        method on an object, what that method returns."""
        named = self.index.refer_in(self.unit)(node.func)
        if named is not None:
            return returned_shape(named, self.index)
        if isinstance(node.func, ast.Attribute):
            return _either(
                returned_shape(m, self.index) for m in self.methods_at(node.func)
            )
        return None

    def _shape_of_attribute(self, node: ast.Attribute) -> Shape | None:
        """What `<object>.attr` at NODE holds: what a property returns, or
        the annotated field; None where NODE names a unit, not a value."""
        if self.index.refer_in(self.unit)(node) is not None:
            return None
        on = self.shape_of(node.value)
        if not isinstance(on, Instance):
            return None
        properties = [m for m in self.methods_at(node) if is_property(m, self.index)]
        return _either(
            [returned_shape(m, self.index) for m in properties]
            + [field_shape(c, node.attr, self.index) for c in sorted(on.classes)]
        )

    def _shape_of_item(self, node: ast.Subscript) -> Shape | None:
        """What `<value>[index]` at NODE holds: a member of a collection,
        or the part of a tuple at a literal position."""
        on = self.shape_of(node.value)
        if isinstance(on, Each):
            return on.of
        index = node.slice
        if (
            isinstance(on, Parts)
            and isinstance(index, ast.Constant)
            and isinstance(index.value, int)
            and 0 <= index.value < len(on.items)
        ):
            return on.items[index.value]
        return None

    def bind(self, target: ast.AST, shape: Shape | None) -> bool:
        """Give the name or tuple of names TARGET the SHAPE; True when a
        name now stands for more than before."""
        if shape is None:
            return False
        if isinstance(target, ast.Name):
            merged = _merged(self.names.get(target.id), shape)
            if merged is None or merged == self.names.get(target.id):
                return False
            self.names[target.id] = merged
            return True
        if (
            isinstance(target, (ast.Tuple, ast.List))
            and isinstance(shape, Parts)
            and len(target.elts) == len(shape.items)
        ):
            changed = [self.bind(t, s) for t, s in zip(target.elts, shape.items)]
            return any(changed)
        return False


def _bindings(reading: _Reading, n: ast.AST) -> list[tuple[ast.AST, Shape | None]]:
    """(target, shape) for what the statement or clause N gives a name: an
    assignment, an annotated local, `:=`, a loop or comprehension over a
    collection, `with … as`; empty for any other node."""
    if isinstance(n, ast.Assign):
        shape = reading.shape_of(n.value)
        return [(t, shape) for t in n.targets]
    if isinstance(n, ast.AnnAssign):
        return [(n.target, annotated_shape(n.annotation, reading.unit, reading.index))]
    if isinstance(n, ast.NamedExpr):
        return [(n.target, reading.shape_of(n.value))]
    if isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
        over = reading.shape_of(n.iter)
        return [(n.target, over.of)] if isinstance(over, Each) else []
    if isinstance(n, ast.withitem) and n.optional_vars is not None:
        return [(n.optional_vars, reading.shape_of(n.context_expr))]
    return []


def _bind_names(reading: _Reading, node: ast.AST) -> None:
    """Fill READING's names from the unit NODE: `self`, the annotated
    parameters, then what every statement gives a name (`_bindings`) —
    repeated until no name gains a class, since a name may be bound from
    one bound further down in the walk."""
    if reading.cls is not None:
        reading.bind(ast.Name("self"), Instance(frozenset({reading.cls})))
    for n in ast.walk(node):
        if isinstance(n, ast.arg) and n.annotation is not None:
            shape = annotated_shape(n.annotation, reading.unit, reading.index)
            reading.bind(ast.Name(n.arg), shape)
    changed = True
    while changed:
        changed = any(
            [
                reading.bind(target, shape)
                for n in ast.walk(node)
                for target, shape in _bindings(reading, n)
            ]
        )


def method_references(
    unit: str, cls: str | None, index: UnitIndex, skip: set[int]
) -> list[tuple[int, str]]:
    """(line, method) for every place UNIT calls or reads a method on an
    object whose class its annotations tell — CLS is the class around UNIT
    when it is a method. A place the unit's module already resolves by name
    (`module.function`, `Class.method`, `self.method`) is left to the
    caller, and so is a node whose id is in SKIP (inside a type
    annotation). Pure."""
    node = index.units[unit]
    reading = _Reading(unit, cls, index, {})
    _bind_names(reading, node)
    refer = index.refer_in(unit)
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute) and id(n) not in skip and refer(n) is None:
            out += [(n.lineno, m) for m in reading.methods_at(n) if m != unit]
    return out
