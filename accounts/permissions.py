from rest_framework.permissions import BasePermission


class IsOwnerOrStaffOrCreateOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    """

    def has_object_permission(self, request, view, obj):
        return request.method == 'POST' or obj.user == request.user or request.user.is_staff
