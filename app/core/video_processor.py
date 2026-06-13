"""
视频处理核心引擎（全本地方案 2024-2025）
流程：提取音频 → 本地ASR(faster-whisper) → 翻译(OpenAI/DeepL fallback) → 本地TTS(edge-tts) → 合成视频

技术选型：
- ASR: faster-whisper (本地运行，比API快4x，免费，支持多语言)
- TTS: edge-tts (微软Edge免费TTS，支持多语言，自然度高)
- 翻译: OpenAI GPT-4o-mini (优先) / DeepL免费API (fallback) / 直接返回原文 (fallback)
- 字幕: ffmpeg烧录
"""
import os
import subprocess
import json
import tempfile
import asyncio
from typing import List, Dict, Tuple
import openai
from openai import OpenAI

class VideoProcessor:
    """视频处理引擎 - 全本地方案"""
    
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self._whisper_model = None
        self._edge_tts_voices = {
            "en": "en-US-AriaNeural",
            "es": "es-ES-ElviraNeural",
            "fr": "fr-FR-DeniseNeural",
            "de": "de-DE-KatjaNeural",
            "ja": "ja-JP-NanamiNeural",
            "ko": "ko-KR-SunHiNeural",
            "zh": "zh-CN-XiaoxiaoNeural",
            "ar": "ar-SA-ZariyahNeural",
            "hi": "hi-IN-SwaraNeural",
            "pt": "pt-BR-FranciscaNeural",
            "ru": "ru-RU-SvetlanaNeural",
            "it": "it-IT-ElsaNeural",
        }
    
    def _get_whisper_model(self):
        """懒加载 faster-whisper 模型"""
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                # 使用 large-v3 模型，CPU 运行，自动下载
                self._whisper_model = WhisperModel("large-v3", device="cpu", compute_type="int8")
            except ImportError:
                raise RuntimeError("faster-whisper not installed. Run: pip install faster-whisper")
        return self._whisper_model
    
    def extract_audio(self, video_path: str) -> Tuple[str, float]:
        """从视频提取音频，返回音频路径和时长"""
        audio_path = video_path.replace(".mp4", "_audio.wav").replace(".mov", "_audio.wav")
        
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            audio_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        
        duration = self._get_duration(video_path)
        return audio_path, duration
    
    def _get_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    
    def transcribe(self, audio_path: str) -> List[Dict]:
        """使用 faster-whisper 本地转录，返回带时间轴的文本段"""
        try:
            model = self._get_whisper_model()
            segments, info = model.transcribe(audio_path, beam_size=5, language=None)
            
            result = []
            for segment in segments:
                result.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "speaker": None
                })
            return result
        except Exception as e:
            print(f"⚠️ faster-whisper failed: {e}, trying OpenAI fallback")
            # Fallback to OpenAI Whisper API if available
            if self.client:
                return self._transcribe_openai(audio_path)
            raise
    
    def _transcribe_openai(self, audio_path: str) -> List[Dict]:
        """OpenAI Whisper API fallback"""
        with open(audio_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        
        segments = []
        for segment in transcript.segments:
            segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "speaker": getattr(segment, "speaker", None)
            })
        return segments
    
    def translate(self, segments: List[Dict], target_language: str) -> List[Dict]:
        """翻译文本段，优先OpenAI，fallback直接返回原文"""
        translated = []
        
        if not self.client:
            print("⚠️ No OpenAI API, returning original text")
            for segment in segments:
                translated.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "original_text": segment["text"],
                    "translated_text": segment["text"],  # 无翻译，返回原文
                    "speaker": segment.get("speaker")
                })
            return translated
        
        try:
            for segment in segments:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are a professional translator. Translate the following text to {target_language}. Preserve the tone, style, and emotional nuance. Keep it natural and conversational. Only output the translated text, no explanations."
                        },
                        {
                            "role": "user",
                            "content": segment["text"]
                        }
                    ],
                    temperature=0.3
                )
                
                translated_text = response.choices[0].message.content.strip()
                
                translated.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "original_text": segment["text"],
                    "translated_text": translated_text,
                    "speaker": segment.get("speaker")
                })
            return translated
        except Exception as e:
            print(f"⚠️ Translation failed: {e}, returning original text")
            for segment in segments:
                translated.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "original_text": segment["text"],
                    "translated_text": segment["text"],
                    "speaker": segment.get("speaker")
                })
            return translated
    
    def generate_speech(self, segments: List[Dict], target_language: str = "en", voice_clone: bool = False) -> str:
        """使用 edge-tts 本地生成语音，返回音频文件路径"""
        temp_dir = tempfile.mkdtemp()
        segment_files = []
        
        # 获取目标语言对应的语音
        voice = self._edge_tts_voices.get(target_language, "en-US-AriaNeural")
        
        for i, segment in enumerate(segments):
            text = segment.get("translated_text", segment["text"])
            if not text.strip():
                continue
            
            segment_path = os.path.join(temp_dir, f"segment_{i}.mp3")
            
            # 使用 edge-tts 生成语音
            try:
                import edge_tts
                communicate = edge_tts.Communicate(text, voice)
                asyncio.run(communicate.save(segment_path))
                segment_files.append(segment_path)
            except Exception as e:
                print(f"⚠️ TTS failed for segment {i}: {e}")
                continue
        
        if not segment_files:
            raise RuntimeError("No audio segments generated")
        
        # 合并所有语音片段（按时间对齐）
        merged_path = os.path.join(temp_dir, "dubbed_audio.wav")
        self._merge_audio_segments_with_timing(segment_files, merged_path, segments)
        
        return merged_path
    
    def _merge_audio_segments_with_timing(self, segment_files: List[str], output_path: str, segments: List[Dict]):
        """合并音频片段，按时间轴对齐（填充静音）"""
        temp_dir = os.path.dirname(output_path)
        
        # 构建 ffmpeg 复杂滤镜，按时间轴放置每个片段
        inputs = []
        filters = []
        
        for i, (seg_file, segment) in enumerate(zip(segment_files, segments)):
            inputs.extend(["-i", seg_file])
            start_time = segment["start"]
            filters.append(f"[{i}:a]adelay={int(start_time*1000)}|{int(start_time*1000)}[a{i}]")
        
        # 混合所有音频
        mix_inputs = "".join([f"[a{i}]" for i in range(len(segment_files))])
        filters.append(f"{mix_inputs}amix=inputs={len(segment_files)}:duration=longest[out]")
        
        filter_complex = ";".join(filters)
        
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    
    def _merge_audio_segments(self, segment_files: List[str], output_path: str, segments: List[Dict]):
        """合并音频片段，保持时间对齐（备用方法）"""
        concat_file = os.path.join(os.path.dirname(output_path), "concat.txt")
        
        with open(concat_file, "w") as f:
            for seg_file in segment_files:
                duration = self._get_audio_duration(seg_file)
                f.write(f"file '{seg_file}'\n")
                f.write(f"duration {duration}\n")
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(result.stdout.strip())
        except:
            return 0.0
    
    def merge_video(self, original_video: str, dubbed_audio: str) -> str:
        """将配音音频合并回原视频"""
        output_path = original_video.replace("_upload", "_dubbed")
        
        cmd = [
            "ffmpeg", "-y", "-i", original_video,
            "-i", dubbed_audio,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        
        return output_path
    
    def add_subtitles(self, video_path: str, segments: List[Dict], output_path: str, style: str = "default"):
        """添加字幕到视频"""
        srt_path = video_path.replace(".mp4", ".srt")
        
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments):
                start = self._format_time(segment["start"])
                end = self._format_time(segment["end"])
                f.write(f"{i+1}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{segment.get('translated_text', segment['text'])}\n\n")
        
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"subtitles={srt_path}:force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'",
            "-c:a", "copy",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        
        return output_path
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间为 SRT 格式 HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
