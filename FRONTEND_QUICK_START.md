# Быстрый старт: Работа с видео API

## 🚀 Основные примеры

### 1. Загрузка видео (Преподаватель)

```javascript
const formData = new FormData();
formData.append('course', courseId);
formData.append('title', 'Название урока');
formData.append('video_file', fileInput.files[0]);

const response = await fetch('/api/teacher/lessons/create-with-upload/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

const lesson = await response.json();
```

### 2. Открытие урока (Студент)

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

### 3. Отображение видео

```javascript
// Если есть video_file_url - используем его
if (lesson.video_file_url) {
  const videoResponse = await fetch(lesson.video_file_url, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const blob = await videoResponse.blob();
  videoElement.src = URL.createObjectURL(blob);
} 
// Иначе используем video_url (YouTube или внешняя ссылка)
else if (lesson.video_url) {
  videoElement.src = lesson.video_url;
}
```

### 4. React компонент (минимальный)

```jsx
function VideoPlayer({ lessonId }) {
  const [videoUrl, setVideoUrl] = useState(null);
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    async function load() {
      // Открываем урок
      const res = await fetch('/api/lessons/open/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ lesson_id: lessonId })
      });
      const { lesson } = await res.json();

      // Загружаем видео
      if (lesson.video_file_url) {
        const videoRes = await fetch(lesson.video_file_url, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const blob = await videoRes.blob();
        setVideoUrl(URL.createObjectURL(blob));
      } else {
        setVideoUrl(lesson.video_url);
      }
    }
    load();
  }, [lessonId, token]);

  return videoUrl ? <video controls src={videoUrl} /> : <div>Загрузка...</div>;
}
```

## 📋 Структура данных урока

```json
{
  "id": 123,
  "title": "Название",
  "video_url": "",                    // YouTube URL или пустая строка
  "video_file_url": "/api/lessons/123/video/",  // URL локального видео
  "youtube_status": "ready",         // ready, uploading, processing, error
  "video_duration": "00:15:30",
  "description": "Описание"
}
```

## ⚠️ Важные моменты

1. **Авторизация**: Все запросы требуют `Authorization: Bearer <token>`
2. **Формат загрузки**: Используйте `FormData` для загрузки файлов
3. **Размер файла**: Максимум 20GB (валидируйте на клиенте перед отправкой)
4. **Приоритет видео**: `video_file_url` > `video_url`
5. **Очистка**: Не забывайте `URL.revokeObjectURL()` для blob URL
6. **Прогресс загрузки**: Используйте `XMLHttpRequest` вместо `fetch` для отслеживания прогресса
7. **Большие файлы**: Показывайте предупреждения и прогресс для файлов >5GB

## 🔗 Endpoints

- `POST /api/teacher/lessons/create-with-upload/` - Загрузка урока с видео
- `POST /api/lessons/open/` - Открытие урока (студент)
- `GET /api/lessons/{id}/video/` - Потоковая передача видео
- `GET /api/teacher/lessons/{id}/` - Получение урока (преподаватель)

## 📚 Документация

- [Полная документация API](./FRONTEND_VIDEO_API.md) - все endpoints и примеры
- [Руководство по оптимизации](./FRONTEND_OPTIMIZATION_GUIDE.md) - как правильно работать с большими файлами
