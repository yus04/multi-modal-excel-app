import json
from typing import List, Dict, Any, Optional
from openai import AzureOpenAI
import logging

logger = logging.getLogger(__name__)


class MultiModalLLMService:
    """Service for structuring documents using multimodal LLM"""
    
    def __init__(self, endpoint: str, api_key: str, deployment_name: str, api_version: str):
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        self.deployment_name = deployment_name
    
    def describe_image(self, image_base64: str) -> str:
        """Generate a text description for an image using multimodal LLM"""
        try:
            system_prompt = """あなたは製造業の作業標準書に含まれる画像を説明する専門家です。
画像の内容を日本語で詳細に説明してください。

以下の点に注意してください：
- 画像に含まれる部品、工具、機械などを具体的に記述
- 作業手順や操作方法が示されている場合は、その詳細を説明
- 図表やグラフの場合は、そのデータや意味を説明
- 安全に関する警告やマークがある場合は、それを明記
- 推測ではなく、画像に明確に表示されている内容のみを記述

簡潔かつ明確に説明してください。"""
            
            user_content = [
                {
                    "type": "text",
                    "text": "この画像の内容を詳細に説明してください。"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    }
                }
            ]
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            description = response.choices[0].message.content
            logger.info(f"Generated image description: {description[:100]}...")
            return description
            
        except Exception as e:
            logger.error(f"Error generating image description: {str(e)}")
            return "[画像の説明を生成できませんでした]"
    
    def merge_text_and_image_descriptions(
        self,
        text_content: List[Dict[str, Any]],
        images_with_descriptions: List[Dict[str, Any]]
    ) -> str:
        """Merge text content and image descriptions at appropriate positions"""
        
        # Group images by sheet and row
        images_by_position = {}
        for img in images_with_descriptions:
            sheet_idx = img.get('sheet_index', 0)
            position = img.get('position')
            if position and 'row' in position:
                row = position['row']
                key = (sheet_idx, row)
                if key not in images_by_position:
                    images_by_position[key] = []
                images_by_position[key].append(img)
        
        # Build combined content
        combined_parts = []
        
        for sheet in text_content:
            sheet_name = sheet.get('sheet_name', 'Unknown')
            sheet_idx = sheet.get('sheet_index', 0)
            rows = sheet.get('rows', [])
            
            combined_parts.append(f"\n【{sheet_name}】\n")
            
            # Track the last processed row
            last_row = 0
            
            for row_data in rows:
                row_num = row_data.get('row_number', 0)
                row_values = row_data.get('values', [])
                
                # Insert image descriptions for rows between last_row and current row_num
                for check_row in range(last_row + 1, row_num + 1):
                    key = (sheet_idx, check_row)
                    if key in images_by_position:
                        for img in images_by_position[key]:
                            description = img.get('description', '[画像]')
                            combined_parts.append(f"[画像: {description}]\n")
                
                # Add text content
                row_text = " | ".join([str(val) for val in row_values if str(val).strip()])
                if row_text:
                    combined_parts.append(f"{row_text}\n")
                
                last_row = row_num
        
        return "".join(combined_parts)
    
    def structure_document(
        self,
        text_content: List[Dict[str, Any]],
        images: List[Dict[str, Any]],
        filename: str
    ) -> Dict[str, Any]:
        """
        Structure Excel document into a single document with merged content
        Returns: A dictionary with combined content, image URLs, and metadata
        """
        
        logger.info(f"Processing document: {filename}")
        logger.info(f"Text sheets: {len(text_content)}, Images: {len(images)}")
        
        # Generate descriptions for all images
        images_with_descriptions = []
        for img in images:
            try:
                img_base64 = img.get('data', '')
                if img_base64:
                    description = self.describe_image(img_base64)
                    img_copy = img.copy()
                    img_copy['description'] = description
                    images_with_descriptions.append(img_copy)
                    logger.info(f"Generated description for image {img.get('filename')}")
            except Exception as e:
                logger.error(f"Error describing image {img.get('filename')}: {str(e)}")
                img_copy = img.copy()
                img_copy['description'] = '[画像の説明を生成できませんでした]'
                images_with_descriptions.append(img_copy)
        
        # Merge text and image descriptions
        combined_content = self.merge_text_and_image_descriptions(
            text_content, 
            images_with_descriptions
        )
        
        logger.info(f"Combined content length: {len(combined_content)} characters")
        
        # Prepare result
        result = {
            'filename': filename,
            'content': combined_content,
            'images': images,  # Keep original images with URLs for display
            'metadata': {
                'sheet_count': len(text_content),
                'image_count': len(images),
                'total_rows': sum(len(sheet.get('rows', [])) for sheet in text_content)
            }
        }
        
        return result
    
    def structure_document_legacy(
        self,
        text_content: List[Dict[str, Any]],
        images: List[Dict[str, Any]],
        filename: str
    ) -> List[Dict[str, Any]]:
        """Structure Excel document into procedure steps using multimodal LLM"""
        
        # Prepare the content for analysis
        text_summary = self._prepare_text_summary(text_content)
        
        # Create prompt for structuring
        system_prompt = """あなたは製造業の作業標準書を分析する専門家です。
Excel ファイルから抽出されたテキストと画像を元に、作業手順を構造化してください。

各手順について以下の情報を抽出してください：
1. 手順番号（step_number）
2. タイトル（title）
3. 詳細説明（description）
4. 関連する画像のインデックス（image_indices）
5. ページ番号や位置情報（metadata）

作業標準書に記載されていない情報は推測しないでください。
根拠がない場合は、その旨を明記してください。

出力は以下のJSON形式で返してください：
{
  "steps": [
    {
      "step_number": "1",
      "title": "手順のタイトル",
      "description": "手順の詳細説明",
      "image_indices": [0, 1],
      "metadata": {
        "sheet": "シート名",
        "row_start": 1,
        "row_end": 5
      }
    }
  ]
}
"""
        
        user_prompt = f"""以下のExcelファイル「{filename}」の内容を分析し、作業手順を構造化してください。

【テキスト内容】
{text_summary}

【画像情報】
画像数: {len(images)}
{self._prepare_image_summary(images)}

作業手順を抽出し、JSON形式で返してください。"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            steps = result.get("steps", [])
            
            # Associate images with steps
            for step in steps:
                step_images = []
                for img_idx in step.get("image_indices", []):
                    if 0 <= img_idx < len(images):
                        step_images.append(images[img_idx])
                step["images"] = step_images
            
            return steps
            
        except Exception as e:
            logger.error(f"Error structuring document with LLM: {str(e)}")
            # Fallback: create basic steps from sheets
            return self._create_fallback_steps(text_content, images)
    
    def _prepare_text_summary(self, text_content: List[Dict[str, Any]]) -> str:
        """Prepare text content summary for LLM"""
        summary_parts = []
        for sheet in text_content[:3]:  # Limit to first 3 sheets
            sheet_name = sheet.get('sheet_name', 'Unknown')
            rows = sheet.get('rows', [])
            summary_parts.append(f"\n【シート: {sheet_name}】")
            for row in rows[:50]:  # Limit to first 50 rows
                row_values = row.get('values', row) if isinstance(row, dict) else row
                row_text = " | ".join([str(cell) for cell in row_values if str(cell).strip()])
                if row_text:
                    row_num = row.get('row_number', '') if isinstance(row, dict) else ''
                    prefix = f"行{row_num}: " if row_num else ""
                    summary_parts.append(f"{prefix}{row_text}")
        
        return "\n".join(summary_parts)
    
    def _prepare_image_summary(self, images: List[Dict[str, Any]]) -> str:
        """Prepare image information summary"""
        summary_parts = []
        for i, img in enumerate(images):
            sheet = img.get('sheet', 'Unknown')
            position = img.get('position', {})
            pos_str = f"列{position.get('col')}, 行{position.get('row')}" if position else "位置不明"
            summary_parts.append(f"画像{i}: シート「{sheet}」, {pos_str}")
        
        return "\n".join(summary_parts)
    
    def _create_fallback_steps(
        self,
        text_content: List[Dict[str, Any]],
        images: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create basic steps as fallback when LLM fails"""
        steps = []
        
        for sheet_idx, sheet in enumerate(text_content):
            sheet_name = sheet.get('sheet_name', f'Sheet{sheet_idx+1}')
            rows = sheet.get('rows', [])
            
            # Find sheet-specific images
            sheet_images = [img for img in images if img.get('sheet') == sheet_name]
            
            steps.append({
                "step_number": str(sheet_idx + 1),
                "title": sheet_name,
                "description": f"シート「{sheet_name}」の内容\n行数: {len(rows)}",
                "images": sheet_images,
                "metadata": {
                    "sheet": sheet_name,
                    "row_count": len(rows)
                }
            })
        
        return steps
