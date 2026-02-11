# Документация API для работы с видео (Фронтенд)

## Содержание
1. [Загрузка видео (Преподаватель)](#загрузка-видео)
2. [Получение информации об уроке](#получение-информации-об-уроке)
3. [Открытие урока (Студент)](#открытие-урока)
4. [Потоковая передача видео](#потоковая-передача-видео)
5. [Примеры использования](#примеры-использования)
6. [Обработка ошибок](#обработка-ошибок)

---

## Загрузка видео

### Endpoint
```
POST /api/teacher/lessons/create-with-upload/
```

### Авторизация
Требуется: `Authorization: Bearer <token>` (роль: teacher)

### Параметры запроса

**FormData** (multipart/form-data):

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| `course` | number | ✅ Да | ID курса |
| `title` | string | ✅ Да | Название урока (макс. 255 символов) |
| `description` | string | ❌ Нет | Описание урока |
| `video_file` | File | ⚠️ Условно | Файл видео (до 20GB) |
| `video_url` | string | ⚠️ Условно | URL видео (альтернатива video_file) |
| `homework_title` | string | ❌ Нет | Название ДЗ |
| `homework_description` | string | ❌ Нет | Описание ДЗ |
| `homework_link` | string | ❌ Нет | Ссылка на ДЗ |
| `homework_file` | File | ❌ Нет | Файл ДЗ |

**Важно:** Нужно указать либо `video_file`, либо `video_url` (но не оба одновременно).

### Пример запроса (JavaScript)

```javascript
// Загрузка видео файла
async function uploadLessonVideo(formData) {
  const token = localStorage.getItem('access_token');
  
  try {
    const response = await fetch('/api/teacher/lessons/create-with-upload/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        // НЕ указывайте Content-Type - браузер установит его автоматически с boundary
      },
      body: formData
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Ошибка загрузки');
    }

    const lesson = await response.json();
    return lesson;
  } catch (error) {
    console.error('Ошибка загрузки видео:', error);
    throw error;
  }
}

// Использование
const formData = new FormData();
formData.append('course', 1);
formData.append('title', 'Введение в Python');
formData.append('description', 'Первый урок курса');
formData.append('video_file', videoFileInput.files[0]); // File объект из <input type="file">

const lesson = await uploadLessonVideo(formData);
console.log('Урок создан:', lesson);
```

### Пример с React

```jsx
import { useState } from 'react';

function LessonUploadForm({ courseId }) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setUploading(true);
    setError(null);

    const formData = new FormData(e.target);
    formData.append('course', courseId);

    try {
      const token = localStorage.getItem('access_token');
      
      const xhr = new XMLHttpRequest();
      
      // Отслеживание прогресса загрузки
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const percentComplete = (e.loaded / e.total) * 100;
          setProgress(percentComplete);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status === 201) {
          const lesson = JSON.parse(xhr.responseText);
          console.log('Урок загружен:', lesson);
          setUploading(false);
          // Перенаправление или обновление списка уроков
        } else {
          const error = JSON.parse(xhr.responseText);
          setError(error.detail || 'Ошибка загрузки');
          setUploading(false);
        }
      });

      xhr.open('POST', '/api/teacher/lessons/create-with-upload/');
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.send(formData);

    } catch (err) {
      setError(err.message);
      setUploading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input 
        type="text" 
        name="title" 
        placeholder="Название урока" 
        required 
      />
      <textarea 
        name="description" 
        placeholder="Описание"
      />
      <input 
        type="file" 
        name="video_file" 
        accept="video/*"
        required
      />
      
      {uploading && (
        <div>
          <progress value={progress} max="100" />
          <span>{progress.toFixed(1)}%</span>
        </div>
      )}
      
      {error && <div className="error">{error}</div>}
      
      <button type="submit" disabled={uploading}>
        {uploading ? 'Загрузка...' : 'Загрузить урок'}
      </button>
    </form>
  );
}
```

### Ответ сервера

**Успех (201 Created):**
```json
{
  "id": 123,
  "course": 1,
  "title": "Введение в Python",
  "order": 0,
  "description": "Первый урок курса",
  "video_url": "",
  "video_file_url": "http://example.com/api/lessons/123/video/",
  "youtube_video_id": "",
  "youtube_status": "ready",
  "youtube_error": "",
  "video_duration": "00:15:30",
  "is_archived": false,
  "homework_title": "",
  "homework_description": "",
  "homework_link": "",
  "homework_file": null,
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Ошибка (400 Bad Request):**
```json
{
  "detail": "Файл слишком большой (25.5GB). Максимальный размер: 20GB",
  "lesson_id": 123
}
```

---

## Получение информации об уроке

### Endpoint (для преподавателя)
```
GET /api/teacher/lessons/{id}/
```

### Endpoint (для студента - после открытия урока)
```
POST /api/lessons/open/
```

### Пример получения урока (Преподаватель)

```javascript
async function getLesson(lessonId) {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch(`/api/teacher/lessons/${lessonId}/`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  if (!response.ok) {
    throw new Error('Урок не найден');
  }

  return await response.json();
}
```

### Структура ответа

```json
{
  "id": 123,
  "course": 1,
  "title": "Введение в Python",
  "order": 0,
  "description": "Описание урока",
  "video_url": "", // Может быть YouTube URL или пустая строка
  "video_file_url": "http://example.com/api/lessons/123/video/", // URL для локального видео
  "youtube_video_id": "",
  "youtube_status": "ready", // idle, uploading, processing, ready, error
  "youtube_error": "",
  "video_duration": "00:15:30", // Формат: HH:MM:SS или null
  "is_archived": false,
  "homework_title": "Домашнее задание",
  "homework_description": "Описание ДЗ",
  "homework_link": "https://example.com/homework",
  "homework_file": null,
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Важно:** 
- Если `video_file_url` не `null` - используйте его для отображения локального видео
- Если `video_url` не пустая строка - это может быть YouTube URL или внешняя ссылка
- `youtube_status` показывает статус обработки: `ready` - готово, `uploading` - загружается, `processing` - обрабатывается, `error` - ошибка

---

## Открытие урока

### Endpoint
```
POST /api/lessons/open/
```

### Авторизация
Требуется: `Authorization: Bearer <token>` (роль: student)

### Параметры запроса

```json
{
  "lesson_id": 123
}
```

### Пример запроса

```javascript
async function openLesson(lessonId) {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('/api/lessons/open/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ lesson_id: lessonId })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Ошибка открытия урока');
  }

  const data = await response.json();
  return data.lesson; // Объект урока с video_file_url
}
```

### Ответ сервера

```json
{
  "lesson": {
    "id": 123,
    "title": "Введение в Python",
    "video_url": "",
    "video_file_url": "http://example.com/api/lessons/123/video/",
    "youtube_video_id": "",
    "youtube_status": "ready",
    "description": "Описание урока",
    "video_duration": "00:15:30",
    "homework_title": "ДЗ",
    "homework_description": "Описание ДЗ",
    "homework_link": "https://example.com/homework"
  }
}
```

---

## Потоковая передача видео

### Endpoint
```
GET /api/lessons/{lesson_id}/video/
```

### Авторизация
Требуется: `Authorization: Bearer <token>`

### Особенности
- Поддерживает **Range requests** (HTTP 206 Partial Content)
- Позволяет перемотку видео
- Работает с большими файлами (до 20GB)
- Требует авторизации и проверки доступа

### Пример использования с HTML5 Video

```html
<video 
  id="lesson-video" 
  controls 
  preload="metadata"
  style="width: 100%; max-width: 800px;"
>
  Ваш браузер не поддерживает видео.
</video>

<script>
async function loadVideo(lessonId) {
  const token = localStorage.getItem('access_token');
  const videoUrl = `/api/lessons/${lessonId}/video/`;
  
  // Добавляем токен в URL (если сервер не принимает его в заголовке для video тега)
  // Или используем fetch для получения blob URL
  const response = await fetch(videoUrl, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  if (!response.ok) {
    throw new Error('Не удалось загрузить видео');
  }

  const blob = await response.blob();
  const videoElement = document.getElementById('lesson-video');
  videoElement.src = URL.createObjectURL(blob);
}

// Использование
loadVideo(123);
</script>
```

### Пример с React и Video.js

```jsx
import { useEffect, useRef } from 'react';
import videojs from 'video.js';
import 'video.js/dist/video-js.css';

function VideoPlayer({ lessonId, token }) {
  const videoRef = useRef(null);
  const playerRef = useRef(null);

  useEffect(() => {
    if (!videoRef.current) return;

    // Создаем URL с токеном
    const videoUrl = `/api/lessons/${lessonId}/video/`;
    
    // Инициализация Video.js
    const player = videojs(videoRef.current, {
      controls: true,
      responsive: true,
      fluid: true,
      playbackRates: [0.5, 1, 1.25, 1.5, 2],
      sources: [{
        src: videoUrl,
        type: 'video/mp4'
      }]
    });

    playerRef.current = player;

    // Добавляем токен в заголовки (через fetch для получения blob)
    fetch(videoUrl, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
      .then(response => response.blob())
      .then(blob => {
        const blobUrl = URL.createObjectURL(blob);
        player.src({ src: blobUrl, type: 'video/mp4' });
      })
      .catch(error => {
        console.error('Ошибка загрузки видео:', error);
      });

    return () => {
      if (playerRef.current) {
        playerRef.current.dispose();
      }
    };
  }, [lessonId, token]);

  return (
    <div data-vjs-player>
      <video
        ref={videoRef}
        className="video-js vjs-big-play-centered"
        playsInline
      />
    </div>
  );
}
```

### Пример с React и нативным video элементом

```jsx
import { useState, useEffect } from 'react';

function VideoPlayer({ lessonId }) {
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    async function loadVideo() {
      try {
        const response = await fetch(`/api/lessons/${lessonId}/video/`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (!response.ok) {
          throw new Error('Не удалось загрузить видео');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setVideoUrl(url);
      } catch (err) {
        setError(err.message);
      }
    }

    loadVideo();

    // Очистка URL при размонтировании
    return () => {
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
      }
    };
  }, [lessonId, token]);

  if (error) {
    return <div>Ошибка: {error}</div>;
  }

  if (!videoUrl) {
    return <div>Загрузка видео...</div>;
  }

  return (
    <video 
      controls 
      src={videoUrl}
      style={{ width: '100%', maxWidth: '800px' }}
    />
  );
}
```

### Альтернативный способ (с токеном в URL параметре)

Если сервер поддерживает токен в query параметре:

```jsx
function VideoPlayer({ lessonId }) {
  const token = localStorage.getItem('access_token');
  const videoUrl = `/api/lessons/${lessonId}/video/?token=${token}`;

  return (
    <video 
      controls 
      src={videoUrl}
      style={{ width: '100%', maxWidth: '800px' }}
    />
  );
}
```

---

## Примеры использования

### Полный пример: Загрузка и просмотр урока

```javascript
// 1. Преподаватель загружает урок
async function createLessonWithVideo(courseId, title, videoFile) {
  const formData = new FormData();
  formData.append('course', courseId);
  formData.append('title', title);
  formData.append('video_file', videoFile);

  const token = localStorage.getItem('access_token');
  const response = await fetch('/api/teacher/lessons/create-with-upload/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  return await response.json();
}

// 2. Студент открывает урок
async function openLesson(lessonId) {
  const token = localStorage.getItem('access_token');
  const response = await fetch('/api/lessons/open/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ lesson_id: lessonId })
  });

  const data = await response.json();
  return data.lesson;
}

// 3. Отображение видео
function displayVideo(lesson) {
  const videoElement = document.getElementById('video-player');
  
  // Приоритет: video_file_url > video_url
  if (lesson.video_file_url) {
    // Локальное видео через потоковую передачу
    loadVideoStream(lesson.video_file_url, videoElement);
  } else if (lesson.video_url) {
    // YouTube или внешняя ссылка
    if (lesson.video_url.includes('youtube.com') || lesson.video_url.includes('youtu.be')) {
      // Встраивание YouTube
      const videoId = extractYouTubeId(lesson.video_url);
      videoElement.src = `https://www.youtube.com/embed/${videoId}`;
    } else {
      // Прямая ссылка
      videoElement.src = lesson.video_url;
    }
  }
}

async function loadVideoStream(videoUrl, videoElement) {
  const token = localStorage.getItem('access_token');
  
  try {
    const response = await fetch(videoUrl, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      throw new Error('Не удалось загрузить видео');
    }

    const blob = await response.blob();
    videoElement.src = URL.createObjectURL(blob);
  } catch (error) {
    console.error('Ошибка загрузки видео:', error);
  }
}

// Использование
const lesson = await openLesson(123);
displayVideo(lesson);
```

### React компонент: Полный пример

```jsx
import { useState, useEffect } from 'react';

function LessonView({ lessonId }) {
  const [lesson, setLesson] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    async function loadLesson() {
      try {
        // Открываем урок
        const response = await fetch('/api/lessons/open/', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ lesson_id: lessonId })
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Ошибка загрузки урока');
        }

        const data = await response.json();
        const lessonData = data.lesson;
        setLesson(lessonData);

        // Загружаем видео
        if (lessonData.video_file_url) {
          const videoResponse = await fetch(lessonData.video_file_url, {
            headers: {
              'Authorization': `Bearer ${token}`
            }
          });

          if (videoResponse.ok) {
            const blob = await videoResponse.blob();
            setVideoUrl(URL.createObjectURL(blob));
          }
        } else if (lessonData.video_url) {
          setVideoUrl(lessonData.video_url);
        }

        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    }

    loadLesson();

    // Очистка
    return () => {
      if (videoUrl && videoUrl.startsWith('blob:')) {
        URL.revokeObjectURL(videoUrl);
      }
    };
  }, [lessonId, token]);

  if (loading) {
    return <div>Загрузка...</div>;
  }

  if (error) {
    return <div className="error">Ошибка: {error}</div>;
  }

  if (!lesson) {
    return <div>Урок не найден</div>;
  }

  return (
    <div className="lesson-view">
      <h1>{lesson.title}</h1>
      <p>{lesson.description}</p>
      
      {videoUrl && (
        <video 
          controls 
          src={videoUrl}
          style={{ width: '100%', maxWidth: '800px' }}
        />
      )}

      {lesson.video_duration && (
        <p>Длительность: {lesson.video_duration}</p>
      )}

      {lesson.homework_title && (
        <div className="homework">
          <h3>{lesson.homework_title}</h3>
          <p>{lesson.homework_description}</p>
          {lesson.homework_link && (
            <a href={lesson.homework_link} target="_blank" rel="noopener noreferrer">
              Ссылка на ДЗ
            </a>
          )}
        </div>
      )}
    </div>
  );
}

export default LessonView;
```

---

## Обработка ошибок

### Коды ошибок

| Код | Описание | Решение |
|-----|----------|---------|
| 400 | Неверные данные запроса | Проверьте формат данных |
| 401 | Не авторизован | Проверьте токен авторизации |
| 402 | Недостаточно прав по тарифу | Студент пытается открыть урок вне тарифа |
| 403 | Нет доступа | Проверьте права доступа |
| 404 | Урок/видео не найдено | Проверьте ID урока |
| 413 | Файл слишком большой | Максимальный размер: 20GB |

### Пример обработки ошибок

```javascript
async function handleVideoUpload(formData) {
  try {
    const response = await fetch('/api/teacher/lessons/create-with-upload/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });

    if (!response.ok) {
      const error = await response.json();
      
      switch (response.status) {
        case 400:
          if (error.detail?.includes('слишком большой')) {
            alert('Файл слишком большой. Максимальный размер: 20GB');
          } else {
            alert('Ошибка валидации: ' + error.detail);
          }
          break;
        case 401:
          alert('Сессия истекла. Пожалуйста, войдите снова.');
          // Перенаправление на страницу входа
          break;
        case 403:
          alert('У вас нет доступа к этому действию');
          break;
        default:
          alert('Произошла ошибка: ' + (error.detail || 'Неизвестная ошибка'));
      }
      
      throw new Error(error.detail || 'Ошибка загрузки');
    }

    return await response.json();
  } catch (error) {
    console.error('Ошибка:', error);
    throw error;
  }
}
```

### Отслеживание статуса загрузки

```javascript
// Статусы youtube_status:
// - "idle" - не загружается
// - "uploading" - загружается
// - "processing" - обрабатывается
// - "ready" - готово
// - "error" - ошибка

function checkUploadStatus(lessonId) {
  return setInterval(async () => {
    const lesson = await getLesson(lessonId);
    
    if (lesson.youtube_status === 'ready') {
      console.log('Видео готово!');
      // Обновить UI
    } else if (lesson.youtube_status === 'error') {
      console.error('Ошибка:', lesson.youtube_error);
      // Показать ошибку
    } else {
      console.log('Статус:', lesson.youtube_status);
      // Показать прогресс
    }
  }, 5000); // Проверка каждые 5 секунд
}
```

---

## Полезные советы

1. **Прогресс загрузки**: Используйте `XMLHttpRequest` вместо `fetch` для отслеживания прогресса загрузки больших файлов
2. **Кэширование**: Видео файлы кэшируются на 1 час (Cache-Control)
3. **Размер файлов**: Для файлов >10GB процесс сжатия может занять значительное время
4. **Форматы**: Поддерживаются все форматы, которые понимает ffmpeg (MP4, AVI, MOV, MKV и др.)
5. **Безопасность**: Все запросы требуют авторизации, студенты могут смотреть только доступные им уроки

---

## Дополнительные ресурсы

- [MDN: Using Fetch](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch)
- [MDN: Using files from web applications](https://developer.mozilla.org/en-US/docs/Web/API/File_API/Using_files_from_web_applications)
- [Video.js Documentation](https://videojs.com/getting-started/)
