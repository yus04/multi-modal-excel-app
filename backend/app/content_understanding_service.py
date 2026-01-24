"""
Azure AI Content Understanding Service
ユーザー定義のスキーマに基づいてExcelファイルからフィールドを抽出
"""
import logging
from typing import List, Dict, Any, Optional
from openai import AzureOpenAI
import json

logger = logging.getLogger(__name__)


class ContentUnderstandingService:
    """Azure AI Content Understanding を使用してドキュメントからフィールドを抽出"""
    
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment_name: str,
        api_version: str
    ):
        """
        Initialize Content Understanding Service
        
        Args:
            endpoint: Azure OpenAI endpoint
            api_key: Azure OpenAI API key
            deployment_name: Deployment name (GPT-4o or similar multimodal model)
            api_version: API version
        """
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        self.deployment_name = deployment_name
        logger.info(f"ContentUnderstandingService initialized with deployment: {deployment_name}")
    
    def extract_fields_from_excel(
        self,
        text_content: List[Dict[str, Any]],
        images: List[Dict[str, Any]],
        schema: Dict[str, Any],
        filename: str
    ) -> Dict[str, Any]:
        """
        スキーマに基づいてExcelファイルからフィールドを抽出
        
        Args:
            text_content: Excelシートのテキストコンテンツ
            images: 抽出された画像リスト（base64エンコード済み）
            schema: フィールド定義を含むスキーマ
            filename: ファイル名
        
        Returns:
            抽出されたフィールドを含む辞書
        """
        logger.info(f"Extracting fields from {filename} using schema: {schema.get('name', 'Unknown')}")
        
        # スキーマからフィールド定義を取得
        field_definitions = schema.get('fields', [])
        if not field_definitions:
            logger.warning("No field definitions found in schema")
            return {}
        
        # テキストコンテンツをまとめる
        text_summary = self._prepare_text_summary(text_content)
        
        # 画像情報をまとめる（最初の数枚のみ）
        image_summary = self._prepare_image_summary(images)
        
        # システムプロンプトを構築
        system_prompt = self._build_system_prompt(field_definitions)
        
        # ユーザープロンプトを構築
        user_prompt = self._build_user_prompt(filename, text_summary, image_summary, field_definitions)
        
        # 画像がある場合はマルチモーダルリクエストを送信
        if images:
            extracted_fields = self._extract_with_images(
                system_prompt,
                user_prompt,
                images[:5],  # 最初の5枚の画像のみ使用
                field_definitions
            )
        else:
            extracted_fields = self._extract_text_only(
                system_prompt,
                user_prompt,
                field_definitions
            )
        
        # 画像フィールドの処理: 画像の説明とOCRを実行
        extracted_fields = self._process_image_fields(
            extracted_fields, 
            field_definitions, 
            images
        )
        
        logger.info(f"Successfully extracted {len(extracted_fields)} fields")
        return extracted_fields
    
    def _build_system_prompt(self, field_definitions: List[Dict[str, Any]]) -> str:
        """システムプロンプトを構築"""
        field_descriptions = []
        for field in field_definitions:
            field_name = field.get('name', '')
            field_type = field.get('data_type', 'text')
            description = field.get('description', '')
            
            if field_type == 'table':
                # Table type field with sub-fields
                sub_fields = field.get('sub_fields', [])
                sub_field_names = ', '.join([sf.get('name', '') for sf in sub_fields])
                field_descriptions.append(
                    f"- {field_name} (table): {description}\n  サブフィールド: [{sub_field_names}] - 複数行のデータを配列として抽出"
                )
            else:
                field_descriptions.append(
                    f"- {field_name} ({field_type}): {description}"
                )
        
        fields_text = "\n".join(field_descriptions)
        
        return f"""あなたはExcelファイルから構造化データを抽出する専門家です。
ユーザーが定義したスキーマに基づいて、Excelファイルのテキストと画像から必要なフィールドを抽出してください。

【抽出対象フィールド】
{fields_text}

【重要な指示】
1. Excelファイルの内容を注意深く分析してください
2. スキーマで定義された各フィールドに対応する値を探してください
3. 明確に記載されている情報のみを抽出してください
4. 推測や想像で値を埋めないでください
5. 値が見つからない場合は null を返してください
6. 日付フィールドは ISO 8601 形式（YYYY-MM-DD）で返してください
7. 数値フィールドは数値型で返してください
8. テキストフィールドは文字列で返してください
9. **テーブル型フィールドは配列として返してください** - Excelの表構造（縦に並んだ複数行）を検出し、各行を配列の要素として抽出
10. テーブルの各行は、定義されたサブフィールドを含むオブジェクトとして返してください

JSON形式で結果を返してください。各フィールド名をキーとして、抽出された値を値として設定してください。

【テーブル型の例】
入力: 工程番号、工程名、実施詳細が表形式で縦に3行ある
出力: {{"工程一覧": [{{"工程番号": "1", "工程名": "電源投入", "実施詳細": "..."}}, {{"工程番号": "2", "工程名": "材料セット", "実施詳細": "..."}}, {{"工程番号": "3", ...}}]}}"""

    
    def _build_user_prompt(
        self,
        filename: str,
        text_summary: str,
        image_summary: str,
        field_definitions: List[Dict[str, Any]]
    ) -> str:
        """ユーザープロンプトを構築"""
        field_names = [field.get('name', '') for field in field_definitions]
        fields_list = ", ".join(field_names)
        
        return f"""以下のExcelファイル「{filename}」から、指定されたフィールドを抽出してください。

【Excelファイルのテキスト内容】
{text_summary}

【画像情報】
{image_summary}

【抽出するフィールド】
{fields_list}

上記のフィールドに対応する値を、Excelファイルの内容から抽出し、JSON形式で返してください。
例: {{"field1": "value1", "field2": 123, "field3": null}}"""
    
    def _prepare_text_summary(self, text_content: List[Dict[str, Any]]) -> str:
        """テキストコンテンツのサマリーを準備"""
        if not text_content:
            return "テキストコンテンツなし"
        
        summary_parts = []
        for sheet in text_content[:3]:  # 最初の3シートのみ
            sheet_name = sheet.get('sheet_name', 'Unknown')
            rows = sheet.get('rows', [])
            summary_parts.append(f"\n【シート: {sheet_name}】")
            
            for row in rows[:100]:  # 最初の100行のみ
                row_num = row.get('row_number', '')
                row_values = row.get('values', [])
                row_text = " | ".join([str(val) for val in row_values if str(val).strip()])
                if row_text:
                    summary_parts.append(f"行{row_num}: {row_text}")
        
        full_summary = "\n".join(summary_parts)
        # 最大15000文字に制限
        if len(full_summary) > 15000:
            return full_summary[:15000] + "\n... (省略)"
        return full_summary
    
    def _prepare_image_summary(self, images: List[Dict[str, Any]]) -> str:
        """画像情報のサマリーを準備"""
        if not images:
            return "画像なし"
        
        summary_parts = [f"画像数: {len(images)}"]
        for i, img in enumerate(images[:5]):  # 最初の5枚のみ
            sheet = img.get('sheet', 'Unknown')
            position = img.get('position', {})
            if position:
                pos_str = f"列{position.get('col', '?')}, 行{position.get('row', '?')}"
            else:
                pos_str = "位置不明"
            summary_parts.append(f"画像{i+1}: シート「{sheet}」, {pos_str}")
        
        if len(images) > 5:
            summary_parts.append(f"... 他 {len(images) - 5} 枚")
        
        return "\n".join(summary_parts)
    
    def _extract_with_images(
        self,
        system_prompt: str,
        user_prompt: str,
        images: List[Dict[str, Any]],
        field_definitions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """画像を含むマルチモーダルリクエストでフィールドを抽出"""
        try:
            # ユーザーコンテンツを構築（テキスト + 画像）
            user_content = [{"type": "text", "text": user_prompt}]
            
            # 画像を追加
            for img in images:
                img_base64 = img.get('data', '')
                if img_base64:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_base64}",
                            "detail": "high"
                        }
                    })
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            extracted_fields = json.loads(result_text)
            
            logger.info("Successfully extracted fields with multimodal request")
            return extracted_fields
            
        except Exception as e:
            logger.error(f"Error extracting fields with images: {str(e)}")
            # フォールバック: テキストのみで再試行
            return self._extract_text_only(system_prompt, user_prompt, field_definitions)
    
    def _extract_text_only(
        self,
        system_prompt: str,
        user_prompt: str,
        field_definitions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """テキストのみでフィールドを抽出"""
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
            
            result_text = response.choices[0].message.content
            extracted_fields = json.loads(result_text)
            
            logger.info("Successfully extracted fields with text-only request")
            return extracted_fields
            
        except Exception as e:
            logger.error(f"Error extracting fields: {str(e)}")
            # フォールバック: 空の結果を返す
            return {field.get('name', ''): None for field in field_definitions}
    
    def describe_image(self, image_base64: str) -> str:
        """画像の説明を生成（既存のLLMサービスとの互換性のため）"""
        try:
            system_prompt = """あなたは製造業の作業標準書に含まれる画像を説明する専門家です。
画像の内容を日本語で詳細に説明してください。"""
            
            user_content = [
                {"type": "text", "text": "この画像の内容を詳細に説明してください。"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_base64}"}
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
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating image description: {str(e)}")
            return f"[画像の説明を生成できませんでした: {type(e).__name__}]"
    
    def analyze_image_with_reasoning_and_ocr(self, image_base64: str, image_index: int = 1) -> str:
        """
        GPT-5.2でReasoningを使って画像を分析し、特徴説明とOCRを実行
        
        Args:
            image_base64: Base64エンコードされた画像データ
            image_index: 画像の番号（ログ用）
            
        Returns:
            画像の特徴説明とOCRテキストを合わせた文字列
        """
        try:
            system_prompt = """あなたは製造業の作業標準書に含まれる画像を分析する専門家です。
画像を注意深く観察し、以下の情報を抽出してください：

1. **画像の特徴説明**: 画像に何が映っているか、どのような状態か、重要なポイントは何かを詳細に説明
2. **OCR（テキスト抽出）**: 画像内に含まれるすべてのテキスト（日本語、英語、数字、記号など）を正確に抽出

深く考えて（reasoning）、画像の文脈を理解した上で分析してください。"""
            
            user_content = [
                {
                    "type": "text", 
                    "text": """この画像を分析し、以下の2つの情報を提供してください：

【特徴説明】
画像に何が映っているか、どのような状態・特徴があるかを詳細に説明してください。
機器、部品、操作、状態、注意点など、作業手順書として重要な情報を含めてください。

【OCRテキスト】
画像内に含まれるすべてのテキスト（ラベル、注釈、説明文、記号など）を正確に抽出してください。
テキストがない場合は「テキストなし」と記載してください。

以下のフォーマットで回答してください：
---
【特徴説明】
(画像の詳細な説明)

【OCRテキスト】
(抽出されたテキスト)
---"""
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": "high"
                    }
                }
            ]
            
            logger.info(f"Analyzing image {image_index} with reasoning and OCR...")
            
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.1,
                max_tokens=1500  # Longer for detailed analysis
            )
            
            result = response.choices[0].message.content
            logger.info(f"Successfully analyzed image {image_index} ({len(result)} chars)")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing image {image_index} with reasoning and OCR: {str(e)}")
            return f"[画像{image_index}の分析に失敗: {type(e).__name__}]"
    
    def _process_image_fields(
        self,
        extracted_fields: Dict[str, Any],
        field_definitions: List[Dict[str, Any]],
        images: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        画像フィールドを処理し、GPT-5.2でReasoningとOCRを実行
        
        Args:
            extracted_fields: 抽出されたフィールド
            field_definitions: フィールド定義
            images: 画像リスト
            
        Returns:
            画像分析結果を含む更新されたフィールド
        """
        if not images:
            logger.info("No images to process")
            return extracted_fields
        
        # 画像フィールドを特定
        image_fields = []
        for field_def in field_definitions:
            if field_def.get('data_type') == 'image':
                image_fields.append(field_def)
            # テーブル型のサブフィールドもチェック
            elif field_def.get('data_type') == 'table' and field_def.get('sub_fields'):
                for sub_field in field_def.get('sub_fields', []):
                    if sub_field.get('data_type') == 'image':
                        parent_name = field_def.get('name')
                        image_fields.append({
                            'name': sub_field.get('name'),
                            'parent': parent_name,
                            'is_sub_field': True
                        })
        
        if not image_fields:
            logger.info("No image fields defined in schema")
            return extracted_fields
        
        logger.info(f"Processing {len(image_fields)} image field(s) with {len(images)} image(s)")
        
        # 各画像フィールドを処理
        for field_info in image_fields:
            field_name = field_info.get('name')
            is_sub_field = field_info.get('is_sub_field', False)
            
            if is_sub_field:
                # サブフィールドの場合（テーブル内の画像）
                parent_name = field_info.get('parent')
                parent_value = extracted_fields.get(parent_name)
                
                if isinstance(parent_value, list):
                    # テーブルの各行の画像フィールドを処理
                    image_idx = 0
                    for row in parent_value:
                        if isinstance(row, dict) and field_name in row:
                            if image_idx < len(images):
                                img_data = images[image_idx].get('data', '')
                                if img_data:
                                    analysis = self.analyze_image_with_reasoning_and_ocr(img_data, image_idx + 1)
                                    row[field_name] = analysis
                                    image_idx += 1
            else:
                # トップレベルの画像フィールド
                field_value = extracted_fields.get(field_name)
                
                # フィールド値から画像数を推測（"画像1\n画像2\n..."のようなパターン）
                if isinstance(field_value, str):
                    image_count = field_value.count('画像')
                    
                    if image_count > 0 and len(images) > 0:
                        # 各画像を分析
                        analyzed_images = []
                        for i in range(min(image_count, len(images))):
                            img_data = images[i].get('data', '')
                            if img_data:
                                analysis = self.analyze_image_with_reasoning_and_ocr(img_data, i + 1)
                                analyzed_images.append(f"【画像{i + 1}】\n{analysis}")
                        
                        # 分析結果を結合して保存
                        if analyzed_images:
                            extracted_fields[field_name] = "\n\n".join(analyzed_images)
                            logger.info(f"Processed {len(analyzed_images)} image(s) for field '{field_name}'")
        
        return extracted_fields
