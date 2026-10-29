"""Límites del modelo de servo y validación sin conversiones implícitas."""

from dataclasses import dataclass

from .errors import ValidationError


@dataclass(frozen=True)
class ServoLimits:
    minimum: int = 0
    maximum: int = 180

    def __post_init__(self) -> None:
        if type(self.minimum) is not int or type(self.maximum) is not int:
            raise ValidationError("Los límites del servo deben ser enteros.")
        if not 0 <= self.minimum < self.maximum <= 180:
            raise ValidationError("El servo requiere 0 <= mínimo < máximo <= 180.")

    def validate(self, angle: object) -> int:
        """Acepta enteros reales: bool, float y str no representan un ángulo."""
        if type(angle) is not int:
            raise ValidationError("angle debe ser un entero, no bool, float o texto.")
        if not self.minimum <= angle <= self.maximum:
            raise ValidationError(
                f"angle debe estar entre {self.minimum} y {self.maximum} grados."
            )
        return angle
