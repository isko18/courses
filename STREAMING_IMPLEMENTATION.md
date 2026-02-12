# Реализация стриминга видео с токеном в URL

## ✅ Что реализовано

### 1. Бекенд: Поддержка токена в query-параметре

**Файл:** `apps/users/views.py` - `VideoStreamView`

- ✅ Поддержка авторизации через `Authorization: Bearer <token>` (header)
- ✅ Поддержка авторизации через `?token=<token>` (query параметр)
- ✅ Потоковая передача с Range requests
- ✅ Оптимизация для больших диапазонов (>10MB использует StreamingHttpResponse)

**Как работает:**
```python
# Проверяет токен из header или query параметра
auth_header = request.META.get('HTTP_AUTHORIZATION', '')
token_param = request.GET.get('token')

# Если есть токен в query - использует его
# Это позволяет использовать прямой URL в <video src>
```

### 2. Сериализаторы: Генерация URL с токеном

**Файл:** `apps/users/serializers.py` - `LessonVideoSerializer`, `TeacherLessonSerializer`

- ✅ Автоматически добавляет токен в query-параметре к `video_file_url`
- ✅ URL готов для прямого использования в `<video src>`

**Пример возвращаемого URL:**
```
/api/lessons/123/video/?token=eyJ0eXAiOiJKV1QiLCJhbGc...
```

### 3. Документация: Обновлены примеры

**Файлы:**
- `FRONTEND_VIDEO_API.md` - обновлены примеры использования
- `FRONTEND_OPTIMIZATION_GUIDE.md` - добавлен раздел о стриминге
- `FRONTEND_QUICK_START.md` - обновлены рекомендации

---

## 🚀 Как использовать на фронтенде

### Простой способ (рекомендуется):

```jsx
function VideoPlayer({ lessonId }) {
  const [videoUrl, setVideoUrl] = useState(null);
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    async function load() {
      // Получаем урок
      const res = await fetch('/api/lessons/open/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ lesson_id: lessonId })
      });
      
      const { lesson } = await res.json();
      
      // video_file_url уже содержит токен: /api/lessons/123/video/?token=xxx
      // Используем прямой URL - браузер сам будет стримить
      if (lesson.video_file_url) {
        setVideoUrl(lesson.video_file_url);
      }
    }
    load();
  }, [lessonId, token]);

  return (
    <video 
      controls 
      preload="metadata"
      src={videoUrl}
    />
  );
}
```

### Преимущества:

1. **Не загружает файл целиком** - браузер запрашивает только нужные части
2. **Поддержка перемотки** - работает сразу, не нужно ждать загрузки
3. **Меньше памяти** - особенно важно для больших файлов (20GB)
4. **Быстрый старт** - видео начинает воспроизводиться сразу

---

## 📊 Сравнение подходов

### ❌ Старый способ (загружает весь файл):

```javascript
// Загружает ВЕСЬ файл в память браузера
const response = await fetch(videoUrl, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const blob = await response.blob(); // 20GB файл = 20GB в памяти!
videoElement.src = URL.createObjectURL(blob);
```

**Проблемы:**
- Загружает весь файл в память
- Для 20GB файла = 20GB в памяти браузера
- Медленный старт (нужно загрузить весь файл)
- Может вызвать OOM в браузере

### ✅ Новый способ (стриминг):

```javascript
// Использует прямой URL - браузер стримит по частям
videoElement.src = lesson.video_file_url; // /api/lessons/123/video/?token=xxx
```

**Преимущества:**
- Загружает только нужные части (Range requests)
- Для 20GB файла = несколько MB в памяти
- Быстрый старт (загружает только начало)
- Безопасно для больших файлов

---

## 🔧 Технические детали

### Как работает Range requests:

1. Браузер отправляет: `GET /api/lessons/123/video/?token=xxx`
2. Сервер отвечает: `206 Partial Content` с заголовком `Content-Range: bytes 0-1048575/21474836480`
3. Браузер запрашивает следующую часть при необходимости
4. При перемотке браузер запрашивает нужную часть: `Range: bytes=10485760-20971519`

### Безопасность:

- Токен проверяется на сервере
- Доступ проверяется (студент/преподаватель/админ)
- Токен в URL безопасен для использования в `<video src>` (HTTPS рекомендуется)

---

## 📝 Чек-лист для фронтенда

- [x] Использовать `video_file_url` из API ответа
- [x] Использовать прямой URL в `<video src>`
- [x] Использовать `preload="metadata"` для оптимизации
- [x] НЕ загружать видео через `fetch().blob()`
- [x] НЕ использовать `preload="auto"` для больших видео

---

## 🎯 Итог

Теперь фронтенд может использовать прямой URL для видео, и браузер сам будет стримить видео по частям через Range requests. Это оптимальный способ для больших файлов (до 20GB).

**Документация обновлена:**
- `FRONTEND_VIDEO_API.md` - примеры использования стриминга
- `FRONTEND_OPTIMIZATION_GUIDE.md` - подробное руководство
- `FRONTEND_QUICK_START.md` - быстрый старт
