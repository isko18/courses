from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD  # "email"

    def validate(self, attrs):
        # attrs содержит email + password
        email = attrs.get("email")
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError("Email и пароль обязательны.")

        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=password,
        )
        if not user:
            raise serializers.ValidationError("Неверный email или пароль.")

        data = super().validate({"email": email, "password": password})
        data["user"] = {"id": user.id, "email": user.email, "role": getattr(user, "role", "")}
        return data
