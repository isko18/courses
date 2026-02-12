# Руководство по оптимизированной работе с API (Фронтенд)

## 🎯 Цель документа

Этот документ объясняет, как правильно использовать API с учетом оптимизаций бекенда для работы с большими видео файлами (до 20GB) без перегрузки сервера.

---

## 📊 Как работает бекенд

### Оптимизации на стороне сервера

1. **Потоковая обработка файлов**
   - Файлы обрабатываются по частям (chunks), а не целиком
   - Максимальное использование памяти: ~8-10MB независимо от размера файла
   - Файлы сохраняются на диск, а не в RAM

2. **Автоматическое переключение на временные файлы**
   - Файлы > 2MB автоматически сохраняются на диск
   - Не требует дополнительных действий от фронтенда

3. **Оптимизация видео (опционально)**
   - Автоматическое сжатие больших файлов
   - Работает в фоновом режиме, не блокирует ответ

4. **Стриминг видео с поддержкой Range requests**
   - Видео передается по частям, не загружается целиком
   - Поддержка токена в query-параметре для прямого использования в `<video src>`
   - Браузер сам запрашивает нужные части видео (перемотка, пауза)

### Что это значит для фронтенда?

✅ **Можно загружать файлы любого размера** (до 20GB)  
✅ **Не нужно беспокоиться о памяти сервера**  
✅ **Загрузка может занять время** - это нормально для больших файлов  
✅ **Нужно показывать прогресс** - пользователь должен видеть процесс  
✅ **Видео стримится, не загружается целиком** - можно использовать прямой URL в `<video>`  

---

## 🚀 Оптимизированные паттерны кода

### 1. Загрузка файлов: Используйте XMLHttpRequest

**❌ НЕ используйте fetch для больших файлов:**
```javascript
// ПЛОХО: fetch не поддерживает отслеживание прогресса
const response = await fetch('/api/teacher/lessons/create-with-upload/', {
  method: 'POST',
  body: formData
});
```

**✅ Используйте XMLHttpRequest:**
```javascript
// ХОРОШО: XMLHttpRequest поддерживает отслеживание прогресса
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

### 2. Показывайте прогресс загрузки

**Критично для UX при больших файлах:**

```javascript
function uploadWithProgress(formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    
    // Отслеживание прогресса
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        const percent = (e.loaded / e.total) * 100;
        const speed = e.loaded / ((Date.now() - startTime) / 1000);
        const remaining = (e.total - e.loaded) / speed;
        
        onProgress({
          percent,
          loaded: e.loaded,
          total: e.total,
          speed,
          remaining
        });
      }
    });
    
    xhr.addEventListener('load', () => {
      if (xhr.status === 201) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(xhr.responseText));
      }
    });
    
    xhr.addEventListener('error', () => reject(new Error('Network error')));
    
    // Таймаут для больших файлов (30 минут)
    xhr.timeout = 30 * 60 * 1000;
    xhr.addEventListener('timeout', () => reject(new Error('Timeout')));
    
    xhr.open('POST', '/api/teacher/lessons/create-with-upload/');
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.send(formData);
  });
}
```

### 3. Валидация размера на клиенте (до загрузки)

**Проверяйте размер файла ПЕРЕД отправкой:**

```javascript
function validateFileSize(file, maxSizeGB = 20) {
  const maxSizeBytes = maxSizeGB * 1024 * 1024 * 1024;
  
  if (file.size > maxSizeBytes) {
    throw new Error(
      `Файл слишком большой (${(file.size / (1024**3)).toFixed(2)}GB). ` +
      `Максимальный размер: ${maxSizeGB}GB`
    );
  }
  
  return true;
}

// Использование
const file = fileInput.files[0];
try {
  validateFileSize(file);
  // Продолжаем загрузку
} catch (error) {
  alert(error.message);
  return;
}
```

### 4. Показывайте предупреждения для больших файлов

```javascript
function getFileSizeWarning(file) {
  const sizeGB = file.size / (1024 ** 3);
  
  if (sizeGB > 10) {
    return {
      warning: true,
      message: `⚠️ Внимание: Файл очень большой (${sizeGB.toFixed(2)}GB). ` +
               `Загрузка может занять 10-30 минут в зависимости от скорости интернета.`
    };
  } else if (sizeGB > 5) {
    return {
      warning: true,
      message: `⚠️ Файл большой (${sizeGB.toFixed(2)}GB). ` +
               `Загрузка может занять 5-15 минут.`
    };
  }
  
  return { warning: false };
}
```

### 5. Предотвращайте случайное закрытие страницы

```javascript
function setupUploadProtection(isUploading) {
  useEffect(() => {
    if (!isUploading) return;
    
    const handleBeforeUnload = (e) => {
      e.preventDefault();
      e.returnValue = 'Загрузка файла еще не завершена. Вы уверены, что хотите покинуть страницу?';
      return e.returnValue;
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [isUploading]);
}
```

---

## 💡 Полный пример: Оптимизированный компонент загрузки

```jsx
import { useState, useEffect, useRef } from 'react';

function OptimizedVideoUpload({ courseId, onSuccess }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState({
    percent: 0,
    loaded: 0,
    total: 0,
    speed: 0,
    remaining: null
  });
  const [error, setError] = useState(null);
  const [warning, setWarning] = useState(null);
  const xhrRef = useRef(null);
  const startTimeRef = useRef(null);

  // Валидация файла при выборе
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    // Проверка размера
    const maxSizeGB = 20;
    const maxSizeBytes = maxSizeGB * 1024 * 1024 * 1024;
    
    if (selectedFile.size > maxSizeBytes) {
      setError(
        `Файл слишком большой (${(selectedFile.size / (1024**3)).toFixed(2)}GB). ` +
        `Максимальный размер: ${maxSizeGB}GB`
      );
      setFile(null);
      return;
    }

    // Предупреждение для больших файлов
    const sizeGB = selectedFile.size / (1024 ** 3);
    if (sizeGB > 5) {
      setWarning(
        `⚠️ Внимание: Файл большой (${sizeGB.toFixed(2)}GB). ` +
        `Загрузка может занять ${Math.ceil(sizeGB * 2)}-${Math.ceil(sizeGB * 5)} минут.`
      );
    } else {
      setWarning(null);
    }

    setFile(selectedFile);
    setError(null);
  };

  // Загрузка с отслеживанием прогресса
  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    startTimeRef.current = Date.now();

    const formData = new FormData();
    formData.append('course', courseId);
    formData.append('title', document.getElementById('title').value);
    formData.append('description', document.getElementById('description').value);
    formData.append('video_file', file);

    const token = localStorage.getItem('access_token');
    const xhr = new XMLHttpRequest();
    xhrRef.current = xhr;

    // Отслеживание прогресса
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const elapsed = (Date.now() - startTimeRef.current) / 1000;
        const speed = e.loaded / elapsed;
        const remaining = speed > 0 ? (e.total - e.loaded) / speed : null;

        setProgress({
          percent: (e.loaded / e.total) * 100,
          loaded: e.loaded,
          total: e.total,
          speed,
          remaining
        });
      }
    });

    // Обработка успешной загрузки
    xhr.addEventListener('load', () => {
      if (xhr.status === 201) {
        const lesson = JSON.parse(xhr.responseText);
        setUploading(false);
        setProgress({ percent: 100, loaded: 0, total: 0, speed: 0, remaining: null });
        if (onSuccess) onSuccess(lesson);
      } else {
        const error = JSON.parse(xhr.responseText);
        setError(error.detail || 'Ошибка загрузки');
        setUploading(false);
      }
    });

    // Обработка ошибок
    xhr.addEventListener('error', () => {
      setError('Ошибка сети при загрузке файла');
      setUploading(false);
    });

    xhr.addEventListener('abort', () => {
      setError('Загрузка отменена');
      setUploading(false);
    });

    // Таймаут для больших файлов (30 минут)
    xhr.timeout = 30 * 60 * 1000;
    xhr.addEventListener('timeout', () => {
      setError('Превышено время ожидания. Попробуйте еще раз.');
      setUploading(false);
    });

    xhr.open('POST', '/api/teacher/lessons/create-with-upload/');
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.send(formData);
  };

  // Отмена загрузки
  const handleCancel = () => {
    if (xhrRef.current) {
      xhrRef.current.abort();
      xhrRef.current = null;
    }
    setUploading(false);
    setProgress({ percent: 0, loaded: 0, total: 0, speed: 0, remaining: null });
  };

  // Защита от случайного закрытия страницы
  useEffect(() => {
    if (!uploading) return;

    const handleBeforeUnload = (e) => {
      e.preventDefault();
      e.returnValue = 'Загрузка файла еще не завершена. Вы уверены, что хотите покинуть страницу?';
      return e.returnValue;
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [uploading]);

  // Форматирование размера файла
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  // Форматирование скорости
  const formatSpeed = (bytesPerSec) => {
    return formatBytes(bytesPerSec) + '/s';
  };

  // Форматирование времени
  const formatTime = (seconds) => {
    if (!seconds || seconds === Infinity) return '—';
    if (seconds < 60) return `${Math.round(seconds)} сек`;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${minutes} мин ${secs} сек`;
  };

  return (
    <div className="video-upload">
      <h2>Загрузка видео урока</h2>

      <div className="form-group">
        <label>Название урока</label>
        <input type="text" id="title" required />
      </div>

      <div className="form-group">
        <label>Описание</label>
        <textarea id="description" rows="3" />
      </div>

      <div className="form-group">
        <label>Видео файл</label>
        <input
          type="file"
          accept="video/*"
          onChange={handleFileChange}
          disabled={uploading}
        />
        {file && (
          <div className="file-info">
            <strong>Выбранный файл:</strong> {file.name}
            <br />
            <strong>Размер:</strong> {formatBytes(file.size)}
          </div>
        )}
      </div>

      {warning && (
        <div className="warning">
          {warning}
        </div>
      )}

      {error && (
        <div className="error">
          {error}
        </div>
      )}

      {uploading && (
        <div className="upload-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
          <div className="progress-stats">
            <div>
              <strong>{progress.percent.toFixed(1)}%</strong>
              <span>
                {formatBytes(progress.loaded)} / {formatBytes(progress.total)}
              </span>
            </div>
            <div>
              <span>Скорость: {formatSpeed(progress.speed)}</span>
              {progress.remaining && (
                <span>Осталось: {formatTime(progress.remaining)}</span>
              )}
            </div>
          </div>
          <small>
            ⚠️ Не закрывайте страницу во время загрузки. 
            Для больших файлов это может занять несколько минут.
          </small>
        </div>
      )}

      <div className="actions">
        {!uploading ? (
          <button
            onClick={handleUpload}
            disabled={!file}
            className="btn-primary"
          >
            Загрузить урок
          </button>
        ) : (
          <button
            onClick={handleCancel}
            className="btn-secondary"
          >
            Отменить загрузку
          </button>
        )}
      </div>
    </div>
  );
}

export default OptimizedVideoUpload;
```

---

## 🎨 CSS для прогресс-бара (опционально)

```css
.upload-progress {
  margin: 20px 0;
  padding: 15px;
  background: #f5f5f5;
  border-radius: 8px;
}

.progress-bar {
  width: 100%;
  height: 24px;
  background: #e0e0e0;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #8bc34a);
  transition: width 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  font-weight: bold;
}

.progress-stats {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}

.progress-stats span {
  margin-right: 15px;
}

.warning {
  padding: 12px;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 4px;
  color: #856404;
  margin: 10px 0;
}

.error {
  padding: 12px;
  background: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 4px;
  color: #721c24;
  margin: 10px 0;
}
```

---

## 🎬 Стриминг видео: Оптимальный способ

### ⚡ Важно: Используйте прямой URL для стриминга

Бекенд поддерживает **токен в query-параметре**, что позволяет использовать прямой URL в `<video src>`. 
Браузер сам будет запрашивать нужные части видео (Range requests), **не загружая файл целиком**.

### ✅ Правильный способ (стриминг):

```jsx
function VideoPlayer({ lessonId }) {
  const [videoUrl, setVideoUrl] = useState(null);
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    async function load() {
      // Получаем урок с video_file_url (уже содержит токен в query)
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
      if (lesson.video_file_url) {
        // Используем прямой URL - браузер сам будет стримить видео
        setVideoUrl(lesson.video_file_url);
      } else if (lesson.video_url) {
        setVideoUrl(lesson.video_url);
      }
    }
    load();
  }, [lessonId, token]);

  return (
    <div>
      {videoUrl ? (
        <video 
          controls 
          src={videoUrl}
          style={{ width: '100%', maxWidth: '800px' }}
        >
          Ваш браузер не поддерживает видео.
        </video>
      ) : (
        <div>Загрузка видео...</div>
      )}
    </div>
  );
}
```

### ❌ Неправильный способ (загружает весь файл):

```jsx
// ПЛОХО: Загружает весь файл в память браузера
const videoResponse = await fetch(lesson.video_file_url, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const blob = await videoResponse.blob(); // Загружает ВЕСЬ файл!
videoElement.src = URL.createObjectURL(blob);
```

### Преимущества стриминга:

1. **Не загружает файл целиком** - браузер запрашивает только нужные части
2. **Поддержка перемотки** - работает сразу, не нужно ждать загрузки
3. **Меньше использование памяти** - особенно важно для больших файлов (20GB)
4. **Быстрый старт** - видео начинает воспроизводиться сразу

### Как это работает:

1. API возвращает `video_file_url` с токеном: `/api/lessons/123/video/?token=xxx`
2. Браузер отправляет запрос с Range header: `Range: bytes=0-1048575`
3. Сервер возвращает только запрошенную часть (206 Partial Content)
4. При перемотке браузер запрашивает другую часть
5. Файл никогда не загружается целиком в память

### Пример с дополнительными настройками:

```jsx
function AdvancedVideoPlayer({ lessonId }) {
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/api/lessons/open/', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ lesson_id: lessonId })
        });

        if (!res.ok) {
          throw new Error('Не удалось загрузить урок');
        }

        const { lesson } = await res.json();
        
        if (lesson.video_file_url) {
          setVideoUrl(lesson.video_file_url);
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
    load();
  }, [lessonId, token]);

  if (loading) {
    return <div>Загрузка...</div>;
  }

  if (error) {
    return <div className="error">Ошибка: {error}</div>;
  }

  if (!videoUrl) {
    return <div>Видео не найдено</div>;
  }

  return (
    <div className="video-player">
      <video 
        controls
        preload="metadata"  // Загружает только метаданные, не весь файл
        src={videoUrl}
        style={{ width: '100%', maxWidth: '800px' }}
        onError={(e) => {
          console.error('Ошибка воспроизведения видео:', e);
          setError('Ошибка воспроизведения видео');
        }}
      >
        Ваш браузер не поддерживает видео.
      </video>
    </div>
  );
}
```

### Настройки video элемента для оптимизации:

```html
<video 
  controls
  preload="metadata"     <!-- Загружает только метаданные (размер, длительность) -->
  playsinline            <!-- Для мобильных устройств -->
  controlsList="nodownload"  <!-- Скрыть кнопку скачивания (опционально) -->
  src={videoUrl}
>
```

---

## 📋 Чек-лист оптимизации

### ✅ Обязательно:

- [ ] Используйте `XMLHttpRequest` вместо `fetch` для загрузки файлов
- [ ] Показывайте прогресс загрузки с процентами
- [ ] Валидируйте размер файла на клиенте ПЕРЕД отправкой
- [ ] Устанавливайте разумные таймауты (30+ минут для больших файлов)
- [ ] Предупреждайте пользователя о больших файлах
- [ ] Защищайте от случайного закрытия страницы во время загрузки
- [ ] Используйте прямой URL для видео (стриминг), не загружайте blob
- [ ] Используйте `preload="metadata"` для video элементов

### ✅ Рекомендуется:

- [ ] Показывайте скорость загрузки
- [ ] Показывайте оставшееся время
- [ ] Позволяйте отменять загрузку
- [ ] Сохраняйте прогресс в localStorage (для восстановления после перезагрузки)
- [ ] Показывайте размер файла в удобном формате (GB, MB)

### ❌ Не делайте:

- [ ] Не используйте `fetch` для больших файлов (нет отслеживания прогресса)
- [ ] Не загружайте файл в память целиком перед отправкой
- [ ] Не устанавливайте маленькие таймауты (< 5 минут)
- [ ] Не скрывайте прогресс загрузки
- [ ] Не позволяйте закрывать страницу без предупреждения
- [ ] Не загружайте видео через `fetch().blob()` - используйте прямой URL для стриминга
- [ ] Не используйте `preload="auto"` для больших видео - используйте `preload="metadata"`

---

## 🔄 Обработка статусов урока

После загрузки файла урок может иметь статус `uploading` или `processing`. Отслеживайте статус:

```javascript
async function waitForVideoReady(lessonId, maxAttempts = 60) {
  const token = localStorage.getItem('access_token');
  let attempts = 0;

  while (attempts < maxAttempts) {
    const response = await fetch(`/api/teacher/lessons/${lessonId}/`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    const lesson = await response.json();
    
    if (lesson.youtube_status === 'ready') {
      return lesson;
    } else if (lesson.youtube_status === 'error') {
      throw new Error(lesson.youtube_error || 'Ошибка обработки видео');
    }
    
    // Ждем 5 секунд перед следующей проверкой
    await new Promise(resolve => setTimeout(resolve, 5000));
    attempts++;
  }
  
  throw new Error('Превышено время ожидания обработки видео');
}
```

---

## 🎯 Итоговые рекомендации

1. **Всегда показывайте прогресс** - пользователь должен видеть, что происходит
2. **Валидируйте на клиенте** - не отправляйте файлы, которые заведомо не пройдут валидацию
3. **Используйте правильные инструменты** - `XMLHttpRequest` для загрузки, `fetch` для остального
4. **Обрабатывайте ошибки** - сеть может прерваться, таймауты могут сработать
5. **Защищайте пользователя** - предупреждайте о больших файлах и долгой загрузке

---

## 📚 Дополнительные ресурсы

- [MDN: XMLHttpRequest.upload](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/upload)
- [MDN: ProgressEvent](https://developer.mozilla.org/en-US/docs/Web/API/ProgressEvent)
- [React: File Upload Best Practices](https://react.dev/reference/react-dom/components/input#file-inputs)

---

**Помните:** Бекенд оптимизирован для работы с большими файлами, но фронтенд должен правильно использовать эти возможности и обеспечивать хороший UX для пользователя.
