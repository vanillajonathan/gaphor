"""The Coder.

The idea:
* Get all classes from a model
  * Drop all classes declared in a Profile
  * Drop all classes from a package blacklist
  * Drop all classes derived from SimpleAttribute's
  * Order all classes in hierarchical order
* Write class definitions
* Write attributes, derived unions, associations, redefines, etc.
  (not sure if there should be an order)

Notes:
* Enumerations are classes ending with "Kind"
* Two stereotypes: Tagged and SimpleAttribute
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from gaphor import UML
from gaphor.codegen.override import Overrides
from gaphor.core.modeling import ElementFactory
from gaphor.storage import storage
from gaphor.UML.modelinglanguage import UMLModelingLanguage


class Coder:
    def __init__(self, class_, overrides):
        self._class = class_
        self.overrides = overrides

    def __str__(self):
        base_classes = ", ".join(
            c.name for c in sorted(bases(self._class), key=lambda c: c.name)  # type: ignore[no-any-return]
        )
        return f"class {self._class.name}({base_classes}):"

    def __iter__(self):
        if self._class.attribute:
            for attr in sorted(self._class.attribute, key=lambda a: a.name or ""):
                full_name = f"{self._class.name}.{attr.name}"
                if self.overrides.has_override(full_name):
                    return f"{attr.name}: {self.overrides.get_type(full_name)}"
                elif attr.isDerived:
                    pass
                elif attr.association and is_simple_attribute(attr.type):
                    yield f"{attr.name}: attribute[str]"
                elif attr.association:
                    mult = "one" if attr.upper == "1" else "many"
                    yield f"{attr.name}: relation_{mult}[{attr.type.name}]"
                elif is_enumeration(attr.typeValue):
                    yield f"{attr.name}: enumeration"
                else:
                    yield f"{attr.name}: attribute[{attr.typeValue}]"
        else:
            yield "pass"


def order_classes(classes: Iterable[UML.Class]) -> Iterable[UML.Class]:
    seen_classes = set()

    def order(c):
        if c not in seen_classes:
            for b in bases(c):
                yield from order(b)
            yield c
            seen_classes.add(c)

    for c in classes:  # sorted(classes, key=lambda c: c.name):  # type: ignore
        yield from order(c)


def bases(c: UML.Class) -> Iterable[UML.Class]:
    for g in c.generalization:
        yield g.general
    # TODO: Add bases from extensions


def is_enumeration(name: str) -> bool:
    return bool(name and (name.endswith("Kind") or name.endswith("Sort")))


def is_simple_attribute(c: UML.Class) -> bool:
    for s in UML.model.get_applied_stereotypes(c):
        if s.name == "SimpleAttribute":
            return True
    for g in c.generalization:
        if is_simple_attribute(g.general):
            return True
    return False


def is_in_profile(c: UML.Class):
    def test(p: UML.Package):
        return isinstance(p, UML.Profile) or (p.owningPackage and test(p.owningPackage))

    return test(c.owningPackage)


def is_in_toplevel_package(c: UML.Class, package_name: str):
    def test(p: UML.Package):
        return (not p.owningPackage and p.name == package_name) or (
            p.owningPackage and test(p.owningPackage)
        )

    return test(c.owningPackage)


def coder(modelfile, overrides, outfile):
    element_factory = ElementFactory()
    uml_modeling_language = UMLModelingLanguage()
    storage.load(
        modelfile,
        element_factory,
        uml_modeling_language,
    )

    classes = list(
        order_classes(
            c
            for c in element_factory.select(UML.Class)
            if not (
                is_enumeration(c.name) or is_simple_attribute(c) or is_in_profile(c)
            )
        )
    )

    for c in classes:
        if overrides.has_override(c.name):
            print(overrides.get_override(c.name))
        else:
            coder = Coder(c, overrides)
            print(coder)
            for a in coder:
                print("    " + a)
        print()
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("modelfile", type=Path, help="Gaphor model filename")
    parser.add_argument(
        "-o", dest="outfile", type=Path, help="Python data model filename"
    )
    parser.add_argument("-r", dest="overridesfile", type=Path, help="Override filename")
    args = parser.parse_args()

    overrides = Overrides(args.overridesfile)
    if args.outfile:
        with open(args.outfile, "w") as outfile:
            coder(args.modelfile, overrides, outfile)
    else:
        coder(args.modelfile, overrides, sys.stdout)
