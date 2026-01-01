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
# SETTINGS
# =========================
admin.site.register(SettingsSite)

# =========================
# USERS
# =========================
@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "id",
        "username",
        "email",
        "phone",
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "phone")
    ordering = ("id",)

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Роль и контакты", {"fields": ("role", "phone")}),
    )


# =========================
# YOUTUBE PROJECT (SINGLETON)
# =========================
@admin.register(ProjectYouTubeCredential)
class ProjectYouTubeCredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "channel_id", "updated_at")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        return not ProjectYouTubeCredential.objects.exists()


# =========================
# CATEGORY
# =========================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("id",)


# =========================
# LESSON INLINE (COURSE)
# =========================
class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    show_change_link = True

    fields = (
        "order",
        "title",
        "youtube_status",
        "is_archived",
    )

    ordering = ("order",)
    readonly_fields = ("youtube_status",)


# =========================
# COURSE
# =========================
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "instructor",
        "lessons_total",
        "lessons_active",
        "lessons_archived",
    )
    list_filter = ("category", "instructor")
    search_fields = ("title",)
    ordering = ("id",)
    inlines = [LessonInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _lessons_total=Count("lessons"),
            _lessons_archived=Count("lessons", filter=Q(lessons__is_archived=True)),
        )

    @admin.display(description="Всего уроков")
    def lessons_total(self, obj):
        return obj._lessons_total

    @admin.display(description="Активных")
    def lessons_active(self, obj):
        return obj._lessons_total - obj._lessons_archived

    @admin.display(description="В архиве")
    def lessons_archived(self, obj):
        return obj._lessons_archived


# =========================
# LESSON ACTIONS
# =========================
@admin.action(description="Архивировать")
def archive_lessons(modeladmin, request, queryset):
    queryset.update(
        is_archived=True,
        archived_at=timezone.now(),
        archived_by=request.user,
    )


@admin.action(description="Восстановить")
def unarchive_lessons(modeladmin, request, queryset):
    queryset.update(
        is_archived=False,
        archived_at=None,
        archived_by=None,
    )


# =========================
# LESSON
# =========================
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "title",
        "course",
        "youtube_status",
        "is_archived",
    )
    list_filter = ("course", "youtube_status", "is_archived")
    search_fields = ("title", "course__title")
    ordering = ("course", "order")

    actions = [archive_lessons, unarchive_lessons]

    readonly_fields = (
        "created_at",
        "updated_at",
        "archived_at",
        "archived_by",
        "youtube_video_id",
        "video_url",
        "youtube_error",
    )

    fieldsets = (
        ("Основное", {
            "fields": ("course", "order", "title", "description", "video_duration")
        }),
        ("YouTube", {
            "fields": ("video_url", "youtube_video_id", "youtube_status", "youtube_error")
        }),
        ("Домашнее задание", {
            "fields": ("homework_title", "homework_description", "homework_link", "homework_file")
        }),
        ("Архив", {
            "fields": ("is_archived", "archived_at", "archived_by")
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("course")
        if getattr(request.user, "role", "") == "teacher" and not request.user.is_superuser:
            return qs.filter(course__instructor=request.user)
        return qs


# =========================
# TARIFF
# =========================
@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "course",
        "title",
        "price",
        "limit_type",
        "limit_value",
        "video_limit",
    )
    list_filter = ("course", "limit_type")
    readonly_fields = ("video_limit",)
    ordering = ("id",)


# =========================
# COURSE ACCESS
# =========================
@admin.register(CourseAccess)
class CourseAccessAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "course",
        "tariff",
        "video_limit",
        "is_active",
        "created_at",
        "token_short",
    )
    list_filter = ("is_active", "course")
    search_fields = ("user__email", "token")
    readonly_fields = ("created_at", "video_limit")

    autocomplete_fields = ("user", "course", "tariff")

    @admin.display(description="Токен")
    def token_short(self, obj):
        if not obj.token:
            return "-"
        return f"{obj.token[:6]}…{obj.token[-4:]}"


# =========================
# LESSON OPEN (READ ONLY)
# =========================
@admin.register(LessonOpen)
class LessonOpenAdmin(admin.ModelAdmin):
    list_display = ("id", "access", "lesson", "opened_at")
    ordering = ("-opened_at",)
    readonly_fields = ("access", "lesson", "opened_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# =========================
# HOMEWORK
# =========================
@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ("id", "lesson", "user", "status", "created_at")
    list_filter = ("status", "lesson__course")
    search_fields = ("lesson__title", "user__email")
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("lesson", "user")
        if getattr(request.user, "role", "") == "teacher" and not request.user.is_superuser:
            return qs.filter(lesson__course__instructor=request.user)
        return qs
