# Документация API для работы с видео (Фронтенд)

## ⚡ Важно: Оптимизация для больших файлов

**Сервер оптимизирован для безопасной загрузки больших видео файлов (до 20GB).**
- ✅ Файлы обрабатываются потоково, без загрузки в память сервера
- ✅ Безопасно загружать файлы любого размера (до 20GB)
- ✅ Рекомендуется использовать прогресс-бар для отслеживания загрузки
- ✅ Для больших файлов (>1GB) загрузка может занять время - это нормально

## Содержание
1. [Загрузка видео (Преподаватель)](#загрузка-видео)
2. [Получение информации об уроке](#получение-информации-об-уроке)
3. [Открытие урока (Студент)](#открытие-урока)
4. [Потоковая передача видео](#потоковая-передача-видео)
5. [Плеер уровня YouTube (Video.js)](#плеер-уровня-youtube-videojs)
6. [Примеры использования](#примеры-использования)
7. [Обработка ошибок](#обработка-ошибок)
8. [Рекомендации для больших файлов](#рекомендации-для-больших-файлов)

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

### Пример с React (с прогресс-баром)

```jsx
import { useState } from 'react';

function LessonUploadForm({ courseId }) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [uploadSpeed, setUploadSpeed] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setUploading(true);
    setError(null);
    setProgress(0);

    const formData = new FormData(e.target);
    formData.append('course', courseId);
    
    const file = formData.get('video_file');
    const fileSize = file?.size || 0;
    const startTime = Date.now();

    try {
      const token = localStorage.getItem('access_token');
      
      const xhr = new XMLHttpRequest();
      
      // Отслеживание прогресса загрузки
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const percentComplete = (e.loaded / e.total) * 100;
          setProgress(percentComplete);
          
          // Расчет скорости загрузки
          const elapsed = (Date.now() - startTime) / 1000; // секунды
          const speed = e.loaded / elapsed; // байт/сек
          setUploadSpeed(formatBytes(speed));
          
          // Расчет оставшегося времени
          if (speed > 0) {
            const remaining = (e.total - e.loaded) / speed;
            setTimeRemaining(formatTime(remaining));
          }
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status === 201) {
          const lesson = JSON.parse(xhr.responseText);
          console.log('Урок загружен:', lesson);
          setUploading(false);
          setProgress(100);
          // Перенаправление или обновление списка уроков
        } else {
          const error = JSON.parse(xhr.responseText);
          setError(error.detail || 'Ошибка загрузки');
          setUploading(false);
        }
      });

      xhr.addEventListener('error', () => {
        setError('Ошибка сети при загрузке файла');
        setUploading(false);
      });

      xhr.addEventListener('abort', () => {
        setError('Загрузка отменена');
        setUploading(false);
      });

      // Устанавливаем таймаут для больших файлов (30 минут)
      xhr.timeout = 30 * 60 * 1000;
      xhr.addEventListener('timeout', () => {
        setError('Превышено время ожидания. Попробуйте еще раз.');
        setUploading(false);
      });

      xhr.open('POST', '/api/teacher/lessons/create-with-upload/');
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.send(formData);

    } catch (err) {
      setError(err.message);
      setUploading(false);
    }
  };

  // Вспомогательные функции для форматирования
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i] + '/s';
  };

  const formatTime = (seconds) => {
    if (seconds < 60) return `${Math.round(seconds)} сек`;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes} мин ${secs} сек`;
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
        <div className="upload-progress">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="progress-info">
            <span>{progress.toFixed(1)}%</span>
            {uploadSpeed && <span>Скорость: {uploadSpeed}</span>}
            {timeRemaining && <span>Осталось: {timeRemaining}</span>}
          </div>
          <small>
            ⚠️ Не закрывайте страницу во время загрузки. 
            Для больших файлов это может занять несколько минут.
          </small>
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
Поддерживает два способа:
1. **Authorization header**: `Authorization: Bearer <token>` (для API запросов)
2. **Query параметр**: `?token=<token>` (для прямого использования в `<video src>`)

### Особенности
- Поддерживает **Range requests** (HTTP 206 Partial Content)
- Позволяет перемотку видео
- Работает с большими файлами (до 20GB)
- Требует авторизации и проверки доступа
- **Оптимально**: Используйте токен в query-параметре для стриминга (не загружает файл целиком)

### Пример использования с HTML5 Video (Оптимальный способ - стриминг)

**✅ Рекомендуемый способ:** Используйте прямой URL с токеном в query-параметре. 
API автоматически возвращает `video_file_url` с токеном, который можно использовать напрямую.

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
  
  // Получаем урок с video_file_url (уже содержит токен)
  const response = await fetch('/api/lessons/open/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ lesson_id: lessonId })
  });

  if (!response.ok) {
    throw new Error('Не удалось загрузить урок');
  }

  const { lesson } = await response.json();
  const videoElement = document.getElementById('lesson-video');
  
  // video_file_url уже содержит токен: /api/lessons/123/video/?token=xxx
  // Используем прямой URL - браузер сам будет стримить видео по частям
  if (lesson.video_file_url) {
    videoElement.src = lesson.video_file_url; // ✅ Стриминг, не загружает весь файл
  } else if (lesson.video_url) {
    videoElement.src = lesson.video_url;
  }
}

// Использование
loadVideo(123);
</script>
```

**❌ Неправильный способ (загружает весь файл):**
```javascript
// ПЛОХО: Загружает весь файл в память браузера
const response = await fetch(videoUrl, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const blob = await response.blob(); // Загружает ВЕСЬ файл!
videoElement.src = URL.createObjectURL(blob);
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

### Пример с React и нативным video элементом (Оптимальный - стриминг)

```jsx
import { useState, useEffect } from 'react';

function VideoPlayer({ lessonId }) {
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    async function loadVideo() {
      try {
        // Открываем урок и получаем video_file_url с токеном
        const response = await fetch('/api/lessons/open/', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ lesson_id: lessonId })
        });

        if (!response.ok) {
          throw new Error('Не удалось загрузить урок');
        }

        const { lesson } = await response.json();
        
        // video_file_url уже содержит токен в query-параметре
        // Используем прямой URL - браузер сам будет стримить видео
        if (lesson.video_file_url) {
          setVideoUrl(lesson.video_file_url); // ✅ Стриминг
        } else if (lesson.video_url) {
          setVideoUrl(lesson.video_url);
        } else {
          throw new Error('Видео не найдено');
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadVideo();
  }, [lessonId, token]);

  if (loading) {
    return <div>Загрузка...</div>;
  }

  if (error) {
    return <div>Ошибка: {error}</div>;
  }

  if (!videoUrl) {
    return <div>Видео не найдено</div>;
  }

  return (
    <video 
      controls 
      preload="metadata"  // Загружает только метаданные, не весь файл
      src={videoUrl}
      style={{ width: '100%', maxWidth: '800px' }}
      onError={(e) => {
        console.error('Ошибка воспроизведения видео:', e);
        setError('Ошибка воспроизведения видео');
      }}
    />
  );
}
```

**Преимущества этого подхода:**
- ✅ Видео стримится по частям, не загружается целиком
- ✅ Поддержка перемотки работает сразу
- ✅ Меньше использование памяти браузера
- ✅ Быстрый старт воспроизведения

---

## Плеер уровня YouTube (Video.js)

Чтобы воспроизведение на фронте было на уровне YouTube (скорость, полноэкранный режим, буферизация, удобные контролы), используйте **Video.js** и подставляйте в плеер **прямой URL** `video_file_url` — так видео стримится, без загрузки всего файла в память.

### Что даёт уровень YouTube

- **Скорость воспроизведения** — 0.5x, 0.75x, 1x, 1.25x, 1.5x, 2x
- **Полноэкранный режим** и Picture-in-Picture (где поддерживается)
- **Перемотка по прогресс-бару** — сервер уже отдаёт по Range
- **Буферизация** — `preload="auto"` для плавного просмотра
- **Адаптивная вёрстка** — `fluid: true` (16:9)
- **Клавиатура** — пробел (play/pause), стрелки (перемотка)

### Подключение Video.js (CDN)

```html
<link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet">
<video id="lesson-video" class="video-js vjs-big-play-centered vjs-fluid" controls preload="auto" playsinline></video>
<script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
```

### Инициализация со стримингом (без загрузки всего файла)

**Важно:** передавайте в плеер именно `lesson.video_file_url` (URL с токеном). Не используйте `fetch` + `blob` — иначе файл скачается целиком.

```javascript
// 1. Открыть урок и получить video_file_url
const response = await fetch('/api/lessons/open/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ lesson_id: lessonId })
});
const { lesson } = await response.json();

// 2. Инициализация Video.js один раз
const player = videojs('lesson-video', {
  controls: true,
  fluid: true,
  preload: 'auto',
  playbackRates: [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]
});

// 3. Подставить URL — браузер будет стримить по Range
player.src({ type: 'video/mp4', src: lesson.video_file_url });
```

### React: плеер уровня YouTube

```jsx
import { useEffect, useRef, useState } from 'react';
import videojs from 'video.js';
import 'video.js/dist/video-js.css';

function YouTubeLevelPlayer({ lessonId }) {
  const videoRef = useRef(null);
  const playerRef = useRef(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    async function load() {
      if (!lessonId || !token) {
        setLoading(false);
        return;
      }
      try {
        const res = await fetch('/api/lessons/open/', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ lesson_id: lessonId })
        });
        if (!res.ok) throw new Error('Не удалось загрузить урок');
        const { lesson } = await res.json();
        const url = lesson.video_file_url || lesson.video_url;
        if (!url) throw new Error('Видео не найдено');
        setVideoUrl(url);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [lessonId, token]);

  useEffect(() => {
    if (!videoRef.current || !videoUrl) return;
    const player = videojs(videoRef.current, {
      controls: true,
      fluid: true,
      preload: 'auto',
      playbackRates: [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2],
      sources: [{ src: videoUrl, type: 'video/mp4' }]
    });
    playerRef.current = player;
    return () => {
      player.dispose();
      playerRef.current = null;
    };
  }, [videoUrl]);

  if (loading) return <div>Загрузка…</div>;
  if (error) return <div className="error">Ошибка: {error}</div>;
  if (!videoUrl) return null;

  return (
    <div data-vjs-player>
      <video ref={videoRef} className="video-js vjs-big-play-centered" playsInline />
    </div>
  );
}
```

### Готовый пример

В репозитории есть готовый HTML-пример: **`frontend-examples/youtube-level-player.html`**. Подставьте свой `API_BASE` и способ получения токена (например, `localStorage.getItem('access_token')`), откройте файл в браузере и введите ID урока — видео будет воспроизводиться через стриминг, как на YouTube.

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
6. **Оптимизация бекенда**: Сервер обрабатывает файлы потоково, безопасно загружать файлы до 20GB

---

## Рекомендации для больших файлов

### ⚡ Оптимизации бекенда

Бекенд оптимизирован для работы с большими файлами:
- ✅ Файлы обрабатываются потоково (по частям), не загружаются целиком в память
- ✅ Автоматическое сохранение на диск для файлов > 2MB
- ✅ Максимальное использование памяти: ~8-10MB независимо от размера файла
- ✅ Безопасно загружать файлы до 20GB

### 📋 Что нужно делать на фронтенде

1. **Используйте XMLHttpRequest для загрузки**
   ```javascript
   // ✅ ХОРОШО: Поддерживает отслеживание прогресса
   const xhr = new XMLHttpRequest();
   xhr.upload.addEventListener('progress', (e) => {
     const percent = (e.loaded / e.total) * 100;
     updateProgress(percent);
   });
   
   // ❌ ПЛОХО: fetch не поддерживает отслеживание прогресса
   await fetch(url, { method: 'POST', body: formData });
   ```

2. **Валидируйте размер файла на клиенте**
   ```javascript
   const maxSize = 20 * 1024 * 1024 * 1024; // 20GB
   if (file.size > maxSize) {
     alert('Файл слишком большой');
     return;
   }
   ```

3. **Показывайте прогресс загрузки**
   - Процент выполнения
   - Скорость загрузки
   - Оставшееся время
   - Размер загруженного / общий размер

4. **Предупреждайте о больших файлах**
   ```javascript
   if (file.size > 5 * 1024 * 1024 * 1024) { // > 5GB
     alert('Файл большой, загрузка может занять время');
   }
   ```

5. **Защищайте от случайного закрытия**
   ```javascript
   window.addEventListener('beforeunload', (e) => {
     if (isUploading) {
       e.preventDefault();
       e.returnValue = 'Загрузка не завершена';
     }
   });
   ```

6. **Устанавливайте разумные таймауты**
   ```javascript
   xhr.timeout = 30 * 60 * 1000; // 30 минут для больших файлов
   ```

### 📖 Подробное руководство

Для детальной информации о том, как оптимизированно работать с API, см.:
**[FRONTEND_OPTIMIZATION_GUIDE.md](./FRONTEND_OPTIMIZATION_GUIDE.md)** - полное руководство с примерами кода

---

## Дополнительные ресурсы

- [MDN: Using Fetch](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch)
- [MDN: Using files from web applications](https://developer.mozilla.org/en-US/docs/Web/API/File_API/Using_files_from_web_applications)
- [MDN: XMLHttpRequest.upload](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/upload)
- [Video.js Documentation](https://videojs.com/getting-started/)
