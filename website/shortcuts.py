from rest_framework.exceptions import NotFound


def get_object_or_404(klass, *args, **kwargs):
    try:
        return klass.objects.get(**kwargs)
    except klass.DoesNotExist:
        raise NotFound(klass._meta.verbose_name + ' não encontrado(a)')
