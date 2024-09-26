import cv2
import numpy as np
from typing import List, Dict
import os
from loguru import logger
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
from app.utils import utils

def parse_timestamp(timestamp: str) -> tuple:
    """
    解析时间戳字符串，返回开始和结束时间
    
    :param timestamp: 格式为 "00:00-00:00" 的时间戳字符串
    :return: 包含开始和结束时间的元组 (start_time, end_time)
    """
    start, end = timestamp.split('-')
    
    def time_to_seconds(time_str):
        parts = time_str.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(parts[0])
    
    return time_to_seconds(start), time_to_seconds(end)

def clip_videos(task_id: str, timestamp_terms: List[str], origin_video: str) -> Dict[str, str]:
    print("Running updated clip_videos function")
    video_paths = {}
    save_dir = utils.task_dir(task_id)

    origin_video = os.path.abspath(origin_video)
    logger.info(f"Attempting to process video: {origin_video}")
    if not os.path.exists(origin_video):
        logger.error(f"Video file does not exist: {origin_video}")
        return {}

    try:
        cap = cv2.VideoCapture(origin_video)
        original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        logger.info(f"Original video dimensions: {original_width}x{original_height}, Duration: {duration}")

        # 读取音频
        with VideoFileClip(origin_video) as video:
            audio = video.audio if video.audio is not None else None
            if audio is None:
                logger.warning("No audio track found in the video.")

        for timestamp in timestamp_terms:
            try:
                start_time, end_time = parse_timestamp(timestamp)
                
                if end_time > duration:
                    logger.warning(f"End time {end_time} is greater than video duration {duration}. Adjusting to video duration.")
                    end_time = duration

                if start_time >= duration:
                    logger.error(f"Invalid start time {start_time} for video with duration {duration}")
                    continue

                if start_time >= end_time:
                    logger.error(f"Invalid time range: start time {start_time} is not less than end time {end_time}")
                    continue

                start_frame = int(start_time * fps)
                end_frame = int(end_time * fps)

                clip_filename = f"clip_{timestamp.replace(':', '_').replace('-', '_')}.mp4"
                clip_path = os.path.join(save_dir, clip_filename)
                
                logger.info(f"Clipping video: {timestamp}, frames: {start_frame}-{end_frame}")

                # 使用 OpenCV 裁剪视频
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(clip_path, fourcc, fps, (original_width, original_height))

                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                for _ in range(start_frame, end_frame):
                    ret, frame = cap.read()
                    if not ret:
                        break
                    out.write(frame)

                out.release()

                # 如果有音频，使用 moviepy 添加音频
                if audio is not None:
                    try:
                        video_clip = VideoFileClip(clip_path)
                        audio_clip = audio.subclip(start_time, end_time)
                        final_clip = video_clip.set_audio(audio_clip)
                        
                        # 确保输出视频保持原始尺寸
                        final_clip = final_clip.resize(width=original_width, height=original_height)
                        
                        # 使用 ffmpeg-python 来避免尺寸改变
                        final_clip.write_videofile(clip_path, codec="libx264", audio_codec="aac",
                                                   ffmpeg_params=["-vf", f"scale={original_width}:{original_height}"])
                        video_clip.close()
                        final_clip.close()
                    except Exception as audio_error:
                        logger.error(f"Error adding audio to clip: {str(audio_error)}")
                        logger.info("Continuing without audio.")

                video_paths[timestamp] = clip_path
                logger.info(f"Successfully clipped video for timestamp {timestamp}: {clip_path}")
            
            except Exception as e:
                logger.error(f"Error clipping video for timestamp {timestamp}: {str(e)}")
                continue

        cap.release()

    except Exception as e:
        logger.error(f"Error processing the original video file: {str(e)}")
        return {}

    return video_paths
