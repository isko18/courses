"""
Сервис для обработки и сжатия видео файлов.
Использует ffmpeg для оптимизации видео.
"""
import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


def check_ffmpeg() -> bool:
    """Проверяет наличие ffmpeg в системе."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_video_info(video_path: str) -> Optional[dict]:
    """
    Получает информацию о видео файле (длительность, разрешение, битрейт).
    """
    if not check_ffmpeg():
        logger.warning("ffmpeg не найден, невозможно получить информацию о видео")
        return None

    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        import json
        data = json.loads(result.stdout)
        
        # Находим видео поток
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break
        
        if not video_stream:
            return None
        
        format_info = data.get("format", {})
        duration = float(format_info.get("duration", 0))
        
        return {
            "duration": duration,
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "bitrate": int(format_info.get("bit_rate", 0)),
            "codec": video_stream.get("codec_name", "unknown"),
            "size": int(format_info.get("size", 0)),
        }
    except Exception as e:
        logger.error(f"Ошибка при получении информации о видео: {e}")
        return None


def compress_video(
    input_path: str,
    output_path: str,
    target_bitrate: str = "2M",
    max_width: int = 1920,
    max_height: int = 1080,
    crf: int = 23,
) -> Tuple[bool, Optional[str]]:
    """
    Сжимает видео файл используя ffmpeg.
    
    Args:
        input_path: Путь к исходному видео
        output_path: Путь для сохранения сжатого видео
        target_bitrate: Целевой битрейт (например, "2M", "5M")
        max_width: Максимальная ширина
        max_height: Максимальная высота
        crf: Constant Rate Factor для x264/x265 (18-28, меньше = лучше качество)
    
    Returns:
        Tuple[bool, Optional[str]]: (успех, сообщение об ошибке)
    """
    if not check_ffmpeg():
        return False, "ffmpeg не установлен в системе"
    
    # Создаём директорию для выходного файла
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        # Получаем информацию о видео
        info = get_video_info(input_path)
        if not info:
            return False, "Не удалось получить информацию о видео"
        
        # Определяем разрешение для вывода
        width = info["width"]
        height = info["height"]
        
        # Масштабируем если нужно
        scale_filter = ""
        if width > max_width or height > max_height:
            # Сохраняем пропорции
            if width / height > max_width / max_height:
                new_width = max_width
                new_height = -2  # Автоматически сохраняет пропорции
            else:
                new_width = -2
                new_height = max_height
            scale_filter = f"scale={new_width}:{new_height},"
        
        # Команда ffmpeg для сжатия
        # Используем H.264 кодек с оптимизацией
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-c:v", "libx264",  # Видео кодек
            "-preset", "medium",  # Скорость кодирования (medium баланс между скоростью и размером)
            "-crf", str(crf),  # Качество (23 - хороший баланс)
            "-b:v", target_bitrate,  # Целевой битрейт
            "-maxrate", target_bitrate,  # Максимальный битрейт
            "-bufsize", f"{int(target_bitrate[:-1]) * 2}M",  # Буфер
            "-vf", f"{scale_filter}format=yuv420p" if scale_filter else "format=yuv420p",  # Фильтры
            "-c:a", "aac",  # Аудио кодек
            "-b:a", "128k",  # Аудио битрейт
            "-movflags", "+faststart",  # Оптимизация для веб-плееров
            "-y",  # Перезаписать выходной файл
            output_path
        ]
        
        logger.info(f"Начало сжатия видео: {input_path} -> {output_path}")
        
        # Запускаем ffmpeg
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr or stdout or "Неизвестная ошибка"
            logger.error(f"Ошибка сжатия видео: {error_msg}")
            return False, f"Ошибка сжатия: {error_msg[:200]}"
        
        # Проверяем что выходной файл создан
        if not os.path.exists(output_path):
            return False, "Выходной файл не был создан"
        
        # Получаем размеры файлов
        input_size = os.path.getsize(input_path)
        output_size = os.path.getsize(output_path)
        compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
        
        logger.info(
            f"Сжатие завершено: {input_size / (1024**3):.2f}GB -> "
            f"{output_size / (1024**3):.2f}GB ({compression_ratio:.1f}% сжатие)"
        )
        
        return True, None
        
    except subprocess.TimeoutExpired:
        return False, "Превышено время ожидания обработки"
    except Exception as e:
        logger.error(f"Исключение при сжатии видео: {e}")
        return False, str(e)


def optimize_video_for_upload(
    input_path: str,
    output_path: str,
    max_file_size_gb: float = 20.0,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Оптимизирует видео для загрузки, пытаясь уложиться в максимальный размер.
    
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (успех, путь к файлу, сообщение об ошибке)
    """
    input_size_gb = os.path.getsize(input_path) / (1024 ** 3)
    
    # Если файл уже меньше лимита, просто копируем
    # КРИТИЧНО: Используем потоковое копирование вместо shutil.copy2 для больших файлов
    if input_size_gb <= max_file_size_gb:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            # Потоковое копирование с буфером 8MB (не загружаем весь файл в RAM)
            CHUNK_SIZE = 8 * 1024 * 1024  # 8MB
            with open(input_path, "rb") as src:
                with open(output_path, "wb") as dst:
                    while True:
                        chunk = src.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        dst.write(chunk)
            return True, output_path, None
        except Exception as e:
            return False, None, f"Ошибка копирования: {e}"
    
    # Пытаемся сжать
    # Начинаем с более агрессивного сжатия для больших файлов
    if input_size_gb > 15:
        target_bitrate = "3M"
        crf = 25
    elif input_size_gb > 10:
        target_bitrate = "4M"
        crf = 24
    elif input_size_gb > 5:
        target_bitrate = "5M"
        crf = 23
    else:
        target_bitrate = "6M"
        crf = 22
    
    success, error = compress_video(
        input_path,
        output_path,
        target_bitrate=target_bitrate,
        crf=crf,
    )
    
    if not success:
        return False, None, error
    
    # Проверяем размер после сжатия
    output_size_gb = os.path.getsize(output_path) / (1024 ** 3)
    
    if output_size_gb > max_file_size_gb:
        # Если всё ещё слишком большой, пробуем более агрессивное сжатие
        logger.warning(f"Файл всё ещё большой ({output_size_gb:.2f}GB), применяем более агрессивное сжатие")
        success, error = compress_video(
            input_path,
            output_path,
            target_bitrate="2M",
            crf=28,
        )
        if not success:
            return False, None, error
        
        output_size_gb = os.path.getsize(output_path) / (1024 ** 3)
        if output_size_gb > max_file_size_gb:
            return False, None, f"Не удалось сжать видео до {max_file_size_gb}GB (итоговый размер: {output_size_gb:.2f}GB)"
    
    return True, output_path, None
