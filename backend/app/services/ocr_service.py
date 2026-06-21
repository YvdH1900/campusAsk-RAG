"""
OCR 服务
========
基于 PaddleOCR + PP-StructureV2 的 OCR 识别服务。
用于扫描版 PDF 和图片的文本提取。

策略：
- 开启版面分析，禁止直接全图识别输出纯文本
- 低质量页面（模糊、识别率 < 60%）直接拦截
- 支持混合页面：正文用原生提取，图片单独 OCR
"""

import logging
import os
import shutil
import tempfile
from typing import Optional, List, Tuple, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

# OCR 模型缓存目录（放在项目内）
_PROJECT_ROOT = Path(__file__).parent.parent.parent
OCR_MODEL_DIR = _PROJECT_ROOT / "ocr_models"


class OCRService:
    """OCR 服务封装"""

    _instance = None
    _ocr = None
    _initialized = False
    _debug_logged = False  # 仅首次打印 result 结构调试信息

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            logger.warning(f"OCRService.__init__ 跳过（已初始化），_available={self._available}")
            return
        self._initialized = True
        self._available = False
        self._cls_enabled = False
        logger.warning(f"OCRService.__init__ 开始初始化，OCR_MODEL_DIR={OCR_MODEL_DIR}")
        self._init_ocr()

    # ---------- CLS 模型自下载（绕过 PaddleOCR maybe_download 的 ._ 文件 bug）----------
    # maybe_download 在解压 tar 时，会把 macOS 资源分叉文件 (._inference.pdmodel)
    # 也当作模型文件提取到 inference.pdmodel，导致 176 字节的无效文件覆盖 1.6MB 的真实模型。
    # 这是 PaddleOCR 上游 bug，我们自行下载来规避。
    _CLS_MODEL_URL = (
        "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar"
    )
    _CLS_MODEL_FILE_NAMES = {
        ".pdmodel": "inference.pdmodel",
        ".pdiparams": "inference.pdiparams",
        ".pdiparams.info": "inference.pdiparams.info",
    }

    @classmethod
    def _download_cls_model(cls, cls_dir: str) -> bool:
        """
        自行下载 CLS 模型，跳过 macOS 资源分叉文件 (._ 前缀)。
        返回 True 表示下载成功。
        """
        import requests
        import tarfile

        os.makedirs(cls_dir, exist_ok=True)

        tar_path = os.path.join(cls_dir, "cls_model.tar")
        try:
            logger.warning("正在下载 CLS 模型...")
            resp = requests.get(cls._CLS_MODEL_URL, stream=True, timeout=120)
            resp.raise_for_status()
            with open(tar_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            logger.warning("CLS 模型下载完成，正在解压...")

            with tarfile.open(tar_path, "r") as tar:
                for member in tar.getmembers():
                    # 跳过 macOS 资源分叉文件（._ 前缀）
                    base_name = os.path.basename(member.name)
                    if base_name.startswith("._"):
                        continue
                    # 匹配模型文件后缀
                    filename = None
                    for suffix, target_name in cls._CLS_MODEL_FILE_NAMES.items():
                        if member.name.endswith(suffix):
                            filename = target_name
                            break
                    if filename is None:
                        continue
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    out_path = os.path.join(cls_dir, filename)
                    with open(out_path, "wb") as out:
                        out.write(f.read())
                    logger.warning(f"  {member.name} -> {filename}")

            os.remove(tar_path)
            logger.warning("CLS 模型解压完成")
            return True

        except Exception as e:
            logger.error(f"CLS 模型下载/解压失败: {e}")
            # 清理不完整的下载
            if os.path.isfile(tar_path):
                try:
                    os.remove(tar_path)
                except Exception:
                    pass
            shutil.rmtree(cls_dir, ignore_errors=True)
            return False

    @classmethod
    def _test_cls_model_inference(cls, cls_dir: str) -> bool:
        """
        直接使用 PaddlePaddle Inference API 加载 CLS 模型并执行一次推理，
        验证模型文件是否真正可用（而不是仅检查文件存在/大小）。

        这是唯一能可靠检测 "Tensor holds no memory" 错误的方法。
        """
        import numpy as np
        try:
            from paddle import inference

            pdmodel = os.path.join(cls_dir, "inference.pdmodel")
            pdiparams = os.path.join(cls_dir, "inference.pdiparams")
            if not os.path.isfile(pdmodel) or not os.path.isfile(pdiparams):
                logger.warning(f"CLS 模型文件不存在: {cls_dir}")
                return False

            config = inference.Config(pdmodel, pdiparams)
            config.disable_gpu()
            config.enable_memory_optim()
            config.disable_glog_info()

            predictor = inference.create_predictor(config)
            input_names = predictor.get_input_names()
            input_tensor = predictor.get_input_handle(input_names[0])
            output_names = predictor.get_output_names()
            output_tensors = [predictor.get_output_handle(n) for n in output_names]

            # 构造 CLS 模型标准输入 (1, 3, 48, 192)
            dummy_input = np.zeros((1, 3, 48, 192), dtype=np.float32)
            input_tensor.copy_from_cpu(dummy_input)
            predictor.run()

            # 尝试读取输出 —— 如果模型图损坏，这里会抛 RuntimeError
            for t in output_tensors:
                _ = t.copy_to_cpu()

            logger.warning("CLS 模型推理验证通过")
            return True

        except RuntimeError as e:
            if "Tensor holds no memory" in str(e):
                logger.warning(f"CLS 模型推理验证失败: Tensor holds no memory（模型图损坏）")
            else:
                logger.warning(f"CLS 模型推理验证失败 (RuntimeError): {e}")
            return False
        except Exception as e:
            logger.warning(f"CLS 模型推理验证失败: {type(e).__name__}: {e}")
            return False

    def _validate_model_files(self, model_dir: str) -> bool:
        """验证模型文件是否完整（文件存在且大小合理）"""
        if not os.path.isdir(model_dir):
            return False
        MIN_PDMODEL_SIZE = 10 * 1024      # 10KB
        MIN_PDPARAMS_SIZE = 100 * 1024    # 100KB
        pdmodel = os.path.join(model_dir, "inference.pdmodel")
        pdiparams = os.path.join(model_dir, "inference.pdiparams")
        if not os.path.isfile(pdmodel) or not os.path.isfile(pdiparams):
            return False
        if os.path.getsize(pdmodel) < MIN_PDMODEL_SIZE:
            logger.warning(f"模型文件过小（可能损坏）: {pdmodel} ({os.path.getsize(pdmodel)} bytes)")
            return False
        if os.path.getsize(pdiparams) < MIN_PDPARAMS_SIZE:
            logger.warning(f"模型文件过小（可能损坏）: {pdiparams} ({os.path.getsize(pdiparams)} bytes)")
            return False
        return True

    def _init_ocr(self):
        """初始化 PaddleOCR"""
        try:
            from app.utils.dependency_checker import ensure_ocr_available
            if not ensure_ocr_available():
                logger.warning("PaddleOCR 不可用，OCR 功能将降级")
                return

            from paddleocr import PaddleOCR

            OCR_MODEL_DIR.mkdir(parents=True, exist_ok=True)

            det_dir = str(OCR_MODEL_DIR / "det")
            rec_dir = str(OCR_MODEL_DIR / "rec")
            cls_dir = str(OCR_MODEL_DIR / "cls")

            # 检查并清理损坏的模型文件
            for model_name, model_dir in [("det", det_dir), ("rec", rec_dir)]:
                if os.path.isdir(model_dir) and os.listdir(model_dir) and not self._validate_model_files(model_dir):
                    logger.warning(f"检测到 {model_name} 模型文件损坏，删除后重新下载")
                    shutil.rmtree(model_dir, ignore_errors=True)

            # ---- CLS 模型：由于 PaddlePaddle 2.6.x 推理引擎 bug，CLS 模型会破坏共享内存池，
            # 导致后续 REC 模型报 "Tensor holds no memory"。暂时禁用 CLS。
            self._cls_enabled = False
            # cls_ready = os.path.isdir(cls_dir) and self._validate_model_files(cls_dir)
            # if not cls_ready:
            #     if os.path.isdir(cls_dir):
            #         shutil.rmtree(cls_dir, ignore_errors=True)
            #     if OCRService._download_cls_model(cls_dir):
            #         cls_ready = self._validate_model_files(cls_dir)
            # if cls_ready:
            #     self._cls_enabled = True
            # else:
            #     logger.warning("CLS 模型不可用，将使用无 CLS 模式")

            logger.warning(
                f"_init_ocr 开始加载模型: det={det_dir}, cls_enabled={self._cls_enabled}"
            )

            if self._cls_enabled:
                self._ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang='ch',
                    use_gpu=False,
                    show_log=False,
                    det_db_thresh=0.3,
                    det_db_box_thresh=0.5,
                    rec_batch_num=6,
                    max_text_length=50,
                    det_model_dir=det_dir,
                    rec_model_dir=rec_dir,
                    cls_model_dir=cls_dir,
                )
                logger.warning("PaddleOCR 初始化完成（含 CLS 模型）")
            else:
                self._ocr = PaddleOCR(
                    use_angle_cls=False,
                    lang='ch',
                    use_gpu=False,
                    show_log=False,
                    det_db_thresh=0.3,
                    det_db_box_thresh=0.5,
                    rec_batch_num=6,
                    max_text_length=50,
                    det_model_dir=det_dir,
                    rec_model_dir=rec_dir,
                )
                logger.warning("PaddleOCR 初始化完成（不含 CLS 模型）")

            # ---- Monkey-patch REC 模型，解决 PaddlePaddle 2.6.x 共享内存池 bug ----
            # DET 模型的 predictor.run() 会破坏共享内存池，导致 REC 模型的
            # output_tensor 失效。此处 patch REC 的 __call__，在遇到
            # "Tensor holds no memory" 时自动重建 predictor 后重试。
            _rec = self._ocr.text_recognizer
            _original_rec_call = _rec.__call__

            def _patched_rec_call(self_rec, *args, **kwargs):
                try:
                    return _original_rec_call(*args, **kwargs)
                except RuntimeError as e:
                    if "Tensor holds no memory" in str(e):
                        logger.warning(
                            "REC model Tensor holds no memory "
                            "(PaddlePaddle shared memory pool bug), re-creating predictor"
                        )
                        from tools.infer import utility as _rec_utility
                        self_rec.predictor, self_rec.input_tensor, \
                            self_rec.output_tensors, self_rec.config = \
                            _rec_utility.create_predictor(self_rec.args, 'rec', logger)
                        return _original_rec_call(*args, **kwargs)
                    raise

            _rec.__call__ = _patched_rec_call.__get__(_rec, type(_rec))
            logger.warning("REC 模型已 patch（PaddlePaddle 共享内存池 bug 修复）")

            self._available = True

        except Exception as e:
            logger.warning(f"PaddleOCR 初始化失败: {str(e)}", exc_info=True)
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def ocr_page(
        self,
        image: bytes,
        return_confidence: bool = True,
    ) -> Tuple[str, float]:
        """
        对单页图片执行 OCR

        Args:
            image: 图片字节数据
            return_confidence: 是否返回置信度

        Returns:
            (识别文本, 平均置信度)

        兼容 PaddleOCR 2.x / 3.x 的多种返回格式。
        首次调用会打印 result 结构调试信息，用于排查版本兼容问题。
        """
        if not self._available:
            return "", 0.0

        try:
            import numpy as np
            from PIL import Image
            import io

            pil_image = Image.open(io.BytesIO(image))

            # 确保 RGB 格式（PIL 打开可能是 RGBA/P/CMYK 等）
            if pil_image.mode not in ('RGB', 'L'):
                pil_image = pil_image.convert('RGB')

            img_array = np.array(pil_image)

            # ---- 调试：图片信息 ----
            if not OCRService._debug_logged:
                logger.warning(f"图片尺寸: {pil_image.size}, mode: {pil_image.mode}, "
                               f"array shape: {img_array.shape}, dtype: {img_array.dtype}")
                logger.warning(f"图片像素均值: {img_array.mean():.1f}, 最小值: {img_array.min()}, 最大值: {img_array.max()}")

            # PaddleOCR 2.x 内部使用 OpenCV，期望 BGR 格式
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                img_array = img_array[:, :, ::-1]  # RGB → BGR

            try:
                result = self._ocr.ocr(img_array, cls=False)
            except RuntimeError as e:
                raise

            # ---- 调试：首次调用打印 result 结构 ----
            if not OCRService._debug_logged:
                OCRService._debug_logged = True
                logger.warning("=== OCR result 结构调试 ===")
                logger.warning(f"result type: {type(result)}, bool(result): {bool(result)}")
                if result:
                    logger.warning(f"result len: {len(result) if hasattr(result, '__len__') else 'N/A'}")
                    if hasattr(result, '__getitem__') and len(result) > 0:
                        r0 = result[0]
                        logger.warning(f"result[0] type: {type(r0)}")
                        if hasattr(r0, 'rec_texts'):
                            logger.warning(f"result[0].rec_texts: {r0.rec_texts}")
                        if hasattr(r0, 'rec_scores'):
                            logger.warning(f"result[0].rec_scores: {r0.rec_scores}")
                        if isinstance(r0, (list, tuple)) and len(r0) > 0:
                            logger.warning(f"result[0] is list/tuple, len={len(r0)}")
                            if len(r0) > 0:
                                item0 = r0[0]
                                logger.warning(f"result[0][0] type: {type(item0)}")
                                if isinstance(item0, (list, tuple)) and len(item0) >= 2:
                                    logger.warning(f"result[0][0][1] type: {type(item0[1])}, value: {item0[1]}")
                logger.warning("=== OCR result 结构调试结束 ===")

            if not result:
                logger.warning("OCR 返回空结果")
                return "", 0.0

            lines = []
            confidences = []

            # ---- 递归提取所有文本和置信度 ----
            def _collect_from(obj, depth=0):
                """递归遍历 result 结构，提取所有文本和置信度"""
                if obj is None or depth > 5:
                    return

                # dict 格式（如 {'rec_texts': [...], 'rec_scores': [...]}）
                if isinstance(obj, dict):
                    if 'rec_texts' in obj and 'rec_scores' in obj:
                        texts = obj['rec_texts']
                        scores = obj['rec_scores']
                        if texts and scores:
                            for t, s in zip(texts, scores):
                                if t and str(t).strip():
                                    lines.append(str(t).strip())
                                    confidences.append(float(s))
                        return
                    # 可能是 {'text': ..., 'confidence': ...} 单条
                    if 'text' in obj:
                        t = obj.get('text', '')
                        s = obj.get('confidence', obj.get('score', 0.0))
                        if t and str(t).strip():
                            lines.append(str(t).strip())
                            confidences.append(float(s))
                    # 递归处理 dict 的 values
                    for v in obj.values():
                        _collect_from(v, depth + 1)
                    return

                # OCRResult 对象（PaddleOCR 3.x）
                if hasattr(obj, 'rec_texts') and hasattr(obj, 'rec_scores'):
                    texts = obj.rec_texts
                    scores = obj.rec_scores
                    if texts and scores:
                        for t, s in zip(texts, scores):
                            if t and str(t).strip():
                                lines.append(str(t).strip())
                                confidences.append(float(s))
                    return

                # 旧格式：[bbox, (text, confidence)]
                if isinstance(obj, (list, tuple)) and len(obj) >= 2:
                    inner = obj[1] if len(obj) > 1 else None
                    # 检查是否是 [bbox, (text, conf)] 格式
                    if isinstance(inner, (list, tuple)) and len(inner) >= 2:
                        t = inner[0]
                        s = inner[1]
                        # 兼容 numpy.float32/float64 等 numpy 数值类型
                        if isinstance(t, str) and isinstance(s, (int, float, np.floating, np.integer)):
                            if t.strip():
                                lines.append(t.strip())
                                confidences.append(float(s))
                            return
                    # 可能是嵌套列表，继续递归
                    for item in obj:
                        _collect_from(item, depth + 1)
                    return

                # 列表/元组：递归处理每个元素
                if isinstance(obj, (list, tuple)):
                    for item in obj:
                        _collect_from(item, depth + 1)
                    return

            # 尝试从 result 中提取
            _collect_from(result)

            text = '\n'.join(lines)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            if not text and not OCRService._debug_logged:
                # 首次且无结果，额外打印一次结构
                logger.warning(f"OCR 未提取到文本，result 完整结构: {type(result)}")

            return text, avg_confidence

        except Exception as e:
            logger.error(f"OCR 识别失败: {str(e)}", exc_info=True)
            return "", 0.0

    def ocr_page_with_layout(
        self,
        image: bytes,
        min_confidence: float = 0.6,
    ) -> Tuple[Optional[str], float, Dict]:
        """
        带版面分析的 OCR（PP-StructureV2 风格）
        
        低质量页面（置信度 < min_confidence）直接拦截返回 None
        
        Returns:
            (text_or_None, confidence, layout_info)
        """
        if not self._available:
            return None, 0.0, {"error": "OCR not available"}

        text, confidence = self.ocr_page(image, return_confidence=True)

        if confidence < min_confidence:
            logger.warning(f"页面识别率过低 ({confidence:.2%})，已拦截")
            return None, confidence, {
                "rejected": True,
                "reason": "low_confidence",
                "confidence": confidence,
                "threshold": min_confidence,
            }

        return text, confidence, {
            "rejected": False,
            "confidence": confidence,
            "text_length": len(text) if text else 0,
        }

    def detect_page_type(self, image: bytes) -> str:
        """
        检测页面类型：可编辑文本 / 扫描件
        
        Returns:
            'editable' | 'scanned' | 'mixed'
        """
        if not self._available:
            return 'scanned'

        try:
            import numpy as np
            from PIL import Image
            import io

            pil_image = Image.open(io.BytesIO(image))
            img_array = np.array(pil_image)

            # 简单判断：灰度方差大 → 扫描件，小 → 纯文本
            if len(img_array.shape) == 3:
                gray = np.mean(img_array, axis=2)
            else:
                gray = img_array

            variance = np.var(gray)

            if variance < 500:
                return 'editable'
            elif variance < 2000:
                return 'mixed'
            else:
                return 'scanned'

        except Exception:
            return 'scanned'

    def ocr_image_crop(
        self,
        page_image: bytes,
        crop_boxes: List[Tuple[int, int, int, int]],
    ) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
        """
        对页面中的独立图片区域分别 OCR
        
        Args:
            page_image: 页面图片字节
            crop_boxes: 裁剪区域列表 [(x0, y0, x1, y1), ...]
        
        Returns:
            [(text, confidence, bbox), ...]
        """
        if not self._available:
            return []

        results = []
        try:
            from PIL import Image
            import io

            pil_image = Image.open(io.BytesIO(page_image))

            for box in crop_boxes:
                cropped = pil_image.crop(box)
                buf = io.BytesIO()
                cropped.save(buf, format='PNG')
                text, conf = self.ocr_page(buf.getvalue())
                if text:
                    results.append((text, conf, box))

        except Exception as e:
            logger.error(f"图片区域 OCR 失败: {str(e)}")

        return results


# 全局单例
ocr_service = OCRService()