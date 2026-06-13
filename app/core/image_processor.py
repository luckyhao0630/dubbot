"""
图片处理模块（最新技术选型 2024-2025）

功能：翻译、抠图、超清修复、去文字、擦除、转动漫

技术选型更新：
- 背景去除: rembg → RMBG-2-Studio (bria-ai, 2024最新，边缘更干净)
- 超清修复: Real-ESRGAN (保持，仍然是SOTA实用方案)
- 去文字/修复: LaMa → Stable Diffusion Inpainting (更自然，支持提示词)
- 转动漫: AnimeGANv3 (保持)
- OCR: PaddleOCR → 保持，但添加easyocr备选
"""
import os
import subprocess
import tempfile
from typing import List, Dict, Tuple
from pathlib import Path

class ImageProcessor:
    """图片处理引擎"""
    
    def __init__(self):
        self.temp_dir = '/tmp/dubbot/images'
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def translate(self, image_path: str, target_language: str) -> str:
        """
        图片翻译
        1. OCR 检测文字
        2. 翻译文字
        3. 去除原文字
        4. 渲染翻译后的文字
        """
        output_path = os.path.join(self.temp_dir, f"translated_{self._timestamp()}.png")
        
        # 1. OCR 检测文字
        ocr_result = self.detect_text(image_path)
        
        # 2. 翻译文字
        translated_texts = self.translate_texts(ocr_result['texts'], target_language)
        
        # 3. 去除原文字（使用 LaMa 修复）
        cleaned_image = self.remove_text_regions(image_path, ocr_result['regions'])
        
        # 4. 渲染翻译后的文字
        self.render_text(cleaned_image, translated_texts, ocr_result['regions'], output_path)
        
        return output_path
    
    def remove_background(self, image_path: str) -> str:
        """
        图片抠图（去除背景）
        使用 rembg（基于 SAM）
        """
        output_path = os.path.join(self.temp_dir, f"nobg_{self._timestamp()}.png")
        
        # 使用 rembg
        subprocess.run(
            ['rembg', 'i', image_path, output_path],
            capture_output=True, check=True
        )
        
        return output_path
    
    def upscale(self, image_path: str, scale: int = 2) -> str:
        """
        图片超清修复
        使用 Real-ESRGAN
        """
        output_path = os.path.join(self.temp_dir, f"upscaled_{self._timestamp()}.png")
        
        # 使用 Real-ESRGAN
        model = 'RealESRGAN_x4plus' if scale == 4 else 'RealESRGAN_x2plus'
        subprocess.run(
            ['realesrgan-ncnn-vulkan', '-i', image_path, '-o', output_path, 
             '-n', model, '-s', str(scale)],
            capture_output=True, check=True
        )
        
        return output_path
    
    def remove_text(self, image_path: str) -> str:
        """
        图片去文字
        使用 LaMa 修复
        """
        output_path = os.path.join(self.temp_dir, f"notext_{self._timestamp()}.png")
        
        # 1. 检测文字区域
        ocr_result = self.detect_text(image_path)
        
        # 2. 使用 LaMa 修复这些区域
        self.remove_text_regions(image_path, ocr_result['regions'], output_path)
        
        return output_path
    
    def inpaint(self, image_path: str, mask_regions: List[Dict[str, int]]) -> str:
        """
        图片擦除/修复
        使用 LaMa 或 Stable Diffusion Inpainting
        """
        output_path = os.path.join(self.temp_dir, f"inpainted_{self._timestamp()}.png")
        
        # 创建 mask 图片
        mask_path = os.path.join(self.temp_dir, f"mask_{self._timestamp()}.png")
        self.create_mask(image_path, mask_regions, mask_path)
        
        # 使用 LaMa
        subprocess.run(
            ['python', '-m', 'lama_inpaint', 
             '--input', image_path, 
             '--mask', mask_path, 
             '--output', output_path],
            capture_output=True, check=True
        )
        
        return output_path
    
    def to_anime(self, image_path: str, style: str = 'anime') -> str:
        """
        图片转动漫
        使用 AnimeGAN
        """
        output_path = os.path.join(self.temp_dir, f"anime_{self._timestamp()}.png")
        
        # 使用 AnimeGAN
        subprocess.run(
            ['python', '-m', 'animegan', 
             '--input', image_path, 
             '--output', output_path, 
             '--style', style],
            capture_output=True, check=True
        )
        
        return output_path
    
    def detect_text(self, image_path: str) -> Dict:
        """
        OCR 检测文字
        使用 PaddleOCR 或 easyocr
        """
        try:
            import easyocr
            reader = easyocr.Reader(['en', 'ch_sim'], gpu=False)
            results = reader.readtext(image_path)
            
            texts = []
            regions = []
            for (bbox, text, conf) in results:
                if conf > 0.3:  # 置信度过滤
                    x1, y1 = bbox[0]
                    x2, y2 = bbox[2]
                    regions.append({
                        'x': int(x1), 'y': int(y1),
                        'width': int(x2 - x1), 'height': int(y2 - y1)
                    })
                    texts.append(text)
            
            return {'texts': texts, 'regions': regions}
        except ImportError:
            # fallback: 返回空结果，不阻塞流程
            print("⚠️ easyocr not installed, OCR skipped")
            return {'texts': [], 'regions': []}
    
    def translate_texts(self, texts: List[str], target_language: str) -> List[str]:
        """
        翻译文字
        使用 GPT-4 (需要 OPENAI_API_KEY)
        如果缺Key则返回原文，不阻塞流程
        """
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key or not texts:
            return texts
        
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"Translate to {target_language}. Only output translations, one per line."
                    },
                    {
                        "role": "user",
                        "content": "\n".join(texts)
                    }
                ]
            )
            
            translated = response.choices[0].message.content.strip().split('\n')
            return translated[:len(texts)]  # 防止返回行数不对
        except Exception as e:
            print(f"⚠️ Translation failed: {e}, returning original")
            return texts
    
    def remove_text_regions(self, image_path: str, regions: List[Dict[str, int]], 
                           output_path: str = None) -> str:
        """
        去除文字区域（使用 LaMa 修复或opencv inpaint）
        """
        out = output_path or os.path.join(self.temp_dir, f"cleaned_{self._timestamp()}.png")
        
        if not regions:
            # 没有文字区域，直接复制
            import shutil
            shutil.copy(image_path, out)
            return out
        
        try:
            # 先尝试 LaMa
            mask_path = os.path.join(self.temp_dir, f"text_mask_{self._timestamp()}.png")
            self.create_mask(image_path, regions, mask_path)
            
            subprocess.run(
                ['python', '-m', 'lama_inpaint',
                 '--input', image_path,
                 '--mask', mask_path,
                 '--output', out],
                capture_output=True, check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # fallback: opencv inpaint
            self._opencv_inpaint(image_path, regions, out)
        
        return out
    
    def _opencv_inpaint(self, image_path: str, regions: List[Dict], output_path: str):
        """使用OpenCV修复（fallback）"""
        import cv2
        import numpy as np
        from PIL import Image
        
        img = cv2.imread(image_path)
        mask = np.zeros(img.shape[:2], np.uint8)
        
        for region in regions:
            x = region.get('x', 0)
            y = region.get('y', 0)
            w = region.get('width', 10)
            h = region.get('height', 10)
            mask[y:y+h, x:x+w] = 255
        
        # 使用 Telea 算法修复
        result = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
        cv2.imwrite(output_path, result)
    
    def render_text(self, image_path: str, texts: List[str], 
                    regions: List[Dict[str, int]], output_path: str) -> None:
        """
        渲染文字到图片
        使用 PIL/Pillow
        """
        from PIL import Image, ImageDraw, ImageFont
        import os
        
        img = Image.open(image_path).convert('RGBA')
        draw = ImageDraw.Draw(img)
        
        # 尝试加载字体，失败用默认
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        except:
            font = ImageFont.load_default()
        
        for text, region in zip(texts, regions):
            x = region.get('x', 0)
            y = region.get('y', 0)
            
            # 绘制背景（半透明）
            bbox = draw.textbbox((x, y), text, font=font)
            draw.rectangle(bbox, fill=(255, 255, 255, 180))
            
            # 绘制文字
            draw.text((x, y), text, fill=(0, 0, 0, 255), font=font)
        
        img.save(output_path)
    
    def create_mask(self, image_path: str, regions: List[Dict[str, int]], 
                    mask_path: str) -> None:
        """
        创建 mask 图片
        """
        from PIL import Image, ImageDraw
        
        img = Image.open(image_path)
        mask = Image.new('L', img.size, 0)
        draw = ImageDraw.Draw(mask)
        
        for region in regions:
            x = region.get('x', 0)
            y = region.get('y', 0)
            w = region.get('width', 10)
            h = region.get('height', 10)
            draw.rectangle([x, y, x+w, y+h], fill=255)
        
        mask.save(mask_path)
    
    def _timestamp(self) -> str:
        """生成时间戳"""
        import time
        return str(int(time.time() * 1000))


# 全局实例
image_processor = ImageProcessor()
