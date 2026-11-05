from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response({"user": request.user.username, "role": request.user.role,
                     "auth": type(request.successful_authenticator).__name__})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def token_logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


class RefreshLogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(trim_whitespace=False)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def jwt_logout(request):
    serializer = RefreshLogoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        token = RefreshToken(serializer.validated_data["refresh"])
        if str(token["user_id"]) != str(request.user.pk):
            return Response({"detail": "Бұл токен басқа пайдаланушыға тиесілі."}, status=403)
        token.blacklist()
    except TokenError:
        return Response({"detail": "Refresh токені жарамсыз."}, status=400)
    return Response(status=status.HTTP_204_NO_CONTENT)
