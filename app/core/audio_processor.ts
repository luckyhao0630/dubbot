/**
 * 音频处理模块
 * 功能：人声分离、TTS、音频分割/拼接/混音
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs';
import * as path from 'path';
import OpenAI from 'openai';

const execAsync = promisify(exec);

export class AudioProcessor {
  private tempDir: string;
  private openai: OpenAI;

  constructor() {
    this.tempDir = '/tmp/dubbot/audio';
    if (!fs.existsSync(this.tempDir)) {
      fs.mkdirSync(this.tempDir, { recursive: true });
    }
    this.openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }

  /**
   * 人声分离
   * 使用 Demucs V4（SOTA）
   */
  async separateVocals(audioPath: string): Promise<{ vocals: string; instrumental: string }> {
    const outputDir = path.join(this.tempDir, `separated_${Date.now()}`);
    fs.mkdirSync(outputDir, { recursive: true });

    // 使用 Demucs
    await execAsync(
      `demucs --two-stems=vocals "${audioPath}" -o "${outputDir}"`
    );

    const baseName = path.basename(audioPath, path.extname(audioPath));
    const vocals = path.join(outputDir, 'htdemucs', baseName, 'vocals.wav');
    const instrumental = path.join(outputDir, 'htdemucs', baseName, 'no_vocals.wav');

    return { vocals, instrumental };
  }

  /**
   * 多乐器分离
   * 使用 Demucs V4 4-stems 模型
   */
  async separateStems(audioPath: string): Promise<{
    vocals: string;
    drums: string;
    bass: string;
    other: string;
  }> {
    const outputDir = path.join(this.tempDir, `stems_${Date.now()}`);
    fs.mkdirSync(outputDir, { recursive: true });

    // 使用 Demucs 4-stems
    await execAsync(
      `demucs "${audioPath}" -o "${outputDir}"`
    );

    const baseName = path.basename(audioPath, path.extname(audioPath));
    const stemsDir = path.join(outputDir, 'htdemucs', baseName);

    return {
      vocals: path.join(stemsDir, 'vocals.wav'),
      drums: path.join(stemsDir, 'drums.wav'),
      bass: path.join(stemsDir, 'bass.wav'),
      other: path.join(stemsDir, 'other.wav'),
    };
  }

  /**
   * 文字转语音（TTS）
   * 使用 ElevenLabs（高质量）
   * 备用：OpenAI TTS
   */
  async textToSpeech(text: string, options: {
    voice?: string;
    model?: 'elevenlabs' | 'openai';
    language?: string;
    style?: string;
  } = {}): Promise<string> {
    const outputPath = path.join(this.tempDir, `tts_${Date.now()}.mp3`);

    if (options.model === 'openai' || !process.env.ELEVENLABS_API_KEY) {
      // 使用 OpenAI TTS（备用）
      const response = await this.openai.audio.speech.create({
        model: 'tts-1',
        voice: (options.voice as any) || 'alloy',
        input: text,
      });
      
      const buffer = Buffer.from(await response.arrayBuffer());
      fs.writeFileSync(outputPath, buffer);
    } else {
      // 使用 ElevenLabs（高质量）
      const response = await fetch('https://api.elevenlabs.io/v1/text-to-speech/' + (options.voice || 'pNInz6obpgDQGcFmaJgB'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'xi-api-key': process.env.ELEVENLABS_API_KEY!,
        },
        body: JSON.stringify({
          text,
          model_id: 'eleven_multilingual_v2',
          voice_settings: {
            stability: 0.5,
            similarity_boost: 0.75,
            style: 0.5,
          },
        }),
      });

      const buffer = Buffer.from(await response.arrayBuffer());
      fs.writeFileSync(outputPath, buffer);
    }

    return outputPath;
  }

  /**
   * 声音克隆（高级功能）
   * 使用 ElevenLabs Voice Cloning
   */
  async cloneVoice(audioSamples: string[], voiceName: string): Promise<string> {
    // 使用 ElevenLabs 创建声音克隆
    const formData = new FormData();
    
    audioSamples.forEach((sample, index) => {
      const blob = new Blob([fs.readFileSync(sample)]);
      formData.append('files', blob, `sample_${index}.wav`);
    });

    const response = await fetch('https://api.elevenlabs.io/v1/voices/add', {
      method: 'POST',
      headers: {
        'xi-api-key': process.env.ELEVENLABS_API_KEY!,
      },
      body: formData,
    });

    const result = await response.json();
    return result.voice_id;
  }

  /**
   * 音频分割
   * 基于静音检测
   */
  async splitBySilence(audioPath: string, silenceThreshold: number = -30, minDuration: number = 1): Promise<string[]> {
    const outputDir = path.join(this.tempDir, `split_${Date.now()}`);
    fs.mkdirSync(outputDir, { recursive: true });

    // 使用 ffmpeg silence detect
    await execAsync(
      `ffmpeg -i "${audioPath}" -af silencedetect=noise=${silenceThreshold}dB:d=${minDuration} -f null - 2> "${outputDir}/silence.log"`
    );

    // 解析 silence 日志并分割
    // 实现...

    return []; // 返回分割后的文件列表
  }

  /**
   * 音频拼接
   * 合并多个音频文件
   */
  async merge(audioFiles: string[], outputPath: string, options: {
    crossfade?: number;
    normalize?: boolean;
  } = {}): Promise<string> {
    // 创建 concat 文件
    const concatFile = path.join(this.tempDir, `concat_${Date.now()}.txt`);
    const content = audioFiles.map(f => `file '${f}'`).join('\n');
    fs.writeFileSync(concatFile, content);

    if (options.crossfade && options.crossfade > 0) {
      // 使用交叉淡化
      await execAsync(
        `ffmpeg -f concat -safe 0 -i "${concatFile}" -af acrossfade=d=${options.crossfade} "${outputPath}"`
      );
    } else {
      // 简单拼接
      await execAsync(
        `ffmpeg -f concat -safe 0 -i "${concatFile}" -c copy "${outputPath}"`
      );
    }

    if (options.normalize) {
      // 音量归一化
      const normalizedPath = outputPath.replace('.wav', '_normalized.wav');
      await execAsync(
        `ffmpeg -i "${outputPath}" -af loudnorm=I=-16:TP=-1.5:LRA=11 "${normalizedPath}"`
      );
      return normalizedPath;
    }

    return outputPath;
  }

  /**
   * 音频混音
   * 混合多个音频轨道
   */
  async mix(audioFiles: string[], outputPath: string, options: {
    volumes?: number[];
    effects?: Array<{ type: string; params: any }>;
  } = {}): Promise<string> {
    // 构建 ffmpeg 混音命令
    let inputs = '';
    let mixFilter = '';

    audioFiles.forEach((file, index) => {
      inputs += `-i "${file}" `;
      const volume = options.volumes?.[index] ?? 1;
      mixFilter += `[${index}:a]volume=${volume}[a${index}];`;
    });

    const amixInputs = audioFiles.map((_, i) => `[a${i}]`).join('');
    mixFilter += `${amixInputs}amix=inputs=${audioFiles.length}:duration=longest[out]`;

    await execAsync(
      `ffmpeg ${inputs}-filter_complex "${mixFilter}" -map "[out]" "${outputPath}"`
    );

    return outputPath;
  }

  /**
   * 音频提取（从视频）
   */
  async extractFromVideo(videoPath: string, outputPath?: string): Promise<string> {
    const out = outputPath || path.join(this.tempDir, `extracted_${Date.now()}.wav`);
    
    await execAsync(
      `ffmpeg -i "${videoPath}" -vn -acodec pcm_s16le -ar 44100 -ac 2 "${out}"`
    );

    return out;
  }

  /**
   * 音频格式转换
   */
  async convert(audioPath: string, format: 'mp3' | 'wav' | 'flac' | 'ogg' | 'aac', outputPath?: string): Promise<string> {
    const out = outputPath || path.join(this.tempDir, `converted_${Date.now()}.${format}`);
    
    const codecs: Record<string, string> = {
      mp3: 'libmp3lame -q:a 2',
      wav: 'pcm_s16le',
      flac: 'flac',
      ogg: 'libvorbis -q:a 4',
      aac: 'aac -b:a 192k',
    };

    await execAsync(
      `ffmpeg -i "${audioPath}" -c:a ${codecs[format]} "${out}"`
    );

    return out;
  }
}
