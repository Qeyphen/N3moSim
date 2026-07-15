from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from rcl_interfaces.msg import (
    FloatingPointRange,
    IntegerRange,
    ParameterDescriptor,
    SetParametersResult,
)
from rclpy.node import Node


@dataclass(frozen=True)
class ParamChange:
    name: str
    old: Any
    new: Any


OnParamsChanged = Callable[[list[ParamChange]], None]

ModelT = TypeVar("ModelT", bound=BaseModel)  # backported from PEP 695 (py3.12) for py3.10


class PydanticParamsBase(Generic[ModelT]):
    """Bridge between a pydantic BaseModel and ROS2 parameters.

    Subclasses parameterize the generic with their pydantic model and set
    ``model_class`` to the same type. The constructor introspects the model
    fields, declares ROS parameters, reads their initial values and builds
    a validated model instance accessible via ``self.p`` (fully typed).

    Example::

        class ControlParams(PydanticParamsBase[ControlModel]):
            model_class = ControlModel

        params = ControlParams(node)
        params.p.sail_kp  # typed as float, PyCharm/ty autocomplete works
    """

    model_class: type[BaseModel]  # override in subclass
    p: ModelT

    def __init__(
        self,
        node: Node,
        *,
        on_change: OnParamsChanged | None = None,
    ):
        self._node = node
        self._on_change = on_change

        # Declare each model field as a ROS parameter
        for name, field_info in self.model_class.model_fields.items():
            if field_info.is_required():
                raise ValueError(
                    f"{type(self).__name__}: field '{name}' in "
                    f"'{self.model_class.__name__}' has no default. "
                    f"All fields must have a default value for ROS parameter declaration."
                )
            if field_info.default is PydanticUndefined:
                # Field has a default_factory (e.g. Field(default_factory=list))
                default = field_info.default_factory()
            else:
                default = field_info.default
            descriptor = self._build_descriptor(field_info)
            node.declare_parameter(name, default, descriptor)

        # Read declared values back and build validated model
        init_values: dict[str, Any] = {}
        for name in self.model_class.model_fields:
            raw = node.get_parameter(name).value
            init_values[name] = self._coerce(name, raw)

        self.p: ModelT = self.model_class(**init_values)  # type: ignore[assignment]

        node.add_on_set_parameters_callback(self._on_set_parameters)

    # --- ROS callback -----------------------------------------------------------

    def _on_set_parameters(self, params: Iterable[Any]) -> SetParametersResult:
        known_names = set(self.model_class.model_fields)

        # Start from current values
        current: dict[str, Any] = self.p.model_dump()

        try:
            for p in params:
                if p.name not in known_names:
                    self._node.get_logger().error(
                        f"ignoring unknown parameter: {p.name}"
                    )
                    continue
                current[p.name] = self._coerce(p.name, p.value)

            new_model = self.model_class(**current)
        except Exception as e:
            self._node.get_logger().error(f"invalid parameter update: {e}")
            return SetParametersResult(
                successful=False,
                reason=str(e),
            )

        # Compute changes
        old_values = self.p.model_dump()
        new_values = new_model.model_dump()
        changes: list[ParamChange] = []
        for name in known_names:
            if old_values[name] != new_values[name]:
                changes.append(
                    ParamChange(name=name, old=old_values[name], new=new_values[name])
                )

        self.p = new_model  # type: ignore[assignment]

        if changes and self._on_change is not None:
            try:
                self._on_change(changes)
            except Exception as e:
                self._node.get_logger().error(
                    f"on_change callback failed: {type(e).__name__}: {e}"
                )

        return SetParametersResult(successful=True)

    # --- helpers ----------------------------------------------------------------

    @staticmethod
    def _build_descriptor(field_info: FieldInfo) -> ParameterDescriptor:
        """Build a ROS ParameterDescriptor from Pydantic Field metadata.

        Extracts ge/le/gt/lt constraints and description from the field and
        maps them to floating_point_range / integer_range descriptor fields.
        """
        descriptor = ParameterDescriptor()
        if field_info.description:
            descriptor.description = field_info.description

        # Extract numeric constraints from Pydantic metadata
        ge: float | int | None = None
        le: float | int | None = None
        gt: float | int | None = None
        lt: float | int | None = None

        for constraint in field_info.metadata:
            cls_name = type(constraint).__name__
            if cls_name == "Ge":
                ge = constraint.ge
            elif cls_name == "Le":
                le = constraint.le
            elif cls_name == "Gt":
                gt = constraint.gt
            elif cls_name == "Lt":
                lt = constraint.lt

        # Resolve annotation to base type (unwrap Optional etc.)
        annotation = field_info.annotation
        if get_origin(annotation) is not None:
            args = get_args(annotation)
            base_type = next((a for a in args if a in (int, float)), None)
        else:
            base_type = annotation

        # Allow int overrides in YAML for float params; _coerce converts them.
        # Without this, rclpy raises InvalidParameterTypeException at declare time,
        # before _coerce ever runs.
        if base_type is float:
            descriptor.dynamic_typing = True

        has_bounds = any(v is not None for v in (ge, le, gt, lt))
        if not has_bounds:
            return descriptor

        # gt/lt → open bounds, offset by smallest step
        if base_type is float:
            from_val = ge if ge is not None else (gt + 1e-9 if gt is not None else None)
            to_val = le if le is not None else (lt - 1e-9 if lt is not None else None)
            fpr = FloatingPointRange()
            fpr.from_value = float(from_val) if from_val is not None else -math.inf
            fpr.to_value = float(to_val) if to_val is not None else math.inf
            fpr.step = 0.0  # continuous
            descriptor.floating_point_range = [fpr]
        elif base_type is int:
            from_val = ge if ge is not None else (gt + 1 if gt is not None else None)
            to_val = le if le is not None else (lt - 1 if lt is not None else None)
            ir = IntegerRange()
            ir.from_value = int(from_val) if from_val is not None else -(2**31)
            ir.to_value = int(to_val) if to_val is not None else 2**31 - 1
            ir.step = 0  # any integer
            descriptor.integer_range = [ir]

        return descriptor

    def _coerce(self, name: str, value: Any) -> Any:
        """Cast int→float when the field annotation is float (common ROS issue)."""
        field = self.model_class.model_fields.get(name)
        if field is None:
            return value
        annotation = field.annotation
        # Unwrap Optional[float] etc.
        if get_origin(annotation) is not None:
            args = get_args(annotation)
            if float in args and isinstance(value, int) and not isinstance(value, bool):
                return float(value)
        elif (
            annotation is float
            and isinstance(value, int)
            and not isinstance(value, bool)
        ):
            return float(value)
        return value
