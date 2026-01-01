import os
import tempfile
import shutil
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.views import TokenObtainPairView
from .auth_serializers import EmailTokenObtainPairSerializer

from .models import (
    Category,
    Course,
    Lesson,
    Tariff,
    CourseAccess,
    LessonOpen,
    Homework,
    ProjectYouTubeCredential,
    CourseDailyAnalytics,
    CourseAnalytics,
    SettingsSite
)
from .permissions import IsTeacher, IsStudent, IsAdminRole
from .serializers import (
    RegisterSerializer,
    MeSerializer,
    CategorySerializer,
    CourseSerializer,
    TariffSerializer,
    LessonPublicSerializer,
    ActivateTokenSerializer,
    CourseAccessSerializer,
    MyCourseLessonSerializer,
    LessonVideoSerializer,
    OpenLessonSerializer,
    HomeworkCreateSerializer,
    HomeworkSerializer,
    HomeworkUpdateSerializer,
    TeacherLessonSerializer,
    TeacherLessonCreateUpdateSerializer,
    TeacherHomeworkSerializer,
    TeacherHomeworkUpdateSerializer,
    TeacherLessonUploadSerializer,
    AnalyticsOverviewSerializer, 
    CourseAnalyticsSerializer,
    TopLessonSerializer,
    CourseDailyAnalyticsSerializer,
    SettingsSeiteSerializer
)
from .youtube_service import build_youtube, creds_from_json, upload_video

from django.db.models import Sum, Count
from apps.users.analytics import (
    on_course_activated,
    on_lesson_open,
    on_homework_submitted,
    on_homework_accepted,
)

# =========================
# AUTH
# =========================

class SettingsSeiteView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = SettingsSeiteSerializer
    queryset = SettingsSite.objects.all()


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer



class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    
class MeView(generics.RetrieveAPIView):
    serializer_class = MeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# =========================
# VITRINA (PUBLIC)
# =========================
class CategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsAdminRole()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        return Category.objects.annotate(
            courses_count=Count("courses")
        ).order_by("id")


class CategoryDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    http_method_names = ["get", "patch"]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [permissions.IsAuthenticated(), IsAdminRole()]
        return [permissions.AllowAny()]


class CourseListCreateView(generics.ListCreateAPIView):
    serializer_class = CourseSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsTeacher()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Course.objects.select_related(
            "category", "instructor"
        ).annotate(
            lessons_count=Count("lessons"),
            tariffs_count=Count("tariffs"),
        )

        category_id = self.request.query_params.get("category_id")
        instructor_id = self.request.query_params.get("instructor_id")

        if category_id:
            qs = qs.filter(category_id=category_id)
        if instructor_id:
            qs = qs.filter(instructor_id=instructor_id)

        return qs.order_by("id")

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)



class CourseDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CourseSerializer
    http_method_names = ["get", "patch"]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [permissions.IsAuthenticated(), IsTeacher()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Course.objects.select_related("category", "instructor")

        # teacher может редактировать только свои курсы
        if self.request.method == "PATCH":
            qs = qs.filter(instructor=self.request.user)

        return qs


class TariffListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = TariffSerializer

    def get_queryset(self):
        qs = Tariff.objects.select_related("course")
        course_id = self.request.query_params.get("course_id")
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs.order_by("id")


class LessonListPublicView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LessonPublicSerializer

    def get_queryset(self):
        qs = Lesson.objects.select_related("course").filter(is_archived=False)
        course_id = self.request.query_params.get("course_id")
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs.order_by("id")


# =========================
# TOKEN ACTIVATE
# =========================
class ActivateTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @transaction.atomic
    def post(self, request):
        ser = ActivateTokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        access = CourseAccess.objects.select_for_update().filter(
            token=ser.validated_data["token"]
        ).first()

        if not access:
            return Response({"detail": "Токен не найден."}, status=404)

        if not access.is_active:
            return Response({"detail": "Доступ отключён."}, status=400)

        if access.user_id and access.user_id != request.user.id:
            return Response({"detail": "Токен уже активирован."}, status=400)

        if CourseAccess.objects.filter(
            user=request.user, course=access.course
        ).exists():
            return Response({"detail": "Доступ уже есть."}, status=400)

        access.user = request.user
        access.save(update_fields=["user"])

        # ✅ АНАЛИТИКА
        on_course_activated(access)

        return Response(CourseAccessSerializer(access).data)


# =========================
# STUDENT CABINET: MY COURSES
# =========================
class MyCoursesView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request):
        accesses = (
            CourseAccess.objects
            .select_related("course", "tariff")
            .filter(user=request.user, is_active=True)
            .order_by("-created_at")
        )

        result = []
        for access in accesses:
            lessons_qs = Lesson.objects.filter(course=access.course, is_archived=False).order_by("id")
            opened_subq = LessonOpen.objects.filter(access=access, lesson_id=OuterRef("pk"))
            lessons_qs = lessons_qs.annotate(is_opened=Exists(opened_subq))

            result.append({
                "access": CourseAccessSerializer(access).data,
                "lessons": MyCourseLessonSerializer(lessons_qs, many=True).data,
            })

        return Response(result, status=status.HTTP_200_OK)


# =========================
# STUDENT: OPEN LESSON
# =========================
class OpenLessonView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @transaction.atomic
    def post(self, request):
        ser = OpenLessonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        lesson = Lesson.objects.select_related("course").filter(
            id=ser.validated_data["lesson_id"],
            is_archived=False,
        ).first()

        if not lesson:
            return Response({"detail": "Урок не найден."}, status=404)

        access = CourseAccess.objects.select_for_update().filter(
            user=request.user,
            course=lesson.course,
            is_active=True,
        ).first()

        if not access:
            return Response({"detail": "Нет доступа."}, status=403)

        if LessonOpen.objects.filter(access=access, lesson=lesson).exists():
            return Response({"lesson": LessonVideoSerializer(lesson).data})

        if access.used_videos >= access.video_limit:
            return Response({"detail": "Лимит исчерпан."}, status=402)

        LessonOpen.objects.create(access=access, lesson=lesson)
        access.used_videos += 1
        access.save(update_fields=["used_videos"])

        # ✅ АНАЛИТИКА
        on_lesson_open(access, lesson)

        return Response({"lesson": LessonVideoSerializer(lesson).data})
# =========================
# STUDENT: HOMEWORK
# =========================
class HomeworkCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = HomeworkCreateSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        lesson = serializer.validated_data["lesson"]

        if not CourseAccess.objects.filter(
            user=self.request.user,
            course=lesson.course,
            is_active=True
        ).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Нет доступа к курсу.")

        hw = serializer.save(user=self.request.user)

        on_homework_submitted(hw)
        


class MyHomeworksView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = HomeworkSerializer

    def get_queryset(self):
        return Homework.objects.select_related("lesson", "lesson__course").filter(user=self.request.user).order_by("-created_at")

# views.py
class MyHomeworkUpdateView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = HomeworkUpdateSerializer
    lookup_field = "id"
    http_method_names = ["patch"]

    def get_queryset(self):
        return Homework.objects.filter(user=self.request.user)

# =========================
# TEACHER CABINET: LESSONS + ARCHIVE
# =========================
class TeacherLessonListCreateView(generics.ListCreateAPIView):
    """
    Обычное создание урока (без загрузки видео) — например по ссылке/позже.
    Для загрузки файла используем отдельный endpoint: TeacherCreateLessonWithUploadView.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = TeacherLessonSerializer

    def get_queryset(self):
        qs = Lesson.objects.select_related("course").filter(course__instructor=self.request.user)

        archived = self.request.query_params.get("archived", "0")
        if archived == "1":
            qs = qs.filter(is_archived=True)
        elif archived == "all":
            pass
        else:
            qs = qs.filter(is_archived=False)

        course_id = self.request.query_params.get("course_id")
        if course_id:
            qs = qs.filter(course_id=course_id)

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(title__icontains=search)

        return qs.order_by("-id")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TeacherLessonCreateUpdateSerializer
        return TeacherLessonSerializer

    def perform_create(self, serializer):
        course = serializer.validated_data.get("course")
        if not course or course.instructor_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Нельзя создавать урок в чужом курсе.")
        serializer.save()


class TeacherLessonDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = TeacherLessonCreateUpdateSerializer

    def get_queryset(self):
        return Lesson.objects.select_related("course").filter(course__instructor=self.request.user)

    def perform_destroy(self, instance):
        instance.archive(by_user=self.request.user)


class TeacherLessonArchiveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def post(self, request, pk):
        lesson = Lesson.objects.select_related("course").filter(pk=pk, course__instructor=request.user).first()
        if not lesson:
            return Response({"detail": "Урок не найден."}, status=status.HTTP_404_NOT_FOUND)
        if lesson.is_archived:
            return Response({"detail": "Урок уже в архиве."}, status=status.HTTP_400_BAD_REQUEST)

        lesson.archive(by_user=request.user)
        return Response({"detail": "Урок архивирован."}, status=status.HTTP_200_OK)


class TeacherLessonUnarchiveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def post(self, request, pk):
        lesson = Lesson.objects.select_related("course").filter(pk=pk, course__instructor=request.user).first()
        if not lesson:
            return Response({"detail": "Урок не найден."}, status=status.HTTP_404_NOT_FOUND)
        if not lesson.is_archived:
            return Response({"detail": "Урок не в архиве."}, status=status.HTTP_400_BAD_REQUEST)

        lesson.unarchive()
        return Response({"detail": "Урок восстановлен."}, status=status.HTTP_200_OK)


# =========================
# TEACHER: CREATE LESSON + UPLOAD VIDEO TO YOUTUBE PROJECT
# =========================
class TeacherCreateLessonWithUploadView(APIView):
    """
    Учитель загружает файл -> backend заливает в YouTube проекта -> создаём Lesson.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        ser = TeacherLessonUploadSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)

        proj = ProjectYouTubeCredential.objects.first()
        if not proj:
            return Response({"detail": "YouTube проекта не подключён."}, status=status.HTTP_400_BAD_REQUEST)

        course = ser.validated_data["course"]
        title = ser.validated_data["title"]
        description = ser.validated_data.get("description", "") or ""
        video_file = ser.validated_data["video_file"]

        # ✅ ДЗ поля
        hw_title = ser.validated_data.get("homework_title", "") or ""
        hw_desc = ser.validated_data.get("homework_description", "") or ""
        hw_link = ser.validated_data.get("homework_link", "") or ""
        hw_file = ser.validated_data.get("homework_file", None)

        # 1) создаём урок сразу
        lesson = Lesson.objects.create(
            course=course,
            title=title,
            description=description,

            video_url="",
            youtube_video_id="",
            youtube_status="uploading",
            youtube_error="",

            homework_title=hw_title,
            homework_description=hw_desc,
            homework_link=hw_link,
            homework_file=hw_file,
        )

        tmp_dir = tempfile.mkdtemp(prefix="yt_upload_")
        # безопасное имя (на Windows/Unix без сюрпризов)
        safe_name = os.path.basename(getattr(video_file, "name", "video.mp4")) or "video.mp4"
        tmp_path = os.path.join(tmp_dir, safe_name)

        try:
            # 2) пишем файл во временную папку
            with open(tmp_path, "wb") as f:
                for chunk in video_file.chunks():
                    f.write(chunk)

            # 3) грузим в YouTube
            creds = creds_from_json(proj.credentials_json)
            youtube = build_youtube(creds)

            video_id = upload_video(
                youtube=youtube,
                file_path=tmp_path,
                title=title,
                description=description,
                privacy_status="private",  # ✅ приватно
                category_id="27",
            )

            # 4) сохраняем данные
            lesson.youtube_video_id = video_id
            lesson.video_url = f"https://www.youtube.com/watch?v={video_id}"
            lesson.youtube_status = "processing"
            lesson.youtube_error = ""
            lesson.save(update_fields=["youtube_video_id", "video_url", "youtube_status", "youtube_error"])

            return Response(TeacherLessonSerializer(lesson).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            lesson.youtube_status = "error"
            lesson.youtube_error = str(e)
            lesson.save(update_fields=["youtube_status", "youtube_error"])
            return Response(
                {"detail": "Ошибка загрузки в YouTube.", "error": str(e), "lesson_id": lesson.id},
                status=status.HTTP_400_BAD_REQUEST,
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# =========================
# TEACHER CABINET: HOMEWORK CHECK
# =========================
class TeacherHomeworksView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = TeacherHomeworkSerializer

    def get_queryset(self):
        qs = (
            Homework.objects
            .select_related("lesson", "lesson__course", "user")
            .filter(lesson__course__instructor=self.request.user)
            .order_by("-created_at")
        )

        status_q = self.request.query_params.get("status")
        if status_q:
            qs = qs.filter(status=status_q)

        course_id = self.request.query_params.get("course_id")
        if course_id:
            qs = qs.filter(lesson__course_id=course_id)

        lesson_id = self.request.query_params.get("lesson_id")
        if lesson_id:
            qs = qs.filter(lesson_id=lesson_id)

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(user__username__icontains=search)

        return qs


class TeacherHomeworkUpdateView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    serializer_class = TeacherHomeworkUpdateSerializer

    def get_queryset(self):
        return Homework.objects.filter(
            lesson__course__instructor=self.request.user
        )

    def perform_update(self, serializer):
        old_status = self.get_object().status
        hw = serializer.save()

        if old_status != "accepted" and hw.status == "accepted":
            # ✅ АНАЛИТИКА
            on_homework_accepted(hw)



class AnalyticsOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        data = {
            "total_revenue": CourseAnalytics.objects.aggregate(s=Sum("total_revenue"))["s"] or 0,
            "total_purchases": CourseAnalytics.objects.aggregate(s=Sum("total_purchases"))["s"] or 0,
            "total_students": CourseAnalytics.objects.aggregate(s=Sum("total_students"))["s"] or 0,
            "total_courses": Course.objects.count(),
            "total_lessons": Lesson.objects.filter(is_archived=False).count(),
            "total_homeworks": Homework.objects.count(),
            "accepted_homeworks": Homework.objects.filter(status="accepted").count(),
        }
        return Response(AnalyticsOverviewSerializer(data).data)
    

class CoursesAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = CourseAnalytics.objects.select_related("course").order_by("-total_revenue")
        return Response(CourseAnalyticsSerializer(qs, many=True).data)

class CourseDetailAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request, course_id):
        analytics = CourseAnalytics.objects.select_related("course").get(course_id=course_id)
        daily = CourseDailyAnalytics.objects.filter(course_id=course_id).order_by("date")

        return Response({
            "course": CourseAnalyticsSerializer(analytics).data,
            "daily": CourseDailyAnalyticsSerializer(daily, many=True).data,
        })
    

class TopLessonsAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = (
            Lesson.objects
            .select_related("course")
            .annotate(opens_count=Count("opens"))
            .order_by("-opens_count")[:10]
        )

        data = [
            {
                "lesson_id": l.id,
                "lesson_title": l.title,
                "course_title": l.course.title,
                "opens_count": l.opens_count,
            }
            for l in qs
        ]

        return Response(TopLessonSerializer(data, many=True).data)

