from rest_framework.permissions import BasePermission


class IsAuthenticatedUser(BasePermission):
    """
    只允許已登入的使用者通過
    """

    def has_permission(self, request, view):
        print(request.user)
        print(request.user.is_authenticated)
        return request.user.is_authenticated
