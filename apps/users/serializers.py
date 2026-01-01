from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (
    ProjectYouTubeCredential,
    Category,
    Course,
    Lesson,
    Tariff,
    CourseAccess,
    Homework,
    CourseAnalytics,
    CourseDailyAnalytics,
    SettingsSite
)

User = get_user_model()


# =========================
# AUTH
# =========================
class SettingsSeiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SettingsSite
        fields = ("id", "logo", "title", "description", "banner", "whatsapp_number")
        
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "email", "username", "phone", "password", "password2")

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Пароли не совпадают."})
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None)
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.role = "student"
        user.set_password(password)
        user.save()
        return user


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "role")


# =========================
# YOUTUBE PROJECT
# =========================
class ProjectYouTubeStatusSerializer(serializers.ModelSerializer):
    connected = serializers.SerializerMethodField()

    class Meta:
        model = ProjectYouTubeCredential
        fields = ("connected", "channel_id", "updated_at")

    def get_connected(self, obj):
        return True


# =========================
# VITRINA
# =========================
class CategorySerializer(serializers.ModelSerializer):
    courses_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "photo","name", "description", "courses_count")


class CourseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    instructor_name = serializers.CharField(source="instructor.username", read_only=True)
    lessons_count = serializers.IntegerField(read_only=True)
    tariffs_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = (
            "id",
            "photo",
            "title",
            "description",
            "category",
            "category_name",
            "instructor",
            "instructor_name",
            "lessons_count",
            "tariffs_count",
            "created_at",
            "updated_at",
        )


class TariffSerializer(serializers.ModelSerializer):
    access_description = serializers.SerializerMethodField()

    def get_access_description(self, obj):
        if obj.limit_type == "all":
            return "Доступ ко всем урокам курса"
        return f"Доступ к первым {obj.video_limit} урокам"

    class Meta:
        model = Tariff
        fields = (
            "id",
            "title",
            "price",
            "video_limit",
            "access_description",
        )



class LessonPublicSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = Lesson
        fields = (
            "id",
            "course",
            "course_title",
            "title",
            "description",
            "youtube_video_id",
            "video_duration",
            "is_archived",
            # ✅ ДЗ (что видит студент на витрине/в списке уроков)
            "homework_title",
            "homework_description",
            "homework_link",
            # ⚠️ homework_file тут лучше не светить ссылкой (без secure download)
            "created_at",
            "updated_at",
        )


# =========================
# ACCESS / TOKEN
# =========================
class ActivateTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=64)

    def validate_token(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Токен обязателен.")
        return value


class CourseAccessSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    tariff_title = serializers.CharField(source="tariff.title", read_only=True)

    class Meta:
        model = CourseAccess
        fields = (
            "id",
            "course",
            "course_title",
            "tariff",
            "tariff_title",
            "video_limit",
            "is_active",
            "created_at",
        )
        read_only_fields = ("video_limit", "created_at")



class MyCourseLessonSerializer(serializers.ModelSerializer):
    is_opened = serializers.BooleanField(read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lesson
        fields = (
            "id",
            "order",            # ✅ ДОБАВИТЬ
            "title",
            "description",
            "video_duration",
            "is_archived",
            "is_opened",
            "is_available",
            "homework_title",
            "homework_description",
            "homework_link",
        )



class LessonVideoSerializer(serializers.ModelSerializer):
    """
    Видео отдаём только после OpenLessonView (когда урок открыт или уже был открыт).
    """
    class Meta:
        model = Lesson
        fields = (
            "id",
            "title",
            "video_url",
            "youtube_video_id",
            "youtube_status",
            "description",
            "video_duration",
            # ✅ ДЗ
            "homework_title",
            "homework_description",
            "homework_link",
            # ⚠️ homework_file лучше отдавать отдельным защищённым endpoint
        )


class OpenLessonSerializer(serializers.Serializer):
    lesson_id = serializers.IntegerField()

    def validate_lesson_id(self, value):
        if value <= 0:
            raise serializers.ValidationError("Некорректный lesson_id.")
        return value


# =========================
# HOMEWORK (student submission)
# =========================
class HomeworkCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ("id", "lesson", "content")

    def validate_content(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Контент обязателен.")
        return value


class HomeworkSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)
    course_id = serializers.IntegerField(source="lesson.course_id", read_only=True)
    course_title = serializers.CharField(source="lesson.course.title", read_only=True)

    class Meta:
        model = Homework
        fields = (
            "id",
            "lesson",
            "lesson_title",
            "course_id",
            "course_title",
            "content",
            "status",
            "comment",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("status", "comment", "created_at", "updated_at")

# serializers.py
class HomeworkUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ("content",)

    def validate(self, attrs):
        homework = self.instance
        if homework.status != "rework":
            raise serializers.ValidationError(
                "Редактирование возможно только если ДЗ на доработке."
            )
        return attrs

    def validate_content(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Контент обязателен.")
        return value

# =========================
# TEACHER: LESSONS + ARCHIVE + UPLOAD + HOMEWORK TASK
# =========================
class TeacherLessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = (
            "id",
            "course",
            "title",
            "description",
            "video_url",
            "youtube_video_id",
            "youtube_status",
            "youtube_error",
            "is_archived",
            # ✅ ДЗ
            "homework_title",
            "homework_description",
            "homework_link",
            "homework_file",
            "created_at",
        )
        # учителю можно показывать file url (для кабинета ок),
        # но если хочешь строго — тоже через secure download.
        # read_only_fields тут не нужны, это read serializer.


class TeacherLessonCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Редактирование урока (без перезаливки видео).
    ДЗ редактируется здесь же.
    """
    class Meta:
        model = Lesson
        fields = (
            "id",
            "course",
            "title",
            "description",
            "video_duration",

            # read-only YouTube
            "video_url",
            "youtube_video_id",
            "youtube_status",
            "youtube_error",

            # read-only archive
            "is_archived",

            # ✅ ДЗ
            "homework_title",
            "homework_description",
            "homework_link",
            "homework_file",

            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "video_url",
            "youtube_video_id",
            "youtube_status",
            "youtube_error",
            "is_archived",
            "created_at",
            "updated_at",
        )


class TeacherLessonUploadSerializer(serializers.Serializer):
    """
    Создание урока с загрузкой видео (в YouTube) + опционально задание ДЗ.
    """
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    video_file = serializers.FileField(required=True)

    # ✅ ДЗ сразу
    homework_title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    homework_description = serializers.CharField(required=False, allow_blank=True)
    homework_link = serializers.URLField(required=False, allow_blank=True)
    homework_file = serializers.FileField(required=False, allow_null=True)

    def validate_course(self, course):
        user = self.context["request"].user
        if course.instructor_id != user.id:
            raise serializers.ValidationError("Нельзя создавать урок в чужом курсе.")
        return course


# =========================
# TEACHER: HOMEWORK CHECK
# =========================
class TeacherHomeworkSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source="user.username", read_only=True)
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)
    course_title = serializers.CharField(source="lesson.course.title", read_only=True)
    course_id = serializers.IntegerField(source="lesson.course_id", read_only=True)

    class Meta:
        model = Homework
        fields = (
            "id",
            "course_id",
            "course_title",
            "lesson",
            "lesson_title",
            "user",
            "student_username",
            "content",
            "status",
            "comment",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


class TeacherHomeworkUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = ("status", "comment")

    def validate_status(self, value):
        allowed = {c[0] for c in Homework.STATUS_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError("Неверный статус.")
        return value


class AnalyticsOverviewSerializer(serializers.Serializer):
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_purchases = serializers.IntegerField()
    total_students = serializers.IntegerField()

    total_courses = serializers.IntegerField()
    total_lessons = serializers.IntegerField()

    total_homeworks = serializers.IntegerField()
    accepted_homeworks = serializers.IntegerField()



class CourseAnalyticsSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField(source="course.id")
    course_title = serializers.CharField(source="course.title")

    class Meta:
        model = CourseAnalytics
        fields = (
            "course_id",
            "course_title",
            "total_purchases",
            "total_revenue",
            "total_students",
            "completion_rate",
        )


class CourseDailyAnalyticsSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title")

    class Meta:
        model = CourseDailyAnalytics
        fields = (
            "date",
            "course_title",
            "purchases",
            "revenue",
            "opened_lessons",
            "unique_students",
            "homeworks_submitted",
            "homeworks_accepted",
        )


class TopLessonSerializer(serializers.Serializer):
    lesson_id = serializers.IntegerField()
    lesson_title = serializers.CharField()
    course_title = serializers.CharField()
    opens_count = serializers.IntegerField()
