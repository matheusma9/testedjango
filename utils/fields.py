from rest_framework.exceptions import ValidationError

def get_fields(data, fields):
    res = []
    errors = []
    for field in fields:
        f = data.get(field)
        if f:
            res.append(f)
        else:
            errors.append('O campo ' + field + ' é obrigatório')
    if errors:
        raise ValidationError(errors)
    return res