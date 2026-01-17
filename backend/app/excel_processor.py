import io
import os
import tempfile
import base64
from typing import List, Dict, Any, Tuple
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class ExcelProcessor:
    """Process Excel files to extract content and images"""
    
    @staticmethod
    async def extract_images_from_excel(file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """Extract all images from an Excel file"""
        images = []
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            workbook = load_workbook(tmp_path)
            
            for sheet_idx, sheet in enumerate(workbook.worksheets):
                if hasattr(sheet, '_images'):
                    for img_idx, img in enumerate(sheet._images):
                        try:
                            image_data = img.ref
                            if hasattr(img, '_data'):
                                pil_image = Image.open(io.BytesIO(img._data()))
                            elif hasattr(image_data, 'data'):
                                pil_image = Image.open(io.BytesIO(image_data.data))
                            else:
                                continue
                            
                            # Convert to PNG and encode as base64
                            img_byte_arr = io.BytesIO()
                            pil_image.save(img_byte_arr, format='PNG')
                            img_byte_arr.seek(0)
                            
                            img_base64 = base64.b64encode(img_byte_arr.read()).decode('utf-8')
                            
                            # Get anchor position if available
                            anchor = getattr(img, 'anchor', None)
                            position = None
                            if anchor and hasattr(anchor, '_from'):
                                position = {
                                    'col': anchor._from.col,
                                    'row': anchor._from.row
                                }
                            
                            images.append({
                                'sheet': sheet.title,
                                'sheet_index': sheet_idx,
                                'image_index': img_idx,
                                'data': img_base64,
                                'position': position,
                                'filename': f"{os.path.splitext(filename)[0]}_sheet{sheet_idx}_img{img_idx}.png"
                            })
                        except Exception as e:
                            logger.warning(f"Error extracting image {img_idx} from sheet {sheet.title}: {str(e)}")
            
            os.unlink(tmp_path)
            return images
            
        except Exception as e:
            logger.error(f"Error processing Excel file {filename}: {str(e)}")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    
    @staticmethod
    async def extract_text_from_excel(file_content: bytes) -> List[Dict[str, Any]]:
        """Extract text content from Excel sheets"""
        sheets_data = []
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            workbook = load_workbook(tmp_path, data_only=True)
            
            for sheet in workbook.worksheets:
                rows_data = []
                for row in sheet.iter_rows(values_only=True):
                    # Filter out empty rows
                    row_values = [str(cell) if cell is not None else "" for cell in row]
                    if any(val.strip() for val in row_values):
                        rows_data.append(row_values)
                
                sheets_data.append({
                    'sheet_name': sheet.title,
                    'rows': rows_data
                })
            
            os.unlink(tmp_path)
            return sheets_data
            
        except Exception as e:
            logger.error(f"Error extracting text from Excel: {str(e)}")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
