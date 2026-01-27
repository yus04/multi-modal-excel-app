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
        filename: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        スキーマに基づいてExcelファイルからフィールドを抽出
        
        Args:
            text_content: Excelシートのテキストコンテンツ
            images: 抽出された画像リスト（base64エンコード済み）
            schema: フィールド定義を含むスキーマ
            filename: ファイル名
            progress_callback: 進捗を報告するコールバック関数 (current, total, message)
        
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
            images,
            progress_callback
        )
        
        logger.info(f"Successfully extracted {len(extracted_fields)} fields")
        return extracted_fields
    
    def _build_system_prompt(self, field_definitions: List[Dict[str, Any]]) -> str:
        """システムプロンプトを構築"""
        field_descriptions = []
        has_long_text = False
        
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
            elif field_type == 'long_text':
                # Long text field - large text blocks spanning multiple rows
                has_long_text = True
                field_descriptions.append(
                    f"- {field_name} (long_text): {description}\n  **大きなテキストブロック** - 20～50行程度にわたるセル範囲のテキストを全て統合して抽出"
                )
            else:
                field_descriptions.append(
                    f"- {field_name} ({field_type}): {description}"
                )
        
        fields_text = "\n".join(field_descriptions)
        
        # Long text specific instructions
        long_text_instructions = ""
        if has_long_text:
            long_text_instructions = """\n\n【大きなテキストブロック (long_text) の抽出方法】
- Excelシート内で **結合セルや罫線で囲まれた大きな領域** を探してください
- 20行～50行程度にわたる連続したテキスト範囲を1つのフィールドとして認識してください
- 以下のような特徴を持つ領域が対象です：
  * 罫線や太枠で囲まれた大きな四角形の領域
  * 複数行にわたる説明文、コメント、詳細記述
  * 「備考」「詳細」「説明」「内容」などのラベルの下にある長文
- **全てのテキストを結合して1つの文字列として抽出してください**
- 行区切りは改行文字（\\n）で保持してください
- セル内の空白行も保持してください
- テキストの途中で切らずに、領域全体を抽出してください
- 表形式ではなく、1つの長いテキストとして返してください"""
        
        return f"""あなたはExcelファイルから構造化データを抽出する専門家です。
ユーザーが定義したスキーマに基づいて、Excelファイルのテキストと画像から必要なフィールドを抽出してください。

【抽出対象フィールド】
{fields_text}

【重要な指示】
1. **Excelの列ヘッダーと行データの対応関係を注意深く分析してください**
2. 各フィールドの説明をよく読み、**フィールド名や説明に含まれるキーワードと、Excel列ヘッダーのキーワードを照合してください**
3. スキーマで定義された各フィールドに対応する**正しい列**から値を抽出してください
4. 明確に記載されている情報のみを抽出してください
5. 推測や想像で値を埋めないでください。値が見つからない場合は null を返してください
6. 日付フィールドは ISO 8601 形式（YYYY-MM-DD）で返してください
7. 数値フィールドは数値型で返してください
8. テキストフィールドは文字列で返してください
9. **テーブル型フィールドは配列として返してください** - Excelの表構造（縦に並んだ複数行）を検出し、各行を配列の要素として抽出
10. テーブルの各行は、定義されたサブフィールドを含むオブジェクトとして返してください{long_text_instructions}

【フィールドとExcel列の対応付けルール】
- フィールドの「description」に記載されたキーワードと、Excel列ヘッダーのテキストを**完全に照合**してください
- **フィールドごとに正しい列を特定し、他の列のデータを絶対に混入させないでください**
- 列ヘッダーが明示されている場合は、必ずヘッダー名に基づいて対応する列を特定してください

【正しいマッピングの具体例】
例1: 作業標準書の場合
  Excel列:
    - 列A: 「作業手順」
    - 列B: 「急所(条件)」
    - 列C: 「使用機械・治具・計測器等」
  
  スキーマフィールド:
    - フィールド「作業手順」(説明: 作業の手順) → 列A「作業手順」から抽出
    - フィールド「急所(条件)」(説明: 作業の急所や条件) → 列B「急所(条件)」から抽出
    - フィールド「使用機械・治具・計測器等」(説明: 使用する機械、治具、計測器) → 列C「使用機械・治具・計測器等」から抽出
  
  ✓ 正しい抽出:
    {{"作業手順": "ベアリング・外刃交換", "急所(条件)": "リフターでかぶたを開ける", "使用機械・治具・計測器等": "リフター、六角レンチ、メガネレンチ"}}
  
  ✗ 間違った抽出（絶対にしないでください）:
    {{"作業手順": "ベアリング・外刃交換", "急所(条件)": "", "使用機械・治具・計測器等": "リフターでかぶたを開ける、リフター、六角レンチ"}}
    → 列Bのデータが列Cに混入している！

例2: 複数列にまたがるデータの場合
  各フィールドは**1つの特定の列にのみ対応**します。
  複数の列からデータを取得してはいけません。

JSON形式で結果を返してください。各フィールド名をキーとして、抽出された値を値として設定してください。

【テーブル型の例】
入力: 工程番号、工程名、実施詳細が表形式で縦に3行ある
出力: {{"工程一覧": [{{"工程番号": "1", "工程名": "電源投入", "実施詳細": "..."}}, {{"工程番号": "2", "工程名": "材料セット", "実施詳細": "..."}}, {{"工程番号": "3", ...}}]}}

【長文テキスト型の例】
入力: 「作業手順詳細」という枠内に30行にわたる説明文がある
出力: {{"作業手順詳細": "1. 電源を投入する\\n2. 初期画面が表示されるまで待つ\\n3. ...(全30行のテキスト)"}}"""

    
    def _build_user_prompt(
        self,
        filename: str,
        text_summary: str,
        image_summary: str,
        field_definitions: List[Dict[str, Any]]
    ) -> str:
        """ユーザープロンプトを構築（フィールド詳細情報を含む）"""
        # 各フィールドの詳細情報を構築
        field_details = []
        for field in field_definitions:
            field_name = field.get('name', '')
            field_type = field.get('data_type', 'text')
            description = field.get('description', '')
            
            if field_type == 'table':
                sub_fields = field.get('sub_fields', [])
                sub_field_names = ', '.join([sf.get('name', '') for sf in sub_fields])
                field_details.append(
                    f"  ◆ フィールド名: {field_name}\n"
                    f"    型: table (表形式)\n"
                    f"    説明: {description}\n"
                    f"    サブフィールド: [{sub_field_names}]\n"
                    f"    → Excelの表形式データから、複数行を配列として抽出"
                )
            else:
                field_details.append(
                    f"  ◆ フィールド名: {field_name}\n"
                    f"    型: {field_type}\n"
                    f"    説明: {description}\n"
                    f"    → Excel内で '{description}' に関連する列またはセルから値を抽出"
                )
        
        fields_detail_text = "\n".join(field_details)
        
        return f"""以下のExcelファイル「{filename}」から、指定されたフィールドを抽出してください。

【Excelファイルのテキスト内容】
{text_summary}

【画像情報】
{image_summary}

【抽出対象フィールドの詳細】
各フィールドの説明をよく読み、Excel内の**対応する列またはセル**から正確に値を抽出してください。
**異なるフィールドのデータを混同しないよう注意してください。**

{fields_detail_text}

【抽出手順】
1. 上記の各フィールドについて、Excelの列ヘッダーまたはラベルを確認
2. フィールドの「説明」に記載されたキーワードと、Excel内のヘッダーやラベルを照合
3. 該当する列またはセルから値を抽出
4. 他のフィールド用の列からデータを誤って取得しないよう注意
5. JSON形式で結果を返す

例: {{"フィールド名1": "値1", "フィールド名2": 123, "フィールド名3": null}}"""
    
    def _prepare_text_summary(self, text_content: List[Dict[str, Any]]) -> str:
        """テキストコンテンツのサマリーを準備"""
        if not text_content:
            return "テキストコンテンツなし"
        
        summary_parts = []
        for sheet in text_content[:3]:  # 最初の3シートのみ
            sheet_name = sheet.get('sheet_name', 'Unknown')
            rows = sheet.get('rows', [])
            summary_parts.append(f"\n【シート: {sheet_name}】")
            
            # Excelの行データをそのまま表示（LLMが自動的に列を識別）
            for row in rows[:100]:  # 最初の100行のみ
                row_num = row.get('row_number', '')
                row_values = row.get('values', [])
                
                # 列インデックスと値をペアで表示
                row_parts = []
                for i, val in enumerate(row_values):
                    val_str = str(val).strip()
                    if val_str:
                        row_parts.append(f"列{i+1}={val_str}")
                
                if row_parts:
                    summary_parts.append(f"行{row_num}: {', '.join(row_parts)}")
        
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

1. **画像の特徴説明**: 検索に役立つキーワードを50文字以内で端的に記載
2. **OCR（テキスト抽出）**: 画像内に含まれるすべてのテキスト（日本語、英語、数字、記号など）を正確に抽出

深く考えて（reasoning）、画像の文脈を理解した上で分析してください。"""
            
            user_content = [
                {
                    "type": "text", 
                    "text": """この画像を分析し、以下の2つの情報を提供してください：

【特徴説明】
画像の内容をキーワードで端的に記載してください（50文字以内）。
機器名、部品名、操作、重要なポイントなどをカンマ区切りで列挙してください。
例: ベアリング交換作業、リフター使用、六角レンチ、メガネレンチ

【OCRテキスト】
画像内に含まれるすべてのテキスト（ラベル、注釈、説明文、記号など）を正確に抽出してください。
テキストがない場合は「テキストなし」と記載してください。

以下のフォーマットで回答してください：
---
【特徴説明】
(50文字以内のキーワード)

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
        images: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        画像フィールドを処理し、GPT-5.2でReasoningとOCRを実行
        
        Args:
            extracted_fields: 抽出されたフィールド
            field_definitions: フィールド定義
            images: 画像リスト
            progress_callback: 進捗を報告するコールバック関数 (current, total, message)
            
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
                image_fields.append({
                    'name': field_def.get('name'),
                    'is_sub_field': False
                })
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
                        if isinstance(row, dict):
                            if image_idx < len(images):
                                img_data = images[image_idx].get('data', '')
                                if img_data:
                                    logger.info(f"Analyzing image {image_idx + 1} for table field '{field_name}'")
                                    if progress_callback:
                                        progress_callback(image_idx, len(images), f"画像 {image_idx + 1}/{len(images)} を分析中")
                                    analysis = self.analyze_image_with_reasoning_and_ocr(img_data, image_idx + 1)
                                    row[field_name] = analysis
                                    image_idx += 1
                                    if progress_callback:
                                        progress_callback(image_idx, len(images), f"画像 {image_idx}/{len(images)} を処理完了")
            else:
                # トップレベルの画像フィールド - すべての画像を分析
                if len(images) > 0:
                    analyzed_images = []
                    for i, img in enumerate(images):
                        img_data = img.get('data', '')
                        if img_data:
                            logger.info(f"Analyzing image {i + 1}/{len(images)} for field '{field_name}'")
                            if progress_callback:
                                progress_callback(i, len(images), f"画像 {i + 1}/{len(images)} を分析中")
                            analysis = self.analyze_image_with_reasoning_and_ocr(img_data, i + 1)
                            analyzed_images.append(f"【画像{i + 1}】\n{analysis}")
                            if progress_callback:
                                progress_callback(i + 1, len(images), f"画像 {i + 1}/{len(images)} を処理完了")
                    
                    # 分析結果を結合して保存
                    if analyzed_images:
                        extracted_fields[field_name] = "\n\n".join(analyzed_images)
                        logger.info(f"Successfully processed {len(analyzed_images)} image(s) for field '{field_name}'")
        
        return extracted_fields
