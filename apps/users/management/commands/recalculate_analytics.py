from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum, Count

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
    help = "Rebuild course and daily analytics from source tables"

    def handle(self, *args, **options):
        today = date.today()
        start_date = today - timedelta(days=30)

        self.stdout.write("Rebuilding analytics...")

        for course in Course.objects.all():

            # =========================
            # TOTAL ANALYTICS
            # =========================
            accesses = CourseAccess.objects.filter(
                course=course,
                is_active=True,
            )

            total_purchases = accesses.count()
            total_students = accesses.values("user_id").distinct().count()
            total_revenue = accesses.aggregate(
                s=Sum("tariff__price")
            )["s"] or 0

            lessons_count = Lesson.objects.filter(
                course=course,
                is_archived=False,
            ).count()

            # уникальные opens: lesson + user
            total_opens = LessonOpen.objects.filter(
                lesson__course=course,
            ).values(
                "lesson_id", "access__user_id"
            ).distinct().count()

            completion_rate = (
                total_opens / (total_students * lessons_count)
                if total_students and lessons_count
                else 0
            )

            CourseAnalytics.objects.update_or_create(
                course=course,
                defaults={
                    "total_purchases": total_purchases,
                    "total_students": total_students,
                    "total_revenue": total_revenue,
                    "total_lessons": lessons_count,
                    "total_opens": total_opens,
                    "completion_rate": round(completion_rate, 4),
                },
            )

            # =========================
            # DAILY ANALYTICS
            # =========================
            current = start_date
            while current <= today:
                day_accesses = CourseAccess.objects.filter(
                    course=course,
                    is_active=True,
                    created_at__date=current,
                )

                day_opens = LessonOpen.objects.filter(
                    lesson__course=course,
                    opened_at__date=current,
                )

                CourseDailyAnalytics.objects.update_or_create(
                    course=course,
                    date=current,
                    defaults={
                        "purchases": day_accesses.count(),
                        "revenue": day_accesses.aggregate(
                            s=Sum("tariff__price")
                        )["s"] or 0,
                        "opened_lessons": day_opens.count(),
                        "unique_students": day_opens.values(
                            "access__user_id"
                        ).distinct().count(),
                        "homeworks_submitted": Homework.objects.filter(
                            lesson__course=course,
                            created_at__date=current,
                        ).count(),
                        "homeworks_accepted": Homework.objects.filter(
                            lesson__course=course,
                            status="accepted",
                            updated_at__date=current,
                        ).count(),
                    },
                )

                current += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS("Analytics rebuild completed successfully"))
