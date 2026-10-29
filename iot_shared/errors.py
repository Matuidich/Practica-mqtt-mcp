"""Errores de entrada que pueden mostrarse sin iniciar conexiones."""


class ConfigurationError(ValueError):
    """La configuración local falta o no cumple el contrato."""


class ValidationError(ValueError):
    """Un mensaje o valor del dominio no cumple el contrato."""
