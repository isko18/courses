from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse

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
        "first_name",
        "last_name",
        "email",
        "phone",
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
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
        "has_video_file",
        "is_archived",
    )

    ordering = ("order",)
    readonly_fields = ("youtube_status", "has_video_file")
    
    @admin.display(description="Видео файл", boolean=True)
    def has_video_file(self, obj):
        return bool(obj.video_file)


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
# LESSON FILTERS
# =========================
class HasVideoFileFilter(admin.SimpleListFilter):
    title = "Наличие видео файла"
    parameter_name = "has_video_file"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Есть видео файл"),
            ("no", "Нет видео файла"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(video_file="").exclude(video_file__isnull=True)
        elif self.value() == "no":
            return queryset.filter(Q(video_file="") | Q(video_file__isnull=True))
        return queryset


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
        "video_file_link",
        "youtube_status",
        "is_archived",
    )
    list_filter = ("course", "youtube_status", "is_archived", HasVideoFileFilter)
    search_fields = ("title", "course__title")
    ordering = ("course", "order")

    actions = [archive_lessons, unarchive_lessons]

    readonly_fields = (
        "created_at",
        "updated_at",
        "archived_at",
        "archived_by",
        "youtube_video_id",
        "youtube_error",
        "video_file",
        "video_file_preview",
        "video_file_info",
        "admin_video_upload_warning",
    )

    fieldsets = (
        ("Основное", {
            "fields": ("course", "order", "title", "description", "video_duration")
        }),
        ("Видео", {
            "fields": (
                "admin_video_upload_warning",
                "video_file",
                "video_file_preview",
                "video_file_info",
                "video_url",
                "youtube_video_id",
                "youtube_status",
                "youtube_error"
            ),
            "description": "Загрузка файла через админку отключена, чтобы не блокировать сайт. Используйте API: POST /api/teacher/lessons/create-with-upload/ или укажите ссылку (video_url)."
        }),
        ("Домашнее задание", {
            "fields": ("homework_title", "homework_description", "homework_link", "homework_file")
        }),
        ("Архив", {
            "fields": ("is_archived", "archived_at", "archived_by")
        }),
        ("Системная информация", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("course")
        if getattr(request.user, "role", "") == "teacher" and not request.user.is_superuser:
            return qs.filter(course__instructor=request.user)
        return qs

    @admin.display(description="")
    def admin_video_upload_warning(self, obj):
        return mark_safe(
            '<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; '
            'padding: 12px; margin-bottom: 12px;">'
            '<strong>⚠️ Загрузка видео через админку отключена</strong>, чтобы сайт не зависал при больших файлах. '
            'Чтобы добавить или заменить видео файл, используйте API: '
            '<code>POST /api/teacher/lessons/create-with-upload/</code> (см. DOCS.md). '
            'Здесь можно только указать ссылку на видео в поле «Ссылка на видео» (video_url).'
            '</div>'
        )

    @admin.display(description="Видео файл", ordering="video_file")
    def video_file_link(self, obj):
        """Отображает ссылку на видео файл в списке уроков."""
        if obj.video_file:
            file_size = ""
            try:
                if obj.video_file.storage.exists(obj.video_file.name):
                    size = obj.video_file.size
                    if size:
                        if size < 1024:
                            file_size = f" ({size} B)"
                        elif size < 1024 * 1024:
                            file_size = f" ({size / 1024:.1f} KB)"
                        elif size < 1024 * 1024 * 1024:
                            file_size = f" ({size / (1024 * 1024):.1f} MB)"
                        else:
                            file_size = f" ({size / (1024 * 1024 * 1024):.2f} GB)"
            except:
                pass
            
            video_url = reverse('admin:users_lesson_change', args=[obj.pk])
            return format_html(
                '<a href="{}" style="color: #417690;">📹 Видео{}</a> | '
                '<a href="/api/lessons/{}/video/" target="_blank" style="color: #ba2121;">▶ Просмотр</a>',
                video_url,
                file_size,
                obj.pk
            )
        return format_html('<span style="color: #999;">—</span>')

    @admin.display(description="Превью видео")
    def video_file_preview(self, obj):
        """Отображает видео плеер в админке."""
        if obj.video_file:
            video_url = f"/api/lessons/{obj.pk}/video/"
            return format_html(
                '<div style="margin: 10px 0;">'
                '<video controls width="100%" style="max-width: 800px; max-height: 450px;">'
                '<source src="{}" type="video/mp4">'
                'Ваш браузер не поддерживает видео.'
                '</video>'
                '<br><small>Для просмотра видео в админке требуется авторизация. '
                'Используйте кнопку "Просмотр" для открытия в новой вкладке.</small>'
                '</div>',
                video_url
            )
        return format_html('<p style="color: #999;">Видео файл не загружен</p>')

    @admin.display(description="Информация о видео")
    def video_file_info(self, obj):
        """Отображает информацию о видео файле."""
        if obj.video_file:
            info = []
            try:
                if obj.video_file.storage.exists(obj.video_file.name):
                    size = obj.video_file.size
                    if size:
                        if size < 1024:
                            info.append(f"Размер: {size} B")
                        elif size < 1024 * 1024:
                            info.append(f"Размер: {size / 1024:.1f} KB")
                        elif size < 1024 * 1024 * 1024:
                            info.append(f"Размер: {size / (1024 * 1024):.1f} MB")
                        else:
                            info.append(f"Размер: {size / (1024 * 1024 * 1024):.2f} GB")
            except Exception as e:
                info.append(f"Ошибка получения размера: {e}")
            
            info.append(f"Путь: {obj.video_file.name}")
            
            if obj.video_duration:
                info.append(f"Длительность: {obj.video_duration}")
            
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">'
                '<strong>📁 Информация о файле:</strong><br>'
                '{}'
                '</div>',
                '<br>'.join(info)
            )
        return format_html('<p style="color: #999;">—</p>')


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
    search_fields = ("title", "course__title")  # ✅ ВАЖНО
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
