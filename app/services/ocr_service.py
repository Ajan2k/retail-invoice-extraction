"""
OCR Service for invoice text extraction
Uses commercial-safe libraries: OpenCV + EasyOCR
"""

import cv2
import numpy as np
import easyocr
from PIL import Image
import io
import logging
from typing import Dict, List, Tuple, Optional
import time

logger = logging.getLogger(__name__)

class OCRService:
    """OCR service for extracting text from invoice images."""
    
    def __init__(self):
        """Initialize OCR service with EasyOCR reader."""
        self.reader = None
        self._initialize_reader()
    
    def _initialize_reader(self):
        """Initialize EasyOCR reader with English language support."""
        try:
            # Initialize EasyOCR with English language
            self.reader = easyocr.Reader(['en'], gpu=False)  # Use CPU for compatibility
            logger.info("EasyOCR reader initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR reader: {str(e)}")
            raise
    
    def preprocess_image(self, image_data: bytes) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Preprocessed image as numpy array
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert PIL to OpenCV format
            opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Apply preprocessing steps
            processed_image = self._apply_preprocessing_steps(opencv_image)
            
            return processed_image
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {str(e)}")
            raise ValueError(f"Failed to preprocess image: {str(e)}")
    
    def _apply_preprocessing_steps(self, image: np.ndarray) -> np.ndarray:
        """
        Apply various preprocessing steps to improve OCR accuracy.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Apply morphological operations to clean up
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Deskew if necessary (basic rotation correction)
        cleaned = self._deskew_image(cleaned)
        
        return cleaned
    
    def _deskew_image(self, image: np.ndarray) -> np.ndarray:
        """
        Attempt to correct skew in the image.
        
        Args:
            image: Input image
            
        Returns:
            Deskewed image
        """
        try:
            # Find edges
            edges = cv2.Canny(image, 50, 150, apertureSize=3)
            
            # Find lines using Hough transform
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is not None and len(lines) > 0:
                # Calculate average angle
                angles = []
                for rho, theta in lines[:10]:  # Use first 10 lines
                    angle = np.degrees(theta) - 90
                    angles.append(angle)
                
                if angles:
                    median_angle = np.median(angles)
                    
                    # Only correct if angle is significant but not too large
                    if 1 < abs(median_angle) < 45:
                        center = (image.shape[1] // 2, image.shape[0] // 2)
                        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                        rotated = cv2.warpAffine(image, rotation_matrix, (image.shape[1], image.shape[0]))
                        return rotated
            
            return image
            
        except Exception as e:
            logger.warning(f"Deskewing failed: {str(e)}")
            return image
    
    def extract_text(self, image_data: bytes, confidence_threshold: float = 0.7) -> Dict:
        """
        Extract text from image using OCR.
        
        Args:
            image_data: Raw image bytes
            confidence_threshold: Minimum confidence for text extraction
            
        Returns:
            Dictionary containing extracted text and metadata
        """
        start_time = time.time()
        
        try:
            # Preprocess image
            processed_image = self.preprocess_image(image_data)
            
            # Perform OCR
            results = self.reader.readtext(processed_image)
            
            # Process results
            extracted_data = self._process_ocr_results(results, confidence_threshold)
            
            processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Add metadata
            extracted_data.update({
                'processing_time_ms': processing_time,
                'ocr_engine': 'EasyOCR',
                'preprocessing_applied': True,
                'confidence_threshold': confidence_threshold
            })
            
            logger.info(f"OCR extraction completed in {processing_time:.2f}ms")
            return extracted_data
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            raise RuntimeError(f"OCR extraction failed: {str(e)}")
    
    def _process_ocr_results(self, results: List, confidence_threshold: float) -> Dict:
        """
        Process OCR results and organize extracted text.
        
        Args:
            results: Raw OCR results from EasyOCR
            confidence_threshold: Minimum confidence threshold
            
        Returns:
            Processed text data with confidence scores
        """
        full_text = ""
        high_confidence_text = ""
        text_blocks = []
        total_confidence = 0.0
        valid_blocks = 0
        
        for result in results:
            try:
                # EasyOCR returns (bounding_box, text, confidence)
                bounding_box, text, confidence = result
                
                # Clean up text
                cleaned_text = text.strip()
                if not cleaned_text:
                    continue
                
                # Create text block
                text_block = {
                    'text': cleaned_text,
                    'confidence': confidence,
                    'bounding_box': bounding_box,
                    'above_threshold': confidence >= confidence_threshold
                }
                
                text_blocks.append(text_block)
                full_text += cleaned_text + " "
                
                if confidence >= confidence_threshold:
                    high_confidence_text += cleaned_text + " "
                    total_confidence += confidence
                    valid_blocks += 1
                
            except Exception as e:
                logger.warning(f"Error processing OCR result: {str(e)}")
                continue
        
        # Calculate average confidence
        average_confidence = total_confidence / valid_blocks if valid_blocks > 0 else 0.0
        
        return {
            'full_text': full_text.strip(),
            'high_confidence_text': high_confidence_text.strip(),
            'text_blocks': text_blocks,
            'total_blocks': len(text_blocks),
            'high_confidence_blocks': valid_blocks,
            'average_confidence': average_confidence,
            'overall_confidence': min(average_confidence, len(text_blocks) / max(len(results), 1))
        }
    
    def extract_text_regions(self, image_data: bytes, regions: List[Dict]) -> Dict:
        """
        Extract text from specific regions of the image.
        
        Args:
            image_data: Raw image bytes
            regions: List of regions to extract from (x, y, width, height)
            
        Returns:
            Dictionary containing text extracted from each region
        """
        try:
            # Preprocess image
            processed_image = self.preprocess_image(image_data)
            
            region_results = {}
            
            for i, region in enumerate(regions):
                try:
                    x, y, w, h = region['x'], region['y'], region['width'], region['height']
                    
                    # Extract region
                    roi = processed_image[y:y+h, x:x+w]
                    
                    # Perform OCR on region
                    results = self.reader.readtext(roi)
                    
                    # Process results for this region
                    region_text = ""
                    region_confidence = 0.0
                    block_count = 0
                    
                    for result in results:
                        _, text, confidence = result
                        cleaned_text = text.strip()
                        if cleaned_text:
                            region_text += cleaned_text + " "
                            region_confidence += confidence
                            block_count += 1
                    
                    region_results[f"region_{i}"] = {
                        'text': region_text.strip(),
                        'confidence': region_confidence / block_count if block_count > 0 else 0.0,
                        'block_count': block_count,
                        'region': region
                    }
                    
                except Exception as e:
                    logger.warning(f"Failed to extract text from region {i}: {str(e)}")
                    region_results[f"region_{i}"] = {
                        'text': "",
                        'confidence': 0.0,
                        'block_count': 0,
                        'region': region,
                        'error': str(e)
                    }
            
            return region_results
            
        except Exception as e:
            logger.error(f"Region-based text extraction failed: {str(e)}")
            raise RuntimeError(f"Region-based text extraction failed: {str(e)}")
    
    def detect_text_orientation(self, image_data: bytes) -> Dict:
        """
        Detect text orientation in the image.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Dictionary containing orientation information
        """
        try:
            # Preprocess image
            processed_image = self.preprocess_image(image_data)
            
            # Try OCR with different orientations
            orientations = [0, 90, 180, 270]
            best_orientation = 0
            best_confidence = 0.0
            
            for angle in orientations:
                # Rotate image
                if angle > 0:
                    center = (processed_image.shape[1] // 2, processed_image.shape[0] // 2)
                    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                    rotated = cv2.warpAffine(processed_image, rotation_matrix, 
                                           (processed_image.shape[1], processed_image.shape[0]))
                else:
                    rotated = processed_image
                
                # Perform OCR
                results = self.reader.readtext(rotated)
                
                # Calculate average confidence
                if results:
                    confidences = [conf for _, _, conf in results]
                    avg_confidence = sum(confidences) / len(confidences)
                    
                    if avg_confidence > best_confidence:
                        best_confidence = avg_confidence
                        best_orientation = angle
            
            return {
                'best_orientation': best_orientation,
                'confidence': best_confidence,
                'rotation_needed': best_orientation != 0
            }
            
        except Exception as e:
            logger.error(f"Text orientation detection failed: {str(e)}")
            return {
                'best_orientation': 0,
                'confidence': 0.0,
                'rotation_needed': False,
                'error': str(e)
            }
    
    def get_text_statistics(self, text: str) -> Dict:
        """
        Get statistics about extracted text.
        
        Args:
            text: Extracted text
            
        Returns:
            Dictionary containing text statistics
        """
        import re
        
        if not text:
            return {
                'character_count': 0,
                'word_count': 0,
                'line_count': 0,
                'number_count': 0,
                'email_count': 0,
                'phone_count': 0,
                'date_count': 0,
                'currency_count': 0
            }
        
        # Basic counts
        character_count = len(text)
        word_count = len(text.split())
        line_count = len(text.split('\n'))
        
        # Pattern matches
        number_pattern = r'\b\d+\.?\d*\b'
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'[\+]?[1-9]?[0-9]{7,15}'
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{2,4}[/-]\d{1,2}[/-]\d{1,2}\b'
        currency_pattern = r'[$€£¥₹]\s*\d+\.?\d*|\b\d+\.?\d*\s*(?:USD|EUR|GBP|JPY|INR)\b'
        
        number_count = len(re.findall(number_pattern, text))
        email_count = len(re.findall(email_pattern, text))
        phone_count = len(re.findall(phone_pattern, text))
        date_count = len(re.findall(date_pattern, text))
        currency_count = len(re.findall(currency_pattern, text, re.IGNORECASE))
        
        return {
            'character_count': character_count,
            'word_count': word_count,
            'line_count': line_count,
            'number_count': number_count,
            'email_count': email_count,
            'phone_count': phone_count,
            'date_count': date_count,
            'currency_count': currency_count
        }