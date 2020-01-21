from rest_framework.permissions import BasePermission, SAFE_METHODS

from django.core.exceptions import ObjectDoesNotExist


class IsStaffAndOwnerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS or
            request.user and
            request.user.is_authenticated and
            request.user.is_staff
        )

    def has_object_permission(self, request, view, obj):
        return bool(
            request.method in SAFE_METHODS or
            request.user and
            request.user.is_authenticated and
            request.user.is_staff and
            ((obj.owner == request.user and request.method in (
                'PATCH', 'DELETE')) or request.method == 'POST')
        )


class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_staff
        )


class IsOwnerOrCreateOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    """

    def has_object_permission(self, request, view, obj):
        return request.method == 'POST' or obj.user == request.user


class CarrinhoPermission(BasePermission):

    def has_object_permission(self, request, view, obj):
        try:
            if request.user and request.user.is_authenticated:
                return obj.cliente.user == request.user
            else:
                return False
        except ObjectDoesNotExist:
            return True
