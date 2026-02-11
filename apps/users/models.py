import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.utils.text import slugify


# =========================
# SETTINGS SITE
# =========================
class SettingsSite(models.Model):
    logo = models.ImageField(
        upload_to="logo/",
        verbose_name="Логотип",
        blank=True,
        null=True,
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Заголовок",
        blank=True,
        null=True,
    )
    description = models.TextField(
        verbose_name="Описание",
        blank=True,
        null=True,
    )
    banner = models.ImageField(
        upload_to="banner/",
        verbose_name="Фото для баннера",
        blank=True,
        null=True,
    )
    whatsapp_number = models.CharField(
        max_length=100,
        verbose_name="Номер WhatsApp",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Основные настройки сайта"
        verbose_name_plural = "Основные настройки сайта"

    def __str__(self):
        return str(self.title or "Настройки сайта")


# =========================
# USERS
# =========================
class User(AbstractUser):
    ROLE_CHOICES = [
        ("student", "Student"),
        ("teacher", "Teacher"),
        ("admin", "Admin"),
    ]

    email = models.EmailField("Email", unique=True)
    phone = models.CharField(
        max_length=255,
        verbose_name="Номер телефона",
        blank=True,
        default="",
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default="student",
        verbose_name="Роль",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def save(self, *args, **kwargs):
        if not self.username:
            base = (self.email or "user").split("@")[0]
            base = slugify(base) or "user"
            self.username = f"{base}_{secrets.token_hex(3)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email or self.username or f"User #{self.pk}"


# =========================
# YOUTUBE PROJECT (ONE ACCOUNT)
# =========================
class ProjectYouTubeCredential(models.Model):
    """
    OAuth токены одного общего YouTube-аккаунта проекта.
    Подключается 1 раз админом, дальше преподы грузят без входа в YouTube.
    """
    credentials_json = models.TextField(verbose_name="OAuth credentials (JSON)")
    channel_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="Channel ID",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "YouTube проекта"
        verbose_name_plural = "YouTube проекта"

    def __str__(self):
        return f"YouTube проекта ({self.channel_id or 'no-channel'})"


# =========================
# CATALOG
# =========================
class Category(models.Model):
    photo = models.ImageField(
        upload_to="category/",
        verbose_name="Фото категории",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=255, verbose_name="Название категории")
    description = models.TextField(
        blank=True,
        default="",
        verbose_name="Описание категории",
    )

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class Course(models.Model):
    photo = models.ImageField(
        upload_to="course/",
        verbose_name="Фото курса",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=255, verbose_name="Название курса")
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="courses",
        verbose_name="Категория",
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"role": "teacher"},
        related_name="teaching_courses",
        verbose_name="Преподаватель",
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name="Описание курса",
    )

    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="В архиве",
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата архивации",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
        indexes = [
            models.Index(fields=["category", "is_archived"]),
            models.Index(fields=["instructor", "is_archived"]),
            models.Index(fields=["title"]),
        ]

    def __str__(self):
        return self.title

    def archive(self):
        if self.is_archived:
            return
        self.is_archived = True
        self.archived_at = timezone.now()
        self.save(update_fields=["is_archived", "archived_at"])

        Lesson.objects.filter(course=self, is_archived=False).update(
            is_archived=True,
            archived_at=timezone.now(),
        )

    def unarchive(self):
        if not self.is_archived:
            return
        self.is_archived = False
        self.archived_at = None
        self.save(update_fields=["is_archived", "archived_at"])


# =========================
# LESSONS (archive + youtube status + homework attach)
# =========================
class Lesson(models.Model):
    YT_STATUS_CHOICES = [
        ("idle", "Не загружается"),
        ("uploading", "Загрузка"),
        ("processing", "Обработка YouTube"),
        ("ready", "Готово"),
        ("error", "Ошибка"),
    ]

    title = models.CharField(max_length=255, verbose_name="Название урока")
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lessons",
        verbose_name="Курс",
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок урока",
        help_text="Чем меньше — тем раньше урок",
    )

    video_url = models.URLField(blank=True, default="", verbose_name="Ссылка на видео")
    youtube_video_id = models.CharField(
        max_length=32,
        blank=True,
        default="",
        verbose_name="YouTube videoId",
    )

    youtube_status = models.CharField(
        max_length=12,
        choices=YT_STATUS_CHOICES,
        default="idle",
        verbose_name="Статус YouTube",
    )
    youtube_error = models.TextField(
        blank=True,
        default="",
        verbose_name="Ошибка YouTube",
    )
    youtube_uploaded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="YouTube: время загрузки",
    )

    video_duration = models.DurationField(
        null=True,
        blank=True,
        verbose_name="Длительность видео",
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name="Описание урока",
    )

    is_archived = models.BooleanField(
        default=False,
        verbose_name="В архиве",
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата архивации",
    )
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archived_lessons",
        verbose_name="Кто архивировал",
    )

    homework_title = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="ДЗ: название",
    )
    homework_description = models.TextField(
        blank=True,
        default="",
        verbose_name="ДЗ: описание",
    )
    homework_link = models.URLField(
        blank=True,
        default="",
        verbose_name="ДЗ: ссылка",
        help_text="Google Drive / GitHub / Notion и т.д.",
    )
    homework_file = models.FileField(
        upload_to="homework_files/%Y/%m/%d/",
        blank=True,
        null=True,
        verbose_name="ДЗ: файл",
        help_text="PDF/DOCX/ZIP и т.д. (не видео)",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
        indexes = [
            models.Index(fields=["course", "is_archived"]),
            models.Index(fields=["course", "order"]),
            models.Index(fields=["youtube_status"]),
            models.Index(fields=["title"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["order", "id"]

    def __str__(self):
        if self.course_id:
            return f"{self.course.title} — {self.title}"
        return self.title

    def archive(self, by_user=None):
        if self.is_archived:
            return
        self.is_archived = True
        self.archived_at = timezone.now()
        self.archived_by = by_user
        self.save(update_fields=["is_archived", "archived_at", "archived_by"])

    def unarchive(self):
        if not self.is_archived:
            return
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.save(update_fields=["is_archived", "archived_at", "archived_by"])


# =========================
# TARIFFS
# =========================
class Tariff(models.Model):
    LIMIT_TYPE_CHOICES = [
        ("count", "Кол-во видео"),
        ("percent", "Процент от курса"),
        ("all", "Все видео курса"),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="tariffs",
        verbose_name="Курс",
    )
    title = models.CharField(max_length=255, verbose_name="Название тарифа")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена",
    )

    limit_type = models.CharField(
        max_length=10,
        choices=LIMIT_TYPE_CHOICES,
        default="count",
        verbose_name="Тип лимита",
    )
    limit_value = models.PositiveIntegerField(
        default=0,
        verbose_name="Значение лимита",
    )
    video_limit = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name="Итоговый лимит",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Тариф"
        verbose_name_plural = "Тарифы"
        indexes = [
            models.Index(fields=["course"]),
            models.Index(fields=["limit_type"]),
        ]

    def __str__(self):
        course_title = getattr(self.course, "title", "")
        return f"{course_title} — {self.title}"

    def clean(self):
        super().clean()
        if not self.course_id:
            return

        total_lessons = Lesson.objects.filter(course_id=self.course_id, is_archived=False).count()
        if total_lessons <= 0:
            raise ValidationError("В курсе нет уроков. Сначала добавь уроки, потом тарифы.")

        if self.limit_type == "all":
            self.video_limit = total_lessons
            return

        if self.limit_type == "count":
            if self.limit_value < 1:
                raise ValidationError("Для типа 'Кол-во видео' значение должно быть >= 1.")
            if self.limit_value > total_lessons:
                raise ValidationError(f"Лимит не может быть больше уроков в курсе ({total_lessons}).")
            self.video_limit = self.limit_value
            return

        if self.limit_type == "percent":
            if not (1 <= self.limit_value <= 100):
                raise ValidationError("Для типа 'Процент' значение должно быть 1..100.")
            calc = round(total_lessons * (self.limit_value / 100))
            self.video_limit = max(1, min(total_lessons, calc))
            return

        raise ValidationError("Неизвестный тип лимита.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# =========================
# ACCESS / PURCHASE
# =========================
class CourseAccess(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_accesses",
        blank=True,
        null=True,
        verbose_name="Пользователь",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="accesses",
        verbose_name="Курс",
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.PROTECT,
        verbose_name="Тариф",
    )

    token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        verbose_name="Токен",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создано",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    video_limit = models.PositiveIntegerField(
        editable=False,
        verbose_name="Лимит уроков",
    )

    class Meta:
        verbose_name = "Доступ к курсу"
        verbose_name_plural = "Доступы к курсам"
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_access_user_course"),
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["course"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        user_label = str(self.user) if self.user_id else "Без пользователя"
        return f"{user_label} → {self.course}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        self.video_limit = self.tariff.video_limit
        super().save(*args, **kwargs)

    def can_open_lesson(self, lesson: "Lesson") -> bool:
        if lesson.course_id != self.course_id:
            return False
        if lesson.is_archived:
            return False
        return lesson.order <= self.video_limit


class LessonOpen(models.Model):
    access = models.ForeignKey(
        CourseAccess,
        on_delete=models.CASCADE,
        related_name="opened_lessons",
        verbose_name="Доступ",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="opens",
        verbose_name="Урок",
    )
    opened_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Открыт",
    )

    class Meta:
        verbose_name = "Открытый урок"
        verbose_name_plural = "Открытые уроки"
        constraints = [
            models.UniqueConstraint(fields=["access", "lesson"], name="uniq_open_access_lesson"),
        ]
        indexes = [
            models.Index(fields=["access"]),
            models.Index(fields=["lesson"]),
            models.Index(fields=["opened_at"]),
        ]

    def __str__(self):
        return f"{self.access} открыл {self.lesson}"


# =========================
# HOMEWORK (student submission)
# =========================
class Homework(models.Model):
    STATUS_CHOICES = [
        ("accepted", "Принято"),
        ("examination", "На проверке"),
        ("rework", "На доработку"),
        ("declined", "Отклонено"),
    ]

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="homeworks",
        verbose_name="Урок",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="homeworks",
        verbose_name="Пользователь",
    )
    content = models.TextField(verbose_name="Ответ / ссылка на ДЗ")

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="examination",
        verbose_name="Статус",
    )
    comment = models.TextField(
        blank=True,
        null=True,
        verbose_name="Комментарий преподавателя",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Домашнее задание (ответ студента)"
        verbose_name_plural = "Домашние задания (ответы студентов)"
        indexes = [
            models.Index(fields=["user", "lesson"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "lesson"], name="uniq_homework_user_lesson"),
        ]

    def __str__(self):
        return f"ДЗ: {self.user} — {self.lesson}"


# =========================
# ANALYTICS
# =========================
class CourseDailyAnalytics(models.Model):
    date = models.DateField(db_index=True, verbose_name="Дата")
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        verbose_name="Курс",
        related_name="daily_analytics",
    )

    purchases = models.PositiveIntegerField(default=0, verbose_name="Покупки")
    revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Выручка",
    )

    opened_lessons = models.PositiveIntegerField(default=0, verbose_name="Открытые уроки")
    unique_students = models.PositiveIntegerField(default=0, verbose_name="Уникальные студенты")

    homeworks_submitted = models.PositiveIntegerField(default=0, verbose_name="ДЗ отправлено")
    homeworks_accepted = models.PositiveIntegerField(default=0, verbose_name="ДЗ принято")

    class Meta:
        verbose_name = "Дневная аналитика курса"
        verbose_name_plural = "Дневная аналитика курсов"
        constraints = [
            models.UniqueConstraint(fields=["date", "course"], name="uniq_daily_date_course"),
        ]
        indexes = [models.Index(fields=["date", "course"])]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.course} — {self.date:%d.%m.%Y}"


class CourseAnalytics(models.Model):
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        verbose_name="Курс",
        related_name="analytics",
    )

    total_purchases = models.PositiveIntegerField(default=0, verbose_name="Всего покупок")
    total_revenue = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Общая выручка",
    )

    total_students = models.PositiveIntegerField(default=0, verbose_name="Всего студентов")

    total_lessons = models.PositiveIntegerField(default=0, verbose_name="Всего уроков")
    total_opens = models.PositiveIntegerField(default=0, verbose_name="Всего открытий")

    completion_rate = models.FloatField(default=0, verbose_name="Процент прохождения")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Аналитика курса"
        verbose_name_plural = "Аналитика курсов"

    def __str__(self):
        return f"Аналитика: {self.course}"
