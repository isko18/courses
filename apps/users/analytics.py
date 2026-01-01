from django.db.models import F
from django.utils import timezone

from apps.users.models import (
    CourseAnalytics,
    CourseDailyAnalytics,
    LessonOpen,
    CourseAccess,
)

# =========================
# HELPERS
# =========================

def _get_daily(course, day=None):
    day = day or timezone.now().date()
    obj, _ = CourseDailyAnalytics.objects.get_or_create(
        course=course,
        date=day,
    )
    return obj


def _get_total(course):
    obj, _ = CourseAnalytics.objects.get_or_create(course=course)
    return obj


# =========================
# EVENTS
# =========================

def on_course_activated(access):
    course = access.course
    user = access.user
    price = access.tariff.price
    today = timezone.now().date()

    # --- DAILY ---
    daily = _get_daily(course, today)

    daily.purchases = F("purchases") + 1
    daily.revenue = F("revenue") + price

    # уникальный студент в день
    already_today = CourseAccess.objects.filter(
        course=course,
        user=user,
        created_at__date=today,
    ).exclude(id=access.id).exists()

    if not already_today:
        daily.unique_students = F("unique_students") + 1

    daily.save(update_fields=["purchases", "revenue", "unique_students"])

    # --- TOTAL ---
    total = _get_total(course)

    total.total_purchases = F("total_purchases") + 1
    total.total_revenue = F("total_revenue") + price

    # уникальный студент за всё время
    already_ever = CourseAccess.objects.filter(
        course=course,
        user=user,
    ).exclude(id=access.id).exists()

    if not already_ever:
        total.total_students = F("total_students") + 1

    total.save(update_fields=["total_purchases", "total_revenue", "total_students"])


def on_lesson_open(access, lesson):
    course = lesson.course
    user = access.user
    today = timezone.now().date()

    daily = _get_daily(course, today)

    daily.opened_lessons = F("opened_lessons") + 1

    # уникальный студент за день
    opened_today = LessonOpen.objects.filter(
        lesson__course=course,
        access__user=user,
        opened_at__date=today,
    ).exclude(access=access, lesson=lesson).exists()

    if not opened_today:
        daily.unique_students = F("unique_students") + 1

    daily.save(update_fields=["opened_lessons", "unique_students"])

    total = _get_total(course)
    total.total_opens = F("total_opens") + 1
    total.save(update_fields=["total_opens"])


def on_homework_submitted(homework):
    daily = _get_daily(homework.lesson.course)
    daily.homeworks_submitted = F("homeworks_submitted") + 1
    daily.save(update_fields=["homeworks_submitted"])


def on_homework_accepted(homework):
    daily = _get_daily(homework.lesson.course)
    daily.homeworks_accepted = F("homeworks_accepted") + 1
    daily.save(update_fields=["homeworks_accepted"])
