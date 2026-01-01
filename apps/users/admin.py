from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    User,
    ProjectYouTubeCredential,
    Category,
    Course,
    Lesson,
    Tariff,
    CourseAccess,
    LessonOpen,
    Homework,
    SettingsSite
)


# =========================
# USERS
# =========================
admin.site.register(SettingsSite)

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("id", "username", "email", "phone", "role", "is_active", "is_staff", "is_superuser")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "phone", "first_name", "last_name")
    ordering = ("id",)

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Роль и контакты", {"fields": ("role", "phone")}),
    )


# =========================
# YOUTUBE PROJECT CREDENTIAL (ONE ACCOUNT)
# =========================
@admin.register(ProjectYouTubeCredential)
class ProjectYouTubeCredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "channel_id", "updated_at", "created_at")
    search_fields = ("channel_id",)
    ordering = ("-updated_at",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("YouTube проекта", {"fields": ("channel_id", "credentials_json")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )

    def has_add_permission(self, request):
        # Разрешаем только одну запись (singleton)
        if ProjectYouTubeCredential.objects.exists():
            return False
        return super().has_add_permission(request)


# =========================
# CATEGORY
# =========================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "photo")
    search_fields = ("name",)
    ordering = ("id",)


# =========================
# LESSON INLINE (for Course)
# =========================
class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    show_change_link = True

    fields = (
        "title",
        "youtube_status",
        "youtube_video_id",
        "video_url",
        "is_archived",
        "homework_title",
        "homework_link",
    )

    readonly_fields = ("youtube_status", "youtube_video_id", "video_url")


# =========================
# COURSE
# =========================
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("id", "photo","title", "category", "instructor", "lessons_total", "lessons_active", "lessons_archived")
    list_filter = ("category", "instructor")
    search_fields = ("title", "description", "category__name", "instructor__username", "instructor__email")
    ordering = ("id",)
    inlines = [LessonInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _lessons_total=Count("lessons", distinct=True),
            _lessons_archived=Count("lessons", filter=Q(lessons__is_archived=True), distinct=True),
        )

    @admin.display(description="Уроков (всего)")
    def lessons_total(self, obj):
        return getattr(obj, "_lessons_total", obj.lessons.count())

    @admin.display(description="Уроков (активные)")
    def lessons_active(self, obj):
        total = getattr(obj, "_lessons_total", obj.lessons.count())
        archived = getattr(obj, "_lessons_archived", obj.lessons.filter(is_archived=True).count())
        return max(0, total - archived)

    @admin.display(description="Уроков (архив)")
    def lessons_archived(self, obj):
        return getattr(obj, "_lessons_archived", obj.lessons.filter(is_archived=True).count())


# =========================
# LESSON actions
# =========================
@admin.action(description="Архивировать выбранные уроки")
def archive_lessons(modeladmin, request, queryset):
    queryset.update(is_archived=True, archived_at=timezone.now(), archived_by=request.user)


@admin.action(description="Восстановить выбранные уроки")
def unarchive_lessons(modeladmin, request, queryset):
    queryset.update(is_archived=False, archived_at=None, archived_by=None)


@admin.action(description="Сбросить YouTube-ошибку (youtube_error)")
def clear_youtube_error(modeladmin, request, queryset):
    queryset.update(youtube_error="")


# =========================
# LESSON
# =========================
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "course",
        "youtube_status",
        "youtube_video_id",
        "is_archived",
        "created_at",
    )
    list_filter = ("course", "youtube_status", "is_archived")
    search_fields = ("title", "course__title", "youtube_video_id", "video_url", "youtube_error", "homework_title")
    ordering = ("-id",)
    actions = [archive_lessons, unarchive_lessons, clear_youtube_error]

    readonly_fields = (
        "created_at",
        "updated_at",
        "archived_at",
        "archived_by",
    )

    fieldsets = (
        ("Основное", {"fields": ("course", "title", "description", "video_duration")}),
        ("YouTube", {"fields": ("video_url", "youtube_video_id", "youtube_status", "youtube_error", "youtube_uploaded_at")}),
        ("Домашнее задание (что делает студент)", {"fields": ("homework_title", "homework_description", "homework_link", "homework_file")}),
        ("Архив", {"fields": ("is_archived", "archived_at", "archived_by")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("course", "archived_by", "course__instructor")
        # если вдруг дать доступ teacher-ам в админку — видят только своё
        if getattr(request.user, "role", "") == "teacher" and not request.user.is_superuser:
            return qs.filter(course__instructor=request.user)
        return qs


# =========================
# TARIFF
# =========================
@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ("id", "course", "title", "price", "limit_type", "limit_value", "video_limit", "updated_at")
    list_filter = ("course", "limit_type")
    search_fields = ("title", "course__title")
    ordering = ("id",)

    fields = ("course", "title", "price", "limit_type", "limit_value", "video_limit")
    readonly_fields = ("video_limit",)


# =========================
# COURSE ACCESS
# =========================
@admin.action(description="Отключить доступ (is_active=False)")
def disable_access(modeladmin, request, queryset):
    queryset.update(is_active=False)


@admin.action(description="Включить доступ (is_active=True)")
def enable_access(modeladmin, request, queryset):
    queryset.update(is_active=True)


@admin.register(CourseAccess)
class CourseAccessAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "course",
        "tariff",
        "is_active",
        "video_limit",
        "used_videos",
        "created_at",
        "token_short",
    )
    list_filter = ("is_active", "course", "tariff")
    search_fields = ("user__username", "user__email", "course__title", "token")
    ordering = ("-created_at",)

    autocomplete_fields = ("user", "course", "tariff")
    readonly_fields = ("created_at", "video_limit")

    fieldsets = (
        ("Основное", {"fields": ("user", "course", "tariff")}),
        ("Доступ", {"fields": ("token", "is_active")}),
        ("Лимиты", {"fields": ("video_limit", "used_videos")}),
        ("Служебное", {"fields": ("created_at",)}),
    )

    actions = [disable_access, enable_access]

    @admin.display(description="Токен")
    def token_short(self, obj):
        if not obj.token:
            return "-"
        if len(obj.token) <= 12:
            return obj.token
        return f"{obj.token[:6]}…{obj.token[-4:]}"


# =========================
# LESSON OPEN (read-only)
# =========================
@admin.register(LessonOpen)
class LessonOpenAdmin(admin.ModelAdmin):
    list_display = ("id", "access", "lesson", "opened_at")
    list_filter = ("access__course",)
    search_fields = ("access__user__username", "lesson__title", "access__course__title", "access__token")
    ordering = ("-opened_at",)
    readonly_fields = ("access", "lesson", "opened_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# =========================
# HOMEWORK (student submissions)
# =========================
@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ("id", "lesson", "user", "status", "created_at", "updated_at")
    list_filter = ("status", "lesson__course")
    search_fields = ("lesson__title", "lesson__course__title", "user__username", "user__email", "comment", "content")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("lesson", "lesson__course", "user", "lesson__course__instructor")
        if getattr(request.user, "role", "") == "teacher" and not request.user.is_superuser:
            return qs.filter(lesson__course__instructor=request.user)
        return qs
