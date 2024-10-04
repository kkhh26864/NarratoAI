import cv2
import numpy as np
from typing import List, Dict
import os
from loguru import logger
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips
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

def clip_videos(task_id: str, timestamp_terms: List[str], origin_video: str, max_clip_duration: int = 3, total_duration: float = None) -> Dict[str, str]:
    print("Running updated clip_videos function")
    video_paths = {}
    save_dir = utils.task_dir(task_id)

    origin_video = os.path.abspath(origin_video)
    logger.info(f"Attempting to process video: {origin_video}")
    if not os.path.exists(origin_video):
        logger.error(f"Video file does not exist: {origin_video}")
        return {}

    try:
        with VideoFileClip(origin_video) as video:
            original_width, original_height = video.w, video.h
            fps = video.fps
            duration = video.duration
            audio = video.audio

            is_portrait = original_height > original_width
            logger.info(f"Original video dimensions: {original_width}x{original_height}, Is portrait: {is_portrait}, Duration: {duration}")

            current_total_duration = 0
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

                    clip_duration = min(end_time - start_time, max_clip_duration)
                    
                    # If we have a total_duration target, adjust the clip duration
                    if total_duration and current_total_duration + clip_duration > total_duration:
                        clip_duration = total_duration - current_total_duration

                    end_time = start_time + clip_duration

                    subclip = video.subclip(start_time, end_time)

                    clip_filename = f"clip_{timestamp.replace(':', '_').replace('-', '_')}.mp4"
                    clip_path = os.path.join(save_dir, clip_filename)
                    
                    logger.info(f"Clipping video: {timestamp}, duration: {subclip.duration}")

                    subclip.write_videofile(clip_path, codec="libx264", audio_codec="aac")
                    video_paths[timestamp] = clip_path

                    current_total_duration += subclip.duration
                    logger.info(f"Successfully clipped video for timestamp {timestamp}: {clip_path}")
                    
                    if total_duration and current_total_duration >= total_duration:
                        logger.info(f"Reached total duration target of {total_duration}. Stopping clip generation.")
                        break
                
                except Exception as e:
                    logger.error(f"Error clipping video for timestamp {timestamp}: {str(e)}")
                    continue

            # If we still need more video content, loop back to the beginning
            while total_duration and current_total_duration < total_duration:
                for timestamp, path in list(video_paths.items()):
                    with VideoFileClip(path) as clip:
                        remaining_duration = total_duration - current_total_duration
                        if remaining_duration <= 0:
                            break
                        if clip.duration > remaining_duration:
                            subclip = clip.subclip(0, remaining_duration)
                        else:
                            subclip = clip
                        
                        new_clip_filename = f"extra_clip_{timestamp.replace(':', '_').replace('-', '_')}.mp4"
                        new_clip_path = os.path.join(save_dir, new_clip_filename)
                        subclip.write_videofile(new_clip_path, codec="libx264", audio_codec="aac")
                        video_paths[f"extra_{timestamp}"] = new_clip_path
                        current_total_duration += subclip.duration
                        
                        if current_total_duration >= total_duration:
                            break

    except Exception as e:
        logger.error(f"Error processing the original video file: {str(e)}")
        return {}

    logger.info(f"Total clipped video duration: {current_total_duration}")
    return video_paths

def combine_clip_videos(task_id: str, clip_videos: dict, output_path: str):
    """
    Combines multiple video clips into a single video.

    :param task_id: The ID of the current task
    :param clip_videos: Dictionary of timestamp to video file paths
    :param output_path: Path where the combined video will be saved
    :return: Path to the combined video file
    """
    try:
        video_clips = [VideoFileClip(path) for path in clip_videos.values()]
        logger.info(f"Combining {len(video_clips)} video clips")
        final_clip = concatenate_videoclips(video_clips)
        final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
        
        # Close the clips to free up system resources
        for clip in video_clips:
            clip.close()
        final_clip.close()
        
        logger.info(f"Combined video duration: {final_clip.duration}")
        return output_path
    except Exception as e:
        logger.error(f"Error in combine_clip_videos: {str(e)}")
        return None
