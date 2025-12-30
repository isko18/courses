from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum, Count, Q

from apps.users.models import (
    Course,
    Lesson,
    LessonOpen,
    CourseAccess,
    Homework,
    CourseAnalytics,
    CourseDailyAnalytics,
)


class Command(BaseCommand):
    help = "Recalculate course and daily analytics"

    @transaction.atomic
    def handle(self, *args, **options):
        today = date.today()

        self.stdout.write("Recalculating CourseAnalytics...")

        for course in Course.objects.all():
            purchases_qs = CourseAccess.objects.filter(
                course=course,
                is_active=True,
            )

            total_purchases = purchases_qs.count()
            total_students = purchases_qs.values("user_id").distinct().count()
            total_revenue = purchases_qs.aggregate(
                s=Sum("tariff__price")
            )["s"] or 0

            total_lessons = Lesson.objects.filter(
                course=course,
                is_archived=False,
            ).count()

            total_opens = LessonOpen.objects.filter(
                lesson__course=course
            ).count()

            if total_students and total_lessons:
                completion_rate = total_opens / (total_students * total_lessons)
            else:
                completion_rate = 0

            CourseAnalytics.objects.update_or_create(
                course=course,
                defaults={
                    "total_purchases": total_purchases,
                    "total_students": total_students,
                    "total_revenue": total_revenue,
                    "total_lessons": total_lessons,
                    "total_opens": total_opens,
                    "completion_rate": round(completion_rate, 4),
                },
            )

        self.stdout.write("Recalculating CourseDailyAnalytics...")

        # считаем, например, последние 30 дней
        start_date = today - timedelta(days=30)

        for course in Course.objects.all():
            current = start_date
            while current <= today:
                purchases_day = CourseAccess.objects.filter(
                    course=course,
                    created_at__date=current,
                    is_active=True,
                )

                opens_day = LessonOpen.objects.filter(
                    lesson__course=course,
                    opened_at__date=current,
                )

                CourseDailyAnalytics.objects.update_or_create(
                    course=course,
                    date=current,
                    defaults={
                        "purchases": purchases_day.count(),
                        "revenue": purchases_day.aggregate(
                            s=Sum("tariff__price")
                        )["s"] or 0,
                        "opened_lessons": opens_day.count(),
                        "unique_students": opens_day.values(
                            "access__user_id"
                        ).distinct().count(),
                        "homeworks_submitted": Homework.objects.filter(
                            lesson__course=course,
                            created_at__date=current,
                        ).count(),
                        "homeworks_accepted": Homework.objects.filter(
                            lesson__course=course,
                            created_at__date=current,
                            status="accepted",
                        ).count(),
                    },
                )

                current += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS("Analytics recalculated successfully"))
