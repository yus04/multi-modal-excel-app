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
    
    def structure_document(
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
            for i, row in enumerate(rows[:50]):  # Limit to first 50 rows
                row_text = " | ".join([str(cell) for cell in row if str(cell).strip()])
                if row_text:
                    summary_parts.append(f"行{i+1}: {row_text}")
        
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
