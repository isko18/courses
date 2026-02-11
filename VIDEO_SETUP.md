# Настройка загрузки и обработки видео

## Требования

Для работы системы загрузки и сжатия видео необходимо установить **ffmpeg**.

### Установка ffmpeg

#### Windows
1. Скачайте ffmpeg с официального сайта: https://ffmpeg.org/download.html
2. Или используйте chocolatey: `choco install ffmpeg`
3. Или используйте winget: `winget install ffmpeg`

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

### Проверка установки

После установки проверьте, что ffmpeg доступен:
```bash
ffmpeg -version
```

## Настройки

В `core/settings.py` уже настроены следующие параметры:

- `VIDEO_MAX_SIZE_GB = 20` - максимальный размер загружаемого видео (20GB)
- `VIDEO_COMPRESSION_ENABLED = True` - включить автоматическое сжатие видео
- `DATA_UPLOAD_MAX_MEMORY_SIZE = 21474836480` - максимальный размер загружаемых данных (20GB)
- `FILE_UPLOAD_MAX_MEMORY_SIZE = 21474836480` - максимальный размер загружаемых файлов (20GB)

## Использование

### Загрузка видео

Используйте endpoint: `POST /api/teacher/lessons/create-with-upload/`

Параметры:
- `course` - ID курса
- `title` - название урока
- `description` - описание (опционально)
- `video_file` - файл видео (до 20GB)
- `video_url` - или URL видео (альтернатива video_file)
- `homework_title`, `homework_description`, `homework_link`, `homework_file` - поля для ДЗ (опционально)

### Просмотр видео

Видео доступно через endpoint: `GET /api/lessons/{lesson_id}/video/`

Этот endpoint поддерживает:
- Потоковую передачу (streaming)
- Range requests (для перемотки видео)
- Авторизацию (только для пользователей с доступом к уроку)

## Обработка видео

Система автоматически:
1. Проверяет размер файла (максимум 20GB)
2. Оптимизирует видео (сжатие при необходимости)
3. Сохраняет в `media/videos/YYYY/MM/DD/`
4. Извлекает длительность видео
5. Поддерживает различные форматы (MP4, AVI, MOV и др.)

## Производительность

- Сжатие видео может занять время в зависимости от размера и длительности
- Для больших файлов (>10GB) используется более агрессивное сжатие
- Рекомендуется использовать SSD для хранения видео файлов
