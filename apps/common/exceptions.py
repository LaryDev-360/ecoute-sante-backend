from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class BusinessRuleError(APIException):
    status_code = 400
    default_detail = "Règle métier non respectée."
    default_code = "business_rule_error"


class NotFoundError(APIException):
    status_code = 404
    default_detail = "Ressource introuvable."
    default_code = "not_found"


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            "success": False,
            "error": response.data,
        }
    return response
