# Документация проекта (курсы, видео)

Единое руководство: настройка сервера, API, загрузка и просмотр видео, оптимизация, админка.

---

## Содержание

1. [Быстрый старт](#1-быстрый-старт)
2. [Настройка сервера](#2-настройка-сервера)
3. [API: эндпоинты](#3-api-эндпоинты)
4. [Видео: загрузка и просмотр](#4-видео-загрузка-и-просмотр)
5. [Стриминг и просмотр без авторизации](#5-стриминг-и-просмотр-без-авторизации)
6. [Оптимизация (память, большие файлы)](#6-оптимизация-память-большие-файлы)
7. [Админка](#7-админка)
8. [Ошибки и рекомендации](#8-ошибки-и-рекомендации)

---

## 1. Быстрый старт

### Загрузка видео (преподаватель)

```javascript
const formData = new FormData();
formData.append('course', courseId);
formData.append('title', 'Название урока');
formData.append('video_file', fileInput.files[0]);

const response = await fetch('/api/teacher/lessons/create-with-upload/', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData
});
const lesson = await response.json();
```

### Открытие урока (студент)

```javascript
const response = await fetch('/api/lessons/open/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ lesson_id: 123 })
});
const { lesson } = await response.json();
```

### Просмотр видео

Видео можно смотреть **без авторизации** по прямой ссылке:

```html
<video controls preload="metadata" src="/api/lessons/123/video/"></video>
```

Либо после открытия урока использовать `lesson.video_url` из ответа API (URL всегда приходит из БД).

**Важно:** не загружайте видео через `fetch().blob()` — используйте прямой URL в `src`, чтобы браузер стримил по Range.

---

## 2. Настройка сервера

### ffmpeg

Для сжатия и обработки видео нужен **ffmpeg**.

- **Windows:** https://ffmpeg.org/download.html или `choco install ffmpeg` / `winget install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`
- **macOS:** `brew install ffmpeg`

Проверка: `ffmpeg -version`

### Django (core/settings.py)

- `VIDEO_MAX_SIZE_GB = 20` — макс. размер видео (20GB)
- `VIDEO_COMPRESSION_ENABLED = True` — автосжатие
- Для больших файлов используются временные файлы на диске (не в RAM):
  - `FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024` (2MB)
  - `DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024` (10MB)
  - `FILE_UPLOAD_HANDLERS` с `TemporaryFileUploadHandler` для файлов > 2MB

Видео сохраняются в `media/videos/YYYY/MM/DD/`.

---

## 3. API: эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/teacher/lessons/create-with-upload/` | Загрузка урока с видео (FormData) |
| GET  | `/api/teacher/lessons/{id}/` | Получение урока (преподаватель) |
| POST | `/api/lessons/open/` | Открытие урока (студент), возвращает урок с `video_url` из БД |
| GET  | `/api/lessons/{id}/video/` | Стриминг видео (без авторизации или с Bearer/?token=) |
| HEAD | `/api/lessons/{id}/video/` | Заголовки (Content-Length, Accept-Ranges, ETag) без тела |

### Авторизация

- Загрузка и открытие урока: `Authorization: Bearer <token>`
- Просмотр видео: **не обязательна**. Без токена видео отдаётся любому. С токеном проверяется доступ по тарифу (студент/преподаватель/админ).

---

## 4. Видео: загрузка и просмотр

### Загрузка (FormData)

Поля: `course`, `title`, `description` (опц.), `video_file` **или** `video_url`, `homework_title`, `homework_description`, `homework_link`, `homework_file` (опц.). Максимум файла: 20GB.

Для отслеживания прогресса используйте **XMLHttpRequest**, не `fetch`:

```javascript
const xhr = new XMLHttpRequest();
xhr.upload.addEventListener('progress', (e) => {
  if (e.lengthComputable) {
    const percent = (e.loaded / e.total) * 100;
    updateProgressBar(percent);
  }
});
xhr.open('POST', '/api/teacher/lessons/create-with-upload/');
xhr.setRequestHeader('Authorization', `Bearer ${token}`);
xhr.send(formData);
```

Валидируйте размер на клиенте до отправки (макс. 20GB). Для больших файлов показывайте предупреждение и прогресс; таймаут рекомендуется 30 минут.

### Структура урока (ответ API)

```json
{
  "id": 123,
  "title": "Название",
  "video_url": "/api/lessons/123/video/",
  "youtube_video_id": "",
  "youtube_status": "ready",
  "video_duration": "00:15:30",
  "description": "Описание",
  "homework_title": "",
  "homework_description": "",
  "homework_link": ""
}
```

URL видео везде приходит из БД в поле `video_url` (для загруженного файла сервер сам подставляет URL стриминга при сохранении урока).

### Плеер (Video.js, уровень YouTube)

Подключение: CDN `video.js` + `video-js.css`. Инициализация с прямым URL (стриминг):

```javascript
const player = videojs('lesson-video', {
  controls: true,
  fluid: true,
  preload: 'auto',
  playbackRates: [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]
});
player.src({ type: 'video/mp4', src: '/api/lessons/123/video/' });
```

Готовый пример: `frontend-examples/youtube-level-player.html`.

---

## 5. Стриминг и просмотр без авторизации

- **GET /api/lessons/{id}/video/** — отдаёт видео без обязательной авторизации. Достаточно знать ID урока.
- Поддержка **Range** (206 Partial Content), перемотка и пауза работают.
- Поддержка **HEAD** (размер, Accept-Ranges, ETag).
- **ETag** и **304 Not Modified** при повторных запросах с тем же If-None-Match.
- С **Bearer** или **?token=** дополнительно проверяется доступ (тариф/роль); при отсутствии доступа — 402/403.

Не используйте `fetch(videoUrl).then(r => r.blob())` — это загружает весь файл. Используйте прямой URL в `<video src>` или в Video.js.

---

## 6. Оптимизация (память, большие файлы)

### Бекенд

- Загрузка: файлы > 2MB сохраняются на диск (`TemporaryFileUploadHandler`), не в RAM.
- Обработка: потоковое чтение/запись, буферы ~8MB; копирование через поток, не `shutil.copy2` целиком.
- Стриминг: Range, чанки по 2MB, ETag, 304. Память сервера не зависит от размера файла (порядка 100–200MB при 20GB файле).

### Фронтенд

1. **Загрузка:** XMLHttpRequest + прогресс, валидация размера до отправки, предупреждение для файлов >5GB, защита от закрытия страницы (beforeunload), таймаут 30 мин.
2. **Просмотр:** только прямой URL в `<video src>` или Video.js, без fetch+blob.

---

## 7. Админка

- **Список уроков** (`/admin/users/lesson/`): колонка «Видео файл» (размер, ссылка «Просмотр»), фильтр «Наличие видео файла».
- **Редактирование урока:** поле «Video file», превью-плеер, информация о файле (размер, путь, длительность).
- Просмотр: в форме урока или по кнопке «▶ Просмотр» в новой вкладке.
- Права: суперпользователь и staff — все видео; преподаватель — свои уроки; студент — по тарифу.

Видео хранятся в `media/videos/YYYY/MM/DD/`. Форматы — те, что поддерживает ffmpeg (MP4, AVI, MOV, MKV и др.).

---

## 8. Ошибки и рекомендации

### Коды ответов

| Код | Описание |
|-----|----------|
| 400 | Неверные данные (в т.ч. файл > 20GB) |
| 401 | Не авторизован (для эндпоинтов, требующих токен) |
| 402 | Тариф не позволяет открыть урок |
| 403 | Нет доступа к уроку |
| 404 | Урок или видео не найдено |
| 416 | Неверный заголовок Range |

### Рекомендации

- Прогресс загрузки — только через XHR; валидация размера на клиенте; предупреждения для больших файлов.
- Просмотр — только стриминг (прямой URL), без blob.
- Кэширование: ответы видео с Cache-Control, ETag для 304.
- Максимальный размер файла: 20GB; для продакшена — мониторинг места на диске и таймауты.
