import os
import tempfile
import shutil
import threading
import logging
from django.db import transaction
from django.utils.text import slugify
logger = logging.getLogger(__name__)
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models import BooleanField, Case, When, Value

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
from .video_service import optimize_video_for_upload, get_video_info
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotModified, StreamingHttpResponse
from django.views.decorators.http import etag
import mimetypes

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
        return (
            Category.objects
            .annotate(courses_count=Count("courses", filter=Q(courses__is_archived=False)))  # ✅
            .order_by("id")
        )


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
        qs = (
            Course.objects
            .select_related("category", "instructor")
            .filter(is_archived=False)  # ✅ ВАЖНО
            .annotate(
                lessons_count=Count("lessons", filter=Q(lessons__is_archived=False)),  # ✅ только неархивные уроки
                tariffs_count=Count("tariffs"),
            )
        )

        category_id = self.request.query_params.get("category_id")
        instructor_id = self.request.query_params.get("instructor_id")
        user = getattr(self.request, "user", None)
        is_teacher = user and getattr(user, "role", None) == "teacher"

        # Учитель без instructor_id — показываем только его курсы
        if is_teacher and instructor_id is None:
            qs = qs.filter(instructor=user)
        elif instructor_id:
            qs = qs.filter(instructor_id=instructor_id)

        if category_id:
            qs = qs.filter(category_id=category_id)

        return qs.order_by("id")

    def list(self, request, *args, **kwargs):
        """Для учителя при запросе своих курсов — без пагинации, чтобы видеть все."""
        queryset = self.filter_queryset(self.get_queryset())
        user = getattr(request, "user", None)
        is_teacher = user and getattr(user, "role", None) == "teacher"
        instructor_id = request.query_params.get("instructor_id")
        is_teacher_own = is_teacher and (instructor_id is None or str(instructor_id) == str(user.id))

        if is_teacher_own:
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)


class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CourseSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [permissions.IsAuthenticated(), IsTeacher()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Course.objects.select_related("category", "instructor").filter(is_archived=False)  # ✅
        if self.request.method in ("PATCH", "DELETE"):
            qs = qs.filter(instructor=self.request.user)
        return qs

    def perform_destroy(self, instance):
        instance.archive()




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
        qs = Lesson.objects.select_related("course").filter(is_archived=False, course__is_archived=False)
        course_id = self.request.query_params.get("course_id")
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs.order_by("order", "id")



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
            lessons_qs = Lesson.objects.filter(course=access.course, is_archived=False).order_by("order", "id")

            opened_subq = LessonOpen.objects.filter(access=access, lesson_id=OuterRef("pk"))
            lessons_qs = lessons_qs.annotate(
                is_opened=Exists(opened_subq),
                is_available=Case(
                    When(order__lte=access.video_limit, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )

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

        # ✅ ГЛАВНАЯ ПРОВЕРКА
        if lesson.order > access.video_limit:
            return Response({"detail": "Тариф не позволяет открыть этот урок."}, status=402)

        # если уже открывали — просто отдаём видео
        if LessonOpen.objects.filter(access=access, lesson=lesson).exists():
            return Response({"lesson": LessonVideoSerializer(lesson, context={"request": request}).data})

        LessonOpen.objects.get_or_create(access=access, lesson=lesson)


        on_lesson_open(access, lesson)

        return Response({"lesson": LessonVideoSerializer(lesson, context={"request": request}).data})

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

        return qs.order_by("order", "id")

    def list(self, request, *args, **kwargs):
        """Уроки учителя — без пагинации, все сразу."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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
# ASYNC VIDEO PROCESSING (фоновая обработка после загрузки)
# =========================
VIDEO_COPY_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB


def _process_video_upload_task(lesson_id, tmp_dir, tmp_path, safe_name, title, compression_enabled, max_size_gb):
    """
    Выполняется в фоновом потоке: оптимизация, копирование в media, обновление урока.
    """
    from django.db import connection
    connection.close()
    try:
        if compression_enabled:
            optimized_path = os.path.join(tmp_dir, "optimized_" + safe_name)
            success, final_path, error = optimize_video_for_upload(
                tmp_path, optimized_path, max_file_size_gb=max_size_gb
            )
            if not success:
                Lesson.objects.filter(pk=lesson_id).update(
                    youtube_status="error",
                    youtube_error=error or "Ошибка оптимизации видео",
                )
                return
            final_video_path = final_path
        else:
            final_video_path = tmp_path

        video_info = get_video_info(final_video_path)
        video_duration = None
        if video_info and video_info.get("duration"):
            video_duration = timedelta(seconds=int(video_info["duration"]))

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename_base = slugify(title)[:50] or "video"
        file_extension = os.path.splitext(safe_name)[1] or ".mp4"
        final_filename = f"{filename_base}_{timestamp}{file_extension}"
        media_path = os.path.join("videos", timezone.now().strftime("%Y/%m/%d"), final_filename)
        full_media_path = os.path.join(settings.MEDIA_ROOT, media_path)
        os.makedirs(os.path.dirname(full_media_path), exist_ok=True)

        with open(final_video_path, "rb") as src:
            with open(full_media_path, "wb") as dst:
                while True:
                    chunk = src.read(VIDEO_COPY_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)

        lesson = Lesson.objects.get(pk=lesson_id)
        lesson.video_file.name = media_path
        lesson.video_duration = video_duration
        lesson.youtube_status = "ready"
        lesson.youtube_error = ""
        lesson.save(update_fields=["video_file", "video_duration", "youtube_status", "youtube_error"])
    except Exception as e:
        logger.exception("Ошибка фоновой обработки видео lesson_id=%s", lesson_id)
        Lesson.objects.filter(pk=lesson_id).update(
            youtube_status="error",
            youtube_error=str(e),
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# =========================
# TEACHER: CREATE LESSON + UPLOAD VIDEO TO YOUTUBE PROJECT
# =========================
class TeacherCreateLessonWithUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacher]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        ser = TeacherLessonUploadSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)

        course = ser.validated_data["course"]
        title = ser.validated_data["title"]
        description = ser.validated_data.get("description", "") or ""

        video_file = ser.validated_data.get("video_file")
        video_url = ser.validated_data.get("video_url", "") or ""

        # ✅ ДЗ поля
        hw_title = ser.validated_data.get("homework_title", "") or ""
        hw_desc = ser.validated_data.get("homework_description", "") or ""
        hw_link = ser.validated_data.get("homework_link", "") or ""
        hw_file = ser.validated_data.get("homework_file", None)

        # =========================
        # CASE 1: MANUAL URL
        # =========================
        if video_url and not video_file:
            lesson = Lesson.objects.create(
                course=course,
                title=title,
                description=description,

                video_url=video_url,
                youtube_video_id="",
                youtube_status="idle",
                youtube_error="",

                homework_title=hw_title,
                homework_description=hw_desc,
                homework_link=hw_link,
                homework_file=hw_file,
            )
            return Response(TeacherLessonSerializer(lesson, context={"request": request}).data, status=status.HTTP_201_CREATED)

        # =========================
        # CASE 2: UPLOAD FILE -> SERVER (с оптимизацией)
        # =========================
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

        tmp_dir = tempfile.mkdtemp(prefix="video_upload_")
        safe_name = os.path.basename(getattr(video_file, "name", "video.mp4")) or "video.mp4"
        # Убираем небезопасные символы из имени файла
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "._-")
        if not safe_name:
            safe_name = "video.mp4"
        tmp_path = os.path.join(tmp_dir, safe_name)

        try:
            # Сохраняем загруженный файл во временную директорию
            with open(tmp_path, "wb") as f:
                for chunk in video_file.chunks():
                    f.write(chunk)

            # Проверяем размер файла
            file_size_gb = os.path.getsize(tmp_path) / (1024 ** 3)
            max_size_gb = getattr(settings, "VIDEO_MAX_SIZE_GB", 20)
            
            if file_size_gb > max_size_gb:
                lesson.youtube_status = "error"
                lesson.youtube_error = f"Файл слишком большой ({file_size_gb:.2f}GB). Максимальный размер: {max_size_gb}GB"
                lesson.save(update_fields=["youtube_status", "youtube_error"])
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return Response(
                    {"detail": lesson.youtube_error, "lesson_id": lesson.id},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            compression_enabled = getattr(settings, "VIDEO_COMPRESSION_ENABLED", True)
            thread = threading.Thread(
                target=_process_video_upload_task,
                args=(lesson.id, tmp_dir, tmp_path, safe_name, title, compression_enabled, max_size_gb),
                daemon=True,
            )
            thread.start()
            return Response(TeacherLessonSerializer(lesson, context={"request": request}).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Ошибка при приёме видео")
            lesson.youtube_status = "error"
            lesson.youtube_error = str(e)
            lesson.save(update_fields=["youtube_status", "youtube_error"])
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return Response(
                {"detail": "Ошибка загрузки видео.", "error": str(e), "lesson_id": lesson.id},
                status=status.HTTP_400_BAD_REQUEST,
            )


# =========================
# VIDEO STREAMING (оптимизировано под воспроизведение уровня YouTube)
# =========================

# Размер чанка для стриминга: быстрая отдача первых байт и перемотка (как у YouTube)
VIDEO_STREAM_CHUNK_SIZE = 2 * 1024 * 1024  # 2 MB
# Порог: диапазон больше этого — отдаём потоком; меньше — одним куском (метаданные MP4)
VIDEO_STREAM_THRESHOLD = 10 * 1024 * 1024  # 10 MB


def _video_stream_etag(video_path):
    """ETag по пути, mtime и размеру — для 304 Not Modified."""
    try:
        stat = os.stat(video_path)
        return f'"{os.path.basename(video_path)}-{stat.st_mtime_ns}-{stat.st_size}"'
    except OSError:
        return None


def _video_stream_get_user(request):
    """Проверка авторизации (Bearer или ?token=). Возвращает user или None."""
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Bearer "):
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import InvalidToken
        try:
            token = AccessToken(auth_header.split(" ", 1)[1])
            return token.user
        except (InvalidToken, IndexError, AttributeError):
            pass
    token_param = request.GET.get("token")
    if token_param:
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import InvalidToken
        try:
            token = AccessToken(token_param)
            return token.user
        except (InvalidToken, AttributeError):
            pass
    return None


def _video_stream_check_access(user, lesson):
    """Проверка доступа к уроку. Возвращает None или Response с ошибкой."""
    from .models import CourseAccess
    if user.is_staff or user.is_superuser:
        return None
    if getattr(user, "role", None) == "student":
        access = CourseAccess.objects.filter(
            user=user, course=lesson.course, is_active=True
        ).first()
        if not access:
            return Response({"detail": "Нет доступа к этому уроку."}, status=403)
        if lesson.order > access.video_limit:
            return Response({"detail": "Тариф не позволяет открыть этот урок."}, status=402)
        return None
    if getattr(user, "role", None) == "teacher":
        if lesson.course.instructor_id != user.id:
            return Response({"detail": "Нет доступа к этому уроку."}, status=403)
        return None
    return Response({"detail": "Нет доступа к этому уроку."}, status=403)


class VideoStreamView(APIView):
    """
    Потоковая передача видео с поддержкой Range, HEAD, ETag/304.
    Просмотр без авторизации: достаточно URL урока. С авторизацией проверяется доступ по тарифу.
    """
    permission_classes = []

    def _get_lesson_and_file(self, request, lesson_id):
        """Урок и файл: без авторизации — отдаём видео любому; с авторизацией — проверяем доступ к курсу."""
        user = _video_stream_get_user(request)
        try:
            lesson = Lesson.objects.select_related("course").get(
                id=lesson_id, is_archived=False
            )
        except Lesson.DoesNotExist:
            raise Http404("Урок не найден")
        if user:
            err = _video_stream_check_access(user, lesson)
            if err:
                return None, err
        if not lesson.video_file:
            return None, Response({"detail": "Видео файл не найден."}, status=404)
        video_path = lesson.video_file.path
        if not os.path.exists(video_path):
            return None, Response({"detail": "Видео файл не существует на сервере."}, status=404)
        content_type, _ = mimetypes.guess_type(video_path)
        if not content_type:
            content_type = "video/mp4"
        file_size = os.path.getsize(video_path)
        return (lesson, video_path, content_type, file_size), None

    def _build_stream_response(
        self, request, video_path, content_type, file_size, head_only=False
    ):
        """Строит ответ 206/200 со стримингом или 416, 304. head_only — без тела (для HEAD)."""
        range_header = (request.META.get("HTTP_RANGE") or "").strip()
        etag = _video_stream_etag(video_path)
        if etag and request.META.get("HTTP_IF_NONE_MATCH", "").strip() == etag:
            r = HttpResponseNotModified()
            r["ETag"] = etag
            r["Cache-Control"] = "public, max-age=3600"
            r["Accept-Ranges"] = "bytes"
            return r

        start, end = 0, file_size - 1
        if range_header.startswith("bytes="):
            parts = range_header[6:].strip().split("-")
            try:
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
            except (ValueError, IndexError):
                r = Response(
                    {"detail": "Неверный заголовок Range."},
                    status=416,
                )
                r["Content-Range"] = f"bytes */{file_size}"
                return r
            start = max(0, start)
            end = min(end, file_size - 1)
            if start > end or start >= file_size:
                r = HttpResponse(status=416)
                r["Content-Range"] = f"bytes */{file_size}"
                return r

        content_length = end - start + 1
        use_stream = content_length > VIDEO_STREAM_THRESHOLD

        if head_only:
            response = HttpResponse(status=206)
            response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            response["Content-Length"] = str(content_length)
        elif use_stream:
            def file_iterator():
                with open(video_path, "rb") as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(VIDEO_STREAM_CHUNK_SIZE, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                        remaining -= len(chunk)

            response = StreamingHttpResponse(file_iterator(), status=206)
            response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            response["Content-Length"] = str(content_length)
        else:
            with open(video_path, "rb") as f:
                f.seek(start)
                content = f.read(content_length)
            response = HttpResponse(content, status=206)
            response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            response["Content-Length"] = str(len(content))

        response["Content-Type"] = content_type
        response["Accept-Ranges"] = "bytes"
        response["Cache-Control"] = "public, max-age=3600"
        if etag:
            response["ETag"] = etag
        return response

    def get(self, request, lesson_id):
        data, err = self._get_lesson_and_file(request, lesson_id)
        if err is not None:
            return err
        lesson, video_path, content_type, file_size = data
        range_header = (request.META.get("HTTP_RANGE") or "").strip()
        if not range_header:
            # Без Range — отдаём весь файл потоком (не грузим в память), как один диапазон 0-(size-1)
            start, end = 0, file_size - 1
            content_length = file_size
            etag = _video_stream_etag(video_path)
            if etag and request.META.get("HTTP_IF_NONE_MATCH", "").strip() == etag:
                r = HttpResponseNotModified()
                r["ETag"] = etag
                r["Cache-Control"] = "public, max-age=3600"
                r["Accept-Ranges"] = "bytes"
                return r

            def full_file_iterator():
                with open(video_path, "rb") as f:
                    remaining = file_size
                    while remaining > 0:
                        chunk_size = min(VIDEO_STREAM_CHUNK_SIZE, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                        remaining -= len(chunk)

            response = StreamingHttpResponse(full_file_iterator(), status=200)
            response["Content-Length"] = str(file_size)
            response["Content-Type"] = content_type
            response["Accept-Ranges"] = "bytes"
            response["Cache-Control"] = "public, max-age=3600"
            if etag:
                response["ETag"] = etag
            return response

        return self._build_stream_response(
            request, video_path, content_type, file_size, head_only=False
        )

    def head(self, request, lesson_id):
        """HEAD: те же заголовки, что и GET (Content-Length, Accept-Ranges, ETag), без тела."""
        data, err = self._get_lesson_and_file(request, lesson_id)
        if err is not None:
            return err
        lesson, video_path, content_type, file_size = data
        range_header = (request.META.get("HTTP_RANGE") or "").strip()
        if not range_header:
            etag = _video_stream_etag(video_path)
            if etag and request.META.get("HTTP_IF_NONE_MATCH", "").strip() == etag:
                r = HttpResponseNotModified()
                r["ETag"] = etag
                r["Cache-Control"] = "public, max-age=3600"
                r["Accept-Ranges"] = "bytes"
                return r
            response = HttpResponse(status=200)
            response["Content-Length"] = str(file_size)
            response["Content-Type"] = content_type
            response["Accept-Ranges"] = "bytes"
            response["Cache-Control"] = "public, max-age=3600"
            if etag:
                response["ETag"] = etag
            return response
        return self._build_stream_response(
            request, video_path, content_type, file_size, head_only=True
        )


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

